"""End-to-end incremental queue regression tests; no live providers."""
import json
import sqlite3
from pathlib import Path

import pytest

from france_admission_agent.memory.database import init_database
from france_admission_agent.pipeline import service
from france_admission_agent.pipeline.state import migrate, transition, request_refresh, now, identity
from france_admission_agent.pipeline.pool import OpportunityVector, compare, review_pool
from france_admission_agent.pipeline.research import TargetedResearch, evaluate
from france_admission_agent.pipeline.reporting import final_selection, convergence
from france_admission_agent.profile import load_candidate
from france_admission_agent.schemas import ProgrammeCandidate, CheckStatus


class MemoryResolver(TargetedResearch):
    seen=[]
    def resolve(self,candidate,p,fields,force=False):
        self.seen.append((p.programme_id,tuple(fields),force))
        return p


@pytest.fixture
def setup(tmp_path):
    db=tmp_path/'memory.db';conn=init_database(db);migrate(conn,tmp_path)
    MemoryResolver.seen=[]
    def run(stage='all',**kwargs):
        return service.run_pending(db_path=db,output_dir=tmp_path,stage=stage,resolver_factory=MemoryResolver,**kwargs)
    yield conn,db,run,tmp_path
    conn.close()


def cat(track='Track A'):
    return dict(institution_id='strasbourg',university='Université de Strasbourg',programme='Master Informatique',
                track=track,level='M1',city='Strasbourg',region='Grand Est',programme_url='https://www.unistra.fr/master/'+track.replace(' ','-'))


def add(conn,track='Track A'):
    data=cat(track);assert service.enqueue(conn,data,1)
    return conn.execute('SELECT programme_id FROM programme_workflow WHERE identity_key=?',(identity('strasbourg','Master Informatique',track),)).fetchone()[0]


def test_51_old_plus_three_new_processes_only_three(setup):
    conn,db,run,out=setup
    conn.execute("INSERT INTO universities(institution_id,canonical_name) VALUES ('legacy','Legacy')")
    for i in range(51):
        conn.execute("INSERT INTO programmes(programme_id,institution_id,programme_name) VALUES (?,'legacy','Old')",(str(i),))
    conn.commit();migrate(conn,out)
    new={add(conn,f'New {i}') for i in range(3)}
    metrics=run('cycle1')
    assert metrics['cycle1_processed']==3
    assert {p for p,_,_ in MemoryResolver.seen}==new
    assert conn.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]==54
    assert conn.execute("SELECT COUNT(*) FROM programme_workflow WHERE state='LEGACY_REVIEW'").fetchone()[0]==51


def test_cycle1_passed_is_not_reprocessed(setup):
    conn,db,run,out=setup;pid=add(conn)
    first=run('cycle1');MemoryResolver.seen=[]
    second=run('cycle1')
    assert first['cycle1_processed']==1
    assert second['cycle1_processed']==0
    assert MemoryResolver.seen==[]


