from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from ..memory.database import get_connection
from ..memory.coverage import FRANCE_REGIONS_REGISTRY
from ..profile import load_candidate
from ..schemas import ProgrammeCandidate, ProgrammeEvaluation, Cycle2Evaluation, CheckStatus, SelectivityAnalysis
from ..cycle2.competitiveness import analyze_admission_competitiveness
from .state import SCHEMA, VERSION, identity, migrate, now, transition, recover, request_refresh, pipeline_lock
from .research import TargetedResearch, evaluate, FIELDS
from .pool import vector, compare, current_pool, review_pool
from .cycle1_review import cycle1_outcome, promotion_decisions, write_cycle1_reports, repair_previous_cycle1, audit_saved_scope, dedupe_specific_urls


def known_identity(conn,cat):
    key=identity(cat['institution_id'],cat['programme'],cat.get('track'),cat.get('level','M1'))
    new_url=str(cat.get('programme_url') or '').split('?',1)[0].rstrip('/').casefold()
    specific_url='parcours-' in urlparse(new_url).path
    # Match canonical names even when an older importer assigned a different hash.
    for row in conn.execute('SELECT programme_id,programme_name,track_name,level FROM programmes WHERE institution_id=?',(cat['institution_id'],)):
        if identity(cat['institution_id'],row['programme_name'],row['track_name'],row['level'])==key:
            return row['programme_id']
    # A programme-specific track URL is a stronger identity than formatting
    # differences such as an acronym added to the track title.
    if specific_url:
        for row in conn.execute('SELECT programme_id,official_url FROM programmes WHERE institution_id=?',(cat['institution_id'],)):
            if str(row['official_url'] or '').split('?',1)[0].rstrip('/').casefold()==new_url:
                return row['programme_id']
    return None


def enqueue(conn,cat,round_number,intake='2027'):
    conn.executescript(SCHEMA)
    if known_identity(conn,cat): return False
    pid=hashlib.sha256(f"{cat['institution_id']}::{cat['programme']}::{cat['track']}".encode()).hexdigest()[:16]
    inst=next((u for us in FRANCE_REGIONS_REGISTRY.values() for u in us if u['id']==cat['institution_id']),None)
    domain=inst['domain'] if inst else None
    p=ProgrammeCandidate(programme_id=pid,institution_id=cat['institution_id'],track_id=cat['track'].casefold(),
        university=cat['university'],programme=cat['programme'],track=cat['track'],level=cat.get('level','M1'),
        city=cat['city'],public=True if inst else None,programme_url=cat.get('programme_url'),official_university_domain=domain)
    # Discovery is a lead, not verified eligibility. Preserve only identity/source.
    text=(p.programme+' '+(p.track or '')).casefold()
    reject=None
    if cat.get('public') is False: reject='Explicitly non-public institution'
    if cat.get('country','France').casefold()!='france': reject='Outside France'
    if not any(x in text for x in ('informatique','computer science','logiciel','software','miage','systems','systèmes','data science','science des données')): reject='Outside computing scope'
    # Ambiguous M2/language/active status remains unknown until official verification.
    with conn:
        conn.execute('''INSERT OR IGNORE INTO universities(institution_id,canonical_name,city,region,is_public,official_domains,coverage_status)
            VALUES (?,?,?,?,?,?,'PARTIALLY_RESEARCHED')''',(p.institution_id,p.university,p.city,cat['region'],p.public,json.dumps([domain] if domain else [])))
        conn.execute('''INSERT INTO programmes(programme_id,institution_id,track_id,programme_name,track_name,level,city,official_url,
            is_viable,cycle1_group,score_status) VALUES (?,?,?,?,?,?,?,?,0,'D_NEEDS_OTHER_VERIFICATION','PROVISIONAL')''',
            (pid,p.institution_id,p.track_id,p.programme,p.track,p.level,p.city,str(p.programme_url or '')))
        conn.execute('''INSERT INTO programme_workflow(programme_id,institution_id,track_id,identity_key,discovered_round,candidate_json,target_intake)
            VALUES (?,?,?,?,?,?,?)''',(pid,p.institution_id,p.track_id,identity(p.institution_id,p.programme,p.track,p.level),round_number,p.model_dump_json(),intake))
        transition(conn,pid,'DISCOVERY_REJECTED' if reject else 'CYCLE1_PENDING',reject or 'New delta passed cheap scope filters',round_number)
    return True


def save_evaluation(conn,row,e,stage):
    pid=row['programme_id'];v=vector(conn,e)
    old=ProgrammeCandidate.model_validate_json(row['candidate_json'])
    changed=old.model_dump(mode='json').get('official_sources')!=e.programme.model_dump(mode='json').get('official_sources')
    conn.execute('''UPDATE programme_workflow SET candidate_json=?,vector_json=?,evidence_version=evidence_version+?,
        evidence_last_updated=CASE WHEN ? THEN ? ELSE evidence_last_updated END,last_error=NULL WHERE programme_id=?''',
        (e.programme.model_dump_json(),v.model_dump_json(),int(changed),int(changed),now(),pid))
    if stage != 'cycle2':
        conn.execute('UPDATE programme_workflow SET cycle1_json=?,cycle1_vector_json=? WHERE programme_id=?',(e.model_dump_json(),v.model_dump_json(),pid))
    conn.execute('UPDATE programmes SET cycle1_group=?,is_viable=?,is_rejected=?,profile_fit_score=?,evidence_confidence_score=?,unresolved_fields=? WHERE programme_id=?',
        (e.group,int(not e.rejected),int(e.rejected),e.score.profile_fit_score,e.score.evidence_confidence_score,json.dumps(v.unknowns),pid))
    return v


def safe_cycle2(candidate,e,conn):
    # Reuse the existing analyzer, but suppress unsourced fixture benchmarks and
    # unsupported equivalence narratives at this new evidence-gated boundary.
    result=analyze_admission_competitiveness(candidate,e,use_known_benchmarks=False)
    s=result.selectivity
    v=vector(conn,e)
    s.academic_strictness=s.degree_strictness=s.prerequisite_strictness='UNKNOWN'
    s.international_process_complexity='LOW' if v.application_simplicity else 'UNKNOWN'
    s.language_risk='LOW' if v.language_compatibility==3 else 'UNKNOWN'
    s.selectivity_pressure={3:'LOW',2:'MODERATE',1:'HIGH'}.get(v.historical_opportunity,'UNKNOWN')
    s.candidate_fit_strength='STRONG' if v.academic_fit==3 else 'MODERATE'
    s.candidate_strengths=[f'{candidate.degree.title}; CGPA {candidate.degree.cgpa}/{candidate.degree.scale}; {candidate.degree.credits} Pakistani university credits.']
    s.reasons_candidate_is_competitive=['Verified prerequisites match candidate coursework.'] if v.prerequisite_match else []
    s.reasons_admission_may_fail=['Unresolved evidence requires review: '+', '.join(v.unknowns)]
    s.unknowns=v.unknowns
    s.academic_strictness_evidence=s.degree_strictness_evidence=s.prerequisite_strictness_evidence=None
    s.international_process_evidence=e.programme.application_route if v.application_simplicity else None
    s.selectivity_pressure_evidence='Audited historical applications / capacity, not an admission probability.' if v.historical_opportunity else None
    from ..schemas import HistoricalMetric
    from .research import official
    for stat in conn.execute("SELECT * FROM admission_statistics WHERE programme_id=? AND verification_status IN ('VERIFIED_CURRENT','VERIFIED_HISTORICAL') ORDER BY academic_year DESC",(e.programme.programme_id,)):
        if not stat['source_url'] or not official(e.programme,stat['source_url']): continue
        for attr,key in [('capacity','capacity'),('historical_applicants','applicants'),('historical_admitted','admitted')]:
            if stat[key] is not None:
                setattr(s,attr,HistoricalMetric(value=stat[key],year=stat['academic_year'],source=stat['source_url'],population=stat['population'],metric_definition=key))
        break
    return result