def test_cycle2_completed_is_not_reprocessed(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1')
    conn.execute("UPDATE programme_workflow SET state='CYCLE2_VERIFIED',cycle2_status='VERIFIED',cycle2_processed_at=? WHERE programme_id=?",(now(),pid));conn.commit()
    result=run('cycle2')
    assert result['cycle2_processed']==0


def test_language_only_refresh(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1');MemoryResolver.seen=[]
    request_refresh(conn,pid,['language'],'Language source stale')
    result=run('cycle1')
    assert result['fields_refreshed']==1
    assert MemoryResolver.seen==[(pid,('language',),True)]
    assert result['cycle1_processed']==0


def strong(**changes):
    data=dict(academic_fit=3,degree_compatibility=3,prerequisite_match=3,language_compatibility=3,
              evidence_confidence=3,candidate_position=3,application_simplicity=2,
              regional_preference=3,region='Grand Est',family='informatics',credible=True)
    data.update(changes);return OpportunityVector(**data)


def seed_researched(conn,pid,v):
    from france_admission_agent.schemas import ProgrammeEvaluation, EvidenceItem
    row=conn.execute('SELECT cycle1_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()
    e=ProgrammeEvaluation.model_validate_json(row[0])
    e.eligibility.degree_field=e.eligibility.level=CheckStatus.PASS
    e.programme.official_sources=[EvidenceItem(claim=k,source_url=e.programme.programme_url,evidence_text='Official programme entry requirements',retrieved_at=now()) for k in ('accepted_degree_fields','level')]
    conn.execute("UPDATE programme_workflow SET cycle1_json=?,cycle1_vector_json=?,cycle1_status='PASSED' WHERE programme_id=?",(e.model_dump_json(),v.model_dump_json(),pid))


def test_weaker_survivor_not_promoted(setup):
    conn,db,run,out=setup;old=add(conn,'Old');new=add(conn,'New')
    run('cycle1')
    conn.execute("UPDATE programme_workflow SET state='POOL_RETAINED',pool_status='POOL_RETAINED',vector_json=? WHERE programme_id=?",(strong().model_dump_json(),old))
    weak=strong(academic_fit=1,language_compatibility=1,evidence_confidence=1,credible=False)
    conn.execute("UPDATE programme_workflow SET state='CYCLE1_PASSED',pool_status='NOT_REVIEWED',vector_json=? WHERE programme_id=?",(weak.model_dump_json(),new));conn.commit()
    seed_researched(conn,old,strong());seed_researched(conn,new,weak);conn.commit()
    result=run('cycle1')
    assert result['promoted_to_cycle2']==0
    assert conn.execute('SELECT pool_status FROM programme_workflow WHERE programme_id=?',(new,)).fetchone()[0]=='NOT_IMPROVE_POOL'


def test_lower_language_risk_promotes(setup):
    conn,db,run,out=setup;old=add(conn,'Old');new=add(conn,'New');run('cycle1')
    conn.execute("UPDATE programme_workflow SET state='POOL_RETAINED',pool_status='POOL_RETAINED',vector_json=? WHERE programme_id=?",(strong(language_compatibility=1).model_dump_json(),old))
    conn.execute("UPDATE programme_workflow SET state='CYCLE1_PASSED',pool_status='NOT_REVIEWED',vector_json=? WHERE programme_id=?",(strong().model_dump_json(),new));conn.commit()
    seed_researched(conn,old,strong(language_compatibility=1));seed_researched(conn,new,strong());conn.commit()
    result=run('cycle1')
    assert result['promoted_to_cycle2']==1
    assert conn.execute('SELECT state FROM programme_workflow WHERE programme_id=?',(new,)).fetchone()[0]=='CYCLE2_PENDING'


def test_pool_replacement_preserves_old_programme(setup):
    conn,db,run,out=setup;old=add(conn,'Old');new=add(conn,'New')
    conn.execute("UPDATE programme_workflow SET state='POOL_RETAINED',pool_status='POOL_RETAINED',vector_json=? WHERE programme_id=?",(strong(language_compatibility=1).model_dump_json(),old))
    conn.execute("UPDATE programme_workflow SET state='CYCLE2_VERIFIED',vector_json=? WHERE programme_id=?",(strong().model_dump_json(),new));conn.commit()
    metrics=review_pool(conn)
    assert metrics['pool_replacements']==1
    assert tuple(conn.execute('SELECT state,superseded_by FROM programme_workflow WHERE programme_id=?',(old,)).fetchone())==('POOL_DROPPED',new)
    assert conn.execute('SELECT state FROM programme_workflow WHERE programme_id=?',(new,)).fetchone()[0]=='POOL_RETAINED'
    assert conn.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]==2


def test_repeated_delta_is_idempotent_and_new_track_is_new(setup):
    conn,db,run,out=setup;add(conn)
    assert not service.enqueue(conn,cat(),2)
    altered=cat();altered['track']='  TRACK A  '
    assert not service.enqueue(conn,altered,2)
    add(conn,'Track B');result=run('cycle1')
    assert result['cycle1_processed']==2
    assert conn.execute('SELECT COUNT(*) FROM universities').fetchone()[0]==1
    assert conn.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]==2


def test_zero_delta_does_not_rerun_old_work(setup):
    conn,db,run,out=setup;add(conn);run();MemoryResolver.seen=[]
    result=run()
    assert result['cycle1_processed']==result['cycle2_processed']==0
    assert not MemoryResolver.seen


def test_invalid_transition_and_crash_recovery(setup):
    conn,db,run,out=setup;pid=add(conn)
    with pytest.raises(ValueError,match='INVALID_PIPELINE_STATE_TRANSITION'):
        transition(conn,pid,'POOL_RETAINED')
    transition(conn,pid,'CYCLE1_PROCESSING','Simulated interrupted process');conn.commit()
    result=run('cycle1')
    assert result['cycle1_processed']==1
    assert conn.execute("SELECT COUNT(*) FROM pipeline_events WHERE reason='Recovered interrupted work'").fetchone()[0]==1


def test_failed_stage_can_resume_without_losing_completed_work(setup):
    conn,db,run,out=setup;add(conn)
    class FailResolver(MemoryResolver):
        def resolve(self,*a,**k): raise RuntimeError('simulated')
    result=service.run_pending(db_path=db,output_dir=out,stage='cycle1',resolver_factory=FailResolver)
    assert result['errors']==1
    assert conn.execute('SELECT state FROM programme_workflow').fetchone()[0]=='CYCLE1_PENDING'
    assert run('cycle1')['cycle1_processed']==1


def test_unverified_stats_never_gain_advantage(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1')
    e=__import__('france_admission_agent.schemas',fromlist=['ProgrammeEvaluation']).ProgrammeEvaluation.model_validate_json(conn.execute('SELECT cycle1_json FROM programme_workflow').fetchone()[0])
    conn.execute("INSERT INTO admission_statistics(programme_id,academic_year,applicants,capacity,source_url,verification_status) VALUES (?,'2025',10,50,'https://www.unistra.fr/stats','UNVERIFIED_STATISTIC')",(pid,));conn.commit()
    assert service.vector(conn,e).historical_opportunity is None


def test_final_selection_does_not_invent_seven_or_search(setup):
    conn,db,run,out=setup;result=final_selection(db,out)
    assert result['finalists']==0
    assert 'Fewer than seven' in Path(result['report']).read_text(encoding='utf-8')


def test_zero_search_rounds_do_not_count_as_diminishing_returns(setup):
    conn,db,run,out=setup
    for n in range(4):
        conn.execute("INSERT INTO pipeline_rounds(round_number,metrics_json,actual_searches,successful_searches,distinct_frontiers,pool_improvements) VALUES (?,'{}',0,0,0,0)",(n,))
    conn.commit()
    assert convergence(conn)['consecutive_rounds_without_pool_improvement']==0
    assert not convergence(conn)['final_selection_ready']


def test_unknown_level_is_not_hard_failure(setup):
    conn,db,run,out=setup
    p=ProgrammeCandidate(programme_id='x',university='Unknown',programme='Master Informatique',city='City',level='M2')
    e=evaluate(load_candidate('config/candidate_profile.json'),p)
    assert not e.rejected
    assert e.eligibility.level==CheckStatus.UNVERIFIED


def test_promoted_challenger_gets_cycle2_only_once(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1')
    conn.execute("UPDATE programme_workflow SET state='CYCLE2_PENDING',cycle2_status='PENDING',pool_status='NOT_REVIEWED' WHERE programme_id=?",(pid,));conn.commit()
    first=run('cycle2');second=run('cycle2')
    assert first['cycle2_processed']==1
    assert first['cycle2_verified']==0  # no fabricated evidence in MemoryResolver
    assert second['cycle2_processed']==0
    assert conn.execute('SELECT pool_status FROM programme_workflow').fetchone()[0]=='INSUFFICIENT_EVIDENCE'


def test_migration_completed_snapshots_retains_uncertainty_without_reprocessing(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1')
    row=conn.execute('SELECT * FROM programme_workflow').fetchone()
    data=json.loads(row['cycle1_json'])
    (out/'cycle1_results.json').write_text(json.dumps({'evaluations':[data]}),encoding='utf-8')
    (out/'cycle2_analysis.json').write_text(json.dumps([{'programme':data['programme'],'cycle1_evaluation':data}]),encoding='utf-8')
    conn.execute('DELETE FROM programme_workflow');conn.commit();MemoryResolver.seen=[]
    result=run()
    assert result['cycle1_processed']==result['cycle2_processed']==0
    assert result['current_pool_size']==0
    assert not MemoryResolver.seen


def test_verified_historical_parser_requires_unambiguous_cohort():
    from france_admission_agent.pipeline.research import parse_claims
    assert parse_claims('historical',"capacity: 30 applicants: 200")=={}
    text="M1 2024-2025 total applications: 200; capacit\u00e9 d'accueil: 30"
    assert parse_claims('historical',text)=={'applicant_count':200,'capacity':30}
    assert parse_claims('historical',text+' 2025-2026')=={}


def test_partial_progress_keeps_completed_records_on_failure(setup):
    conn,db,run,out=setup;ids={add(conn,'First'),add(conn,'Second')}
    fail_id=sorted(ids)[1]
    class PartialResolver(MemoryResolver):
        def resolve(self,c,p,fields,force=False):
            if p.programme_id==fail_id: raise RuntimeError('simulated')
            return super().resolve(c,p,fields,force)
    result=service.run_pending(db_path=db,output_dir=out,stage='cycle1',resolver_factory=PartialResolver)
    assert result['cycle1_processed']==1
    assert result['errors']==1
    MemoryResolver.seen=[]
    assert run('cycle1')['cycle1_processed']==1
    assert {p for p,_,_ in MemoryResolver.seen}=={fail_id}


def test_cycle2_keeps_original_cycle1_snapshot(setup):
    conn,db,run,out=setup;pid=add(conn);run('cycle1')
    snapshot=json.loads(conn.execute('SELECT cycle1_json FROM programme_workflow').fetchone()[0])
    snapshot['classification']='Original Cycle 1 assessment'
    original=json.dumps(snapshot)
    conn.execute("UPDATE programme_workflow SET state='CYCLE2_PENDING',cycle2_status='PENDING',pool_status='NOT_REVIEWED',cycle1_json=? WHERE programme_id=?",(original,pid));conn.commit()
    result=run('cycle2')
    assert result['cycle2_processed']==1
    assert conn.execute('SELECT cycle1_json FROM programme_workflow').fetchone()[0]==original
    assert conn.execute('SELECT cycle2_json FROM programme_workflow').fetchone()[0]


def test_no_provider_keeps_research_pending(setup):
    conn,db,run,out=setup;pid=add(conn)
    result=service.run_pending(db_path=db,output_dir=out,stage='cycle1',search=None)
    assert result['cycle1_passed']==0
    assert result['cycle1_deferred']==1
    assert conn.execute('SELECT state FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0]=='CYCLE1_PENDING'


def test_single_programme_run_leaves_other_pending_untouched(setup):
    conn,db,run,out=setup
    chosen=add(conn,'Chosen');other=add(conn,'Other')
    MemoryResolver.seen=[]
    result=service.run_pending(db_path=db,output_dir=out,stage='cycle1',resolver_factory=MemoryResolver,programme_id=chosen)
    assert result['cycle1_processed']==1
    assert [pid for pid,_,_ in MemoryResolver.seen]==[chosen]
    assert conn.execute('SELECT state FROM programme_workflow WHERE programme_id=?',(other,)).fetchone()[0]=='CYCLE1_PENDING'


def test_compare_old_cycle1_without_deep_pool(setup):
    conn,db,run,out=setup;old=add(conn,'Old');new=add(conn,'New');run('cycle1')
    seed_researched(conn,old,strong());seed_researched(conn,new,strong(academic_fit=1))
    conn.execute("UPDATE programme_workflow SET state='CYCLE1_PASSED',pool_status='NOT_REVIEWED'");conn.commit()
    result=run('cycle1')
    details=json.loads(conn.execute('SELECT cycle1_comparison_json FROM programme_workflow WHERE programme_id=?',(new,)).fetchone()[0])
    assert old in details['compared_against']
    assert details['decision']=='NOT_IMPROVE_POOL'
    assert result['current_pool_size']==0
    assert (out/'Cycle1-Detailed-Latest.md').exists()


def test_incomplete_cycle1_is_review_not_pass(setup):
    conn,db,run,out=setup;pid=add(conn);result=run('cycle1')
    assert result['cycle1_review_required']==1
    assert result['cycle1_passed']==0
    assert result['promoted_to_cycle2']==0


def test_language_without_scoped_source_is_unverified(setup):
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    e=evaluate(load_candidate('config/candidate_profile.json'),p)
    assert e.eligibility.language==CheckStatus.UNVERIFIED


def test_official_french_b2_policy_rejects_candidate_without_certificate(setup):
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    url='https://www.unistra.fr/international/french-requirement'
    TargetedResearch.apply(p,'teaching_language','French',url,'Track A: French instruction for this programme',now())
    TargetedResearch.apply(p,'french_level_required','B2',url,'Track A: French CEFR B2 required',now())
    e=evaluate(load_candidate('config/candidate_profile.json'),p)
    assert e.rejected
    assert e.eligibility.french==CheckStatus.FAIL


def test_official_page_read_before_search_and_shared_across_fields(setup,monkeypatch):
    import httpx
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    requests=[]
    def serve(request):
        requests.append(str(request.url))
        return httpx.Response(200,headers={'content-type':'text/html'},text='<main>Master Informatique Track A. Admission M1: titulaire licence informatique. Language of instruction: English.</main>')
    real_client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(serve),**kw))
    class NoSearchExpected:
        def search(self,*args,**kwargs): raise AssertionError('Page evidence should avoid searches')
    r=TargetedResearch(conn,NoSearchExpected(),3)
    r.resolve(load_candidate('config/candidate_profile.json'),p,('degree','structure','language'))
    assert len(requests)==1
    assert r.metrics['external_searches']==0
    assert {'accepted_degree_fields','level','teaching_language'} <= {e.claim for e in p.official_sources}


def test_homepage_cannot_supply_programme_evidence(setup):
    from france_admission_agent.pipeline.research import scoped
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    p.programme_url='https://www.unistra.fr/en'
    assert not scoped(p,str(p.programme_url),'Track A Master 1 Licence informatique')


def test_official_programme_page_with_query_id_is_in_scope(setup):
    from france_admission_agent.pipeline.research import scoped
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    p.programme_url='https://www.unistra.fr/?page_id=29'
    assert scoped(p,str(p.programme_url),'Master Informatique Track A')
    assert not scoped(p,'https://www.unistra.fr/','Master Informatique Track A')


def test_general_catalogue_cannot_reject_unrelated_track(setup):
    from france_admission_agent.pipeline.research import scoped
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    p.track='Science des Données et IA'
    p.programme_url='https://international-welcome.unistra.fr/apply-to-the-university-of-strasbourg/courses-of-the-university-of-strasbourg/courses-taught-in-english/masters-degrees-taught-in-english'
    assert not scoped(p,str(p.programme_url),'Master Computer Science. M2 only in Business Law')


def test_long_generic_catalogue_cannot_supply_other_track_language(setup):
    from france_admission_agent.pipeline.research import scoped
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    p.programme_url='https://www.unistra.fr/master-informatique'
    text='Track A. '+'Other tracks and courses. '*100+'Language of instruction: French'
    assert not scoped(p,p.programme_url,text)
    assert scoped(p,'https://www.unistra.fr/master/Track-A','Track A: Language of instruction English')


def test_same_specific_track_url_deduplicates_name_variant(setup):
    conn,db,run,out=setup
    first=cat('Data Science (DS)');first['programme_url']='https://www.unistra.fr/master/parcours-data-science'
    assert service.enqueue(conn,first,1)
    second=cat('Data Science');second['programme_url']=first['programme_url']
    assert service.known_identity(conn,second)
    assert not service.enqueue(conn,second,2)


def test_existing_specific_url_duplicates_are_superseded_idempotently(setup):
    from france_admission_agent.pipeline.cycle1_review import dedupe_specific_urls
    conn,db,run,out=setup
    first=add(conn,'Track A');second=add(conn,'Track B')
    url='https://www.unistra.fr/master/parcours-shared'
    conn.execute('UPDATE programmes SET official_url=? WHERE programme_id IN (?,?)',(url,first,second))
    conn.commit()
    assert dedupe_specific_urls(conn)==1
    rows=conn.execute('SELECT programme_id,superseded_by FROM programme_workflow WHERE programme_id IN (?,?)',(first,second)).fetchall()
    assert sum(bool(r['superseded_by']) for r in rows)==1
    assert dedupe_specific_urls(conn)==0


def test_failed_page_fetch_not_repeated_per_field(setup,monkeypatch):
    import httpx
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    real_client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(lambda request:httpx.Response(404)),**kw))
    r=TargetedResearch(conn,budget=4)
    assert r.fetch_compact(p,str(p.programme_url),'degree')==''
    assert r.fetch_compact(p,str(p.programme_url),'language')==''
    assert r.metrics['page_fetches']==1
    assert r.page_diagnostics[0]['status']=='HTTP_404'


def test_official_redirect_is_followed_but_external_redirect_is_blocked(setup,monkeypatch):
    import httpx
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    requested=[]
    def serve(request):
        requested.append(str(request.url))
        if str(request.url).endswith('/Track-A'):
            return httpx.Response(301,headers={'location':'/master/Track-A/'})
        return httpx.Response(200,headers={'content-type':'text/html'},text='<main>Master Informatique Track A</main>')
    real_client=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(serve),**kw))
    r=TargetedResearch(conn,budget=2)
    assert 'Master Informatique' in r.fetch_compact(p,str(p.programme_url),'degree')
    assert len(requested)==2
    requested.clear()
    def external(request):
        requested.append(str(request.url))
        return httpx.Response(301,headers={'location':'https://example.org/master'})
    monkeypatch.setattr(httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(external),**kw))
    r=TargetedResearch(conn,budget=2)
    assert r.fetch_compact(p,str(p.programme_url),'degree',force=True)==''
    assert len(requested)==1
    assert r.page_diagnostics[-1]['status']=='UNSAFE_OR_EXCESS_REDIRECT'