def schedule_changes(conn,intake):
    for row in conn.execute("SELECT * FROM programme_workflow WHERE state NOT IN ('LEGACY_REVIEW','DISCOVERED_NEW','CYCLE1_PENDING','CYCLE1_PROCESSING','CYCLE2_PENDING','CYCLE2_PROCESSING','REQUIRES_REFRESH')").fetchall():
        fields=[];reason=[]
        if row['target_intake']!=intake: fields+=['calendar','route'];reason+=['Target intake changed']
        if row['pool_status']=='POOL_RETAINED' and row['evidence_last_updated']:
            from datetime import datetime,timezone
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['evidence_last_updated']).replace(tzinfo=timezone.utc)).days
                if age>90: fields+=['language','calendar','route','structure'];reason+=['Critical sources stale']
            except ValueError: pass
        cutoff=row['evidence_last_updated'] or row['cycle2_processed_at'] or row['cycle1_processed_at'] or row['updated_at']
        newer=conn.execute("SELECT DISTINCT claim_type FROM evidence WHERE programme_id=? AND retrieved_at>? AND verification_status='VERIFIED_CURRENT'",(row['programme_id'],cutoff)).fetchall()
        for ev in newer:
            fields += [f for f,keys in FIELDS.items() if ev['claim_type'] in keys]
        if newer: reason+=['New or changed official evidence']
        if fields: request_refresh(conn,row['programme_id'],fields,'; '.join(reason))


def refresh_pending(conn,candidate,resolver,limit=10):
    count=0
    for row in conn.execute("SELECT * FROM programme_workflow WHERE state='REQUIRES_REFRESH' LIMIT ?",(limit,)).fetchall():
        p=ProgrammeCandidate.model_validate_json(row['candidate_json']);fields=json.loads(row['refresh_fields'])
        keys=set().union(*(FIELDS[f] for f in fields))
        p.official_sources=[x for x in p.official_sources if x.claim not in keys]
        # Clear only requested field groups. Unrelated completed research survives.
        fresh=ProgrammeCandidate(programme_id=p.programme_id,university=p.university,programme=p.programme,level=p.level,city=p.city)
        attrs={'language':['language','teaching_language_info','english_req_info','french_req_info'],
               'calendar':['canonical_cycle','deadline','deadline_cycle','cycle_status'],
               'degree':['accepted_degree_fields'],'prerequisites':['explicit_prerequisites','transcript_match_info'],
               'route':['application_route','application_route_info'],'structure':['programme_structure']}
        for f in fields:
            for attr in attrs.get(f,[]): setattr(p,attr,getattr(fresh,attr))
        try:
            resolver.resolve(candidate,p,fields,force=True)
            had_c2=bool(row['cycle2_processed_at'])
            e=evaluate(candidate,p);v=save_evaluation(conn,row,e,'cycle2' if had_c2 else 'refresh')
            state=('CYCLE2_REJECTED' if e.rejected else ('CYCLE2_VERIFIED' if v.credible else 'CYCLE2_REVIEW_REQUIRED')) if had_c2 else ('CYCLE1_'+cycle1_outcome(e))
            transition(conn,p.programme_id,state,'Field refresh: '+', '.join(fields))
            if had_c2:
                c2=safe_cycle2(candidate,e,conn)
                conn.execute('UPDATE programme_workflow SET cycle2_json=?,cycle2_version=?,cycle2_processed_at=? WHERE programme_id=?',(c2.model_dump_json(),VERSION,now(),p.programme_id))
            conn.execute("UPDATE programme_workflow SET needs_refresh=0,refresh_fields='[]',resume_state=NULL,pool_status='NOT_REVIEWED',target_intake=? WHERE programme_id=?",(candidate.target.intake,p.programme_id))
            conn.commit();count+=len(fields)
        except Exception as exc:
            conn.rollback();conn.execute('UPDATE programme_workflow SET last_error=? WHERE programme_id=?',(type(exc).__name__,p.programme_id));conn.commit()
    return count


def run_pending(db_path='data/france_research.db',candidate_path='config/candidate_profile.json',output_dir='output',
                search=None,stage='all',round_number=None,cycle1_limit=20,cycle2_limit=5,promotion_limit=5,
                cycle1_budget=6,cycle2_budget=6,resolver_factory=TargetedResearch,programme_id=None):
    with pipeline_lock(db_path):
        conn=get_connection(db_path)
        try:
            candidate=load_candidate(candidate_path);migrated=migrate(conn,output_dir,candidate.target.intake);recover(conn);repaired=repair_previous_cycle1(conn)
            scope_demotions=audit_saved_scope(conn)
            duplicate_ids=dedupe_specific_urls(conn)
            # Evaluate imported completed analyses for migration only; no searches.
            for row in conn.execute("SELECT * FROM programme_workflow WHERE cycle1_json IS NOT NULL AND vector_json IS NULL").fetchall():
                e=ProgrammeEvaluation.model_validate_json(row['cycle1_json']);v=vector(conn,e)
                conn.execute('UPDATE programme_workflow SET vector_json=? WHERE programme_id=?',(v.model_dump_json(),row['programme_id']))
                if row['cycle2_json'] and v.credible:
                    conn.execute("UPDATE programme_workflow SET state='CYCLE2_VERIFIED',cycle2_status='VERIFIED' WHERE programme_id=?",(row['programme_id'],))
            conn.commit();schedule_changes(conn,candidate.target.intake)
            metrics=dict(migrated_records=migrated,repaired_cycle1_records=repaired,scope_demotions=scope_demotions,duplicate_ids=duplicate_ids,cycle1_processed=0,cycle1_passed=0,cycle1_rejected=0,cycle1_review_required=0,cycle1_deferred=0,
                promoted_to_cycle2=0,cycle2_processed=0,cycle2_verified=0,cycle2_rejected=0,fields_refreshed=0,
                pool_additions=0,pool_replacements=0,pool_unchanged_candidates=0,errors=0)
            r1=resolver_factory(conn,search,cycle1_budget);r2=resolver_factory(conn,search,cycle2_budget)
            start_event=conn.execute('SELECT COALESCE(MAX(id),0) FROM pipeline_events').fetchone()[0]
            if stage in ('all','cycle1','cycle2'):
                metrics['fields_refreshed']=refresh_pending(conn,candidate,r1)
            if stage in ('all','cycle1'):
                rows=conn.execute("SELECT * FROM programme_workflow WHERE state='CYCLE1_PENDING' AND (? IS NULL OR programme_id=?) ORDER BY discovered_round,programme_id LIMIT ?",(programme_id,programme_id,cycle1_limit)).fetchall()
                for row in rows:
                    pid=row['programme_id'];transition(conn,pid,'CYCLE1_PROCESSING','Incremental Cycle 1',round_number);conn.commit()
                    try:
                        p=ProgrammeCandidate.model_validate_json(row['candidate_json'])
                        e=evaluate(candidate,p,r1,('degree','structure','language','prerequisites','route','calendar'))
                        save_evaluation(conn,row,e,'cycle1')
                        status=cycle1_outcome(e)
                        if status!='REJECTED' and getattr(r1,'deferred_fields',{}).get(pid):
                            status='PENDING'
                        transition(conn,pid,'CYCLE1_'+status,'Evidence-backed eligibility screening',round_number)
                        conn.execute('UPDATE programme_workflow SET cycle1_status=?,cycle1_version=?,cycle1_processed_at=? WHERE programme_id=?',(status,VERSION,now(),pid))
                        conn.commit()
                        if status=='PENDING': metrics['cycle1_deferred']+=1
                        else:
                            metrics['cycle1_processed']+=1;metrics['cycle1_'+status.lower()]+=1
                    except Exception as exc:
                        conn.rollback();transition(conn,pid,'CYCLE1_PENDING','Retry after '+type(exc).__name__)
                        conn.execute('UPDATE programme_workflow SET last_error=? WHERE programme_id=?',(type(exc).__name__,pid));conn.commit();metrics['errors']+=1
            if stage in ('all','cycle1','cycle2'):
                # Rank and compare saved Cycle 1 snapshots before promotion.
                for row,details in promotion_decisions(conn):
                    if metrics['promoted_to_cycle2']>=promotion_limit: break
                    pid=row['programme_id']
                    if row['state']=='CYCLE1_PASSED': transition(conn,pid,'PROMOTION_REVIEW','Compare saved Cycle 1 research',round_number)
                    decision=details['decision'];reason=details['reason']
                    if decision in ('OUTPERFORM_EXISTING','COMPLEMENT_EXISTING'):
                        transition(conn,pid,'CYCLE2_PENDING',decision+': '+reason,round_number)
                        metrics['promoted_to_cycle2']+=1
                    elif decision=='INSUFFICIENT_EVIDENCE':
                        transition(conn,pid,'CYCLE1_REVIEW_REQUIRED',reason,round_number)
                    else:
                        transition(conn,pid,'POOL_DROPPED',decision+': '+reason,round_number)
                        conn.execute('UPDATE programme_workflow SET pool_status=? WHERE programme_id=?',(decision,pid))
                        metrics['pool_unchanged_candidates']+=1
                    conn.commit()
            if stage in ('all','cycle2'):
                for row in conn.execute("SELECT * FROM programme_workflow WHERE state='CYCLE2_PENDING' ORDER BY COALESCE(json_extract(cycle1_comparison_json,'$.rank'),1000000),discovered_round,programme_id LIMIT ?",(cycle2_limit,)).fetchall():
                    pid=row['programme_id'];transition(conn,pid,'CYCLE2_PROCESSING','Promoted challenger only',round_number);conn.commit()
                    try:
                        p=ProgrammeCandidate.model_validate_json(row['candidate_json'])
                        prior=ProgrammeEvaluation.model_validate_json(row['cycle1_json'])
                        fields=[]
                        for field,check in [('language',prior.eligibility.language),('degree',prior.eligibility.degree_field),('structure',prior.eligibility.level),('route',prior.eligibility.application_route),('prerequisites',p.transcript_match_info.status)]:
                            if check!=CheckStatus.PASS: fields.append(field)
                        r2.resolve(candidate,p,fields+['historical','tuition','stability'])
                        e=evaluate(candidate,p);v=save_evaluation(conn,row,e,'cycle2');c2=safe_cycle2(candidate,e,conn)
                        status='REJECTED' if e.rejected else ('VERIFIED' if v.credible else 'REVIEW_REQUIRED')
                        transition(conn,pid,'CYCLE2_'+status,'Deep targeted checks completed',round_number)
                        conn.execute('UPDATE programme_workflow SET cycle2_status=?,cycle2_version=?,cycle2_processed_at=?,cycle2_json=? WHERE programme_id=?',(status,VERSION,now(),c2.model_dump_json(),pid))
                        conn.commit();metrics['cycle2_processed']+=1
                        if status!='REVIEW_REQUIRED': metrics['cycle2_'+status.lower()]+=1
                    except Exception as exc:
                        conn.rollback();transition(conn,pid,'CYCLE2_PENDING','Retry after '+type(exc).__name__)
                        conn.execute('UPDATE programme_workflow SET last_error=? WHERE programme_id=?',(type(exc).__name__,pid));conn.commit();metrics['errors']+=1
            if stage in ('all','pool','cycle2'):
                for k,v in review_pool(conn).items(): metrics[k]+=v
            for key in r1.metrics: metrics[key]=r1.metrics[key]+r2.metrics[key]
            metrics['cycle1_searches']=r1.metrics['external_searches'];metrics['cycle2_searches']=r2.metrics['external_searches']
            metrics['page_diagnostics']=getattr(r1,'page_diagnostics',[])+getattr(r2,'page_diagnostics',[])
            metrics['current_pool_size']=len(current_pool(conn))
            metrics['stage_events']=[dict(r) for r in conn.execute('SELECT programme_id,from_state,to_state,reason FROM pipeline_events WHERE id>?',(start_event,))]
            metrics['pending_counts']={r['state']:r['n'] for r in conn.execute('SELECT state,COUNT(*) n FROM programme_workflow GROUP BY state')}
            out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
            metrics['reports']=write_cycle1_reports(conn,out,candidate.target.intake)
            (out/'Pipeline-Latest.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
            return metrics
        finally: conn.close()