def test_language_labels_from_caen_page():
    from france_admission_agent.pipeline.research import parse_claims
    claims=parse_claims('language','Minimum French level required: C1 Minimum English level required: B2 Language of instruction French')
    assert claims=={'teaching_language':'French','french_level_required':'C1','english_cefr_required':'B2'}
    assert parse_claims('language','Filter languages: French English Other language')=={}


def test_explicit_miage_degree_wording_is_preserved():
    from france_admission_agent.pipeline.research import parse_claims
    text='The M1 MIAGE is based on student report for the graduates of a three-year training (BAC+3) with computer science and management.'
    assert parse_claims('degree',text)=={'accepted_degree_fields':['BAC+3 with computer science and management']}


def test_course_language_does_not_override_master_language():
    from france_admission_agent.pipeline.research import parse_claims
    text="Langue(s) d'enseignement Français. Courses taught in English (B2 level required). Admission en Master 1 : Licence dans le même domaine (180 crédits)."
    assert parse_claims('language',text)['teaching_language']=='French'
    assert parse_claims('degree',text)=={'accepted_degree_fields':['Licence in the same field (180 ECTS)']}


def test_evidence_keeps_late_page_claim(setup):
    conn,db,run,out=setup;pid=add(conn)
    p=ProgrammeCandidate.model_validate_json(conn.execute('SELECT candidate_json FROM programme_workflow WHERE programme_id=?',(pid,)).fetchone()[0])
    text='Course overview. '*200+'Language of instruction French'
    r=TargetedResearch(conn)
    assert r.consume(p,'language',str(p.programme_url),text,'2027')
    assert 'Language of instruction French' in p.official_sources[-1].evidence_text
