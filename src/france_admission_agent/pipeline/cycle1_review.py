"""Compare saved Cycle 1 research before admitting any challenger to Cycle 2."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse
from ..schemas import ProgrammeEvaluation, CheckStatus
from ..reporting import build_markdown_report
from .pool import vector, OpportunityVector, dominates, compare
from .research import official, scoped


def cycle1_outcome(e):
    if e.rejected or e.eligibility.hard_fail:
        return 'REJECTED'
    p=e.programme
    claims={ev.claim for ev in p.official_sources if ev.source_url and ev.evidence_text and scoped(p,str(ev.source_url),ev.evidence_text)}
    if (not p.programme_url or not official(p,str(p.programme_url)) or p.scope_mismatch_flags
        or e.eligibility.degree_field!=CheckStatus.PASS or e.eligibility.level!=CheckStatus.PASS
        or 'accepted_degree_fields' not in claims or not claims.intersection({'level','programme_structure'})):
        return 'REVIEW_REQUIRED'
    return 'PASSED'


def rank_cycle1(conn):
    entries=[]
    for row in conn.execute('SELECT * FROM programme_workflow WHERE cycle1_json IS NOT NULL'):
        e=ProgrammeEvaluation.model_validate_json(row['cycle1_json'])
        v=OpportunityVector.model_validate_json(row['cycle1_vector_json']) if row['cycle1_vector_json'] else vector(conn,e)
        eligible=cycle1_outcome(e)=='PASSED' and not row['needs_refresh'] and not row['superseded_by'] and row['cycle1_status'] not in ('PENDING','PROCESSING','REVIEW_REQUIRED')
        entries.append(dict(programme_id=row['programme_id'],university=e.programme.university,track=e.programme.track,
            status=row['cycle1_status'],discovered_round=row['discovered_round'],eligible_for_comparison=eligible,
            profile_fit=e.score.profile_fit_score,evidence_confidence=e.score.evidence_confidence_score,
            group=e.group,unknowns=v.unknowns,rank=None,pareto_tier=None,vector=v.model_dump(),evaluation=e.model_dump(mode='json')))
    remaining=[x for x in entries if x['eligible_for_comparison']]
    rank=1;tier=1
    while remaining:
        front=[x for x in remaining if not any(dominates(OpportunityVector(**y['vector']),OpportunityVector(**x['vector'])) for y in remaining if y is not x)]
        # Evidence gates and Pareto tier precede scores; scores break ties only.
        front.sort(key=lambda x:(-x['evidence_confidence'],-x['profile_fit'],x['programme_id']))
        for x in front:
            x['rank']=rank;x['pareto_tier']=tier;rank+=1
        remaining=[x for x in remaining if x not in front];tier+=1
    entries.sort(key=lambda x:(x['rank'] is None,x['rank'] or 0,x['programme_id']))
    return entries


def audit_saved_scope(conn):
    """Keep saved Cycle 1 rankings honest after source-scope rules tighten."""
    changed=0
    for row in conn.execute('SELECT * FROM programme_workflow WHERE cycle1_json IS NOT NULL').fetchall():
        e=ProgrammeEvaluation.model_validate_json(row['cycle1_json'])
        current=cycle1_outcome(e)
        if row['cycle1_status']=='PASSED' and current!='PASSED':
            v=vector(conn,e).model_dump_json()
            conn.execute('UPDATE programme_workflow SET cycle1_vector_json=?,vector_json=CASE WHEN cycle2_json IS NULL THEN ? ELSE vector_json END WHERE programme_id=?',
                         (v,v,row['programme_id']))
            conn.execute('UPDATE programme_workflow SET cycle1_status=? WHERE programme_id=?',(current,row['programme_id']))
            conn.execute('INSERT INTO pipeline_events(programme_id,from_state,to_state,reason) VALUES (?,?,?,?)',
                         (row['programme_id'],row['state'],row['state'],'Cycle 1 scope audit: '+current))
            changed+=1
    conn.commit()
    return changed


def dedupe_specific_urls(conn):
    """Supersede duplicate IDs for the same official track page, preserving rows."""
    groups={}
    for row in conn.execute('''SELECT w.programme_id,w.state,w.cycle1_status,w.cycle2_json,w.cycle1_json,w.superseded_by,
                               p.institution_id,p.official_url FROM programme_workflow w
                               JOIN programmes p USING(programme_id)'''):
        url=str(row['official_url'] or '').split('?',1)[0].rstrip('/').casefold()
        if 'parcours-' not in urlparse(url).path:
            continue
        groups.setdefault((row['institution_id'],url),[]).append(row)
    changed=0
    for rows in groups.values():
        if len(rows)<2:
            continue
        def priority(row):
            return (row['state'] in ('FINAL_CANDIDATE','POOL_RETAINED'),
                    row['cycle1_status']=='PASSED',bool(row['cycle2_json']),bool(row['cycle1_json']),
                    -int(row['programme_id'],16))
        canonical=max(rows,key=priority)['programme_id']
        for row in rows:
            if row['programme_id']==canonical:
                if row['superseded_by']:
                    conn.execute('UPDATE programme_workflow SET superseded_by=NULL,supersession_reason=NULL WHERE programme_id=?',
                                 (canonical,))
                continue
            if row['superseded_by']==canonical:
                continue
            conn.execute('UPDATE programme_workflow SET superseded_by=?,supersession_reason=? WHERE programme_id=?',
                         (canonical,'Same official programme-specific track URL',row['programme_id']))
            changed+=1
    conn.commit()
    return changed


def promotion_decisions(conn):
    ranked=rank_cycle1(conn)
    by_id={x['programme_id']:x for x in ranked}
    pending=conn.execute("SELECT * FROM programme_workflow WHERE state IN ('CYCLE1_PASSED','PROMOTION_REVIEW')").fetchall()
    pending=sorted(pending,key=lambda r:(by_id.get(r['programme_id'],{}).get('rank') or 10**9,r['programme_id']))
    decisions=[]
    for row in pending:
        entry=by_id[row['programme_id']]
        # Compare against all saved eligible Cycle 1 candidates, including earlier
        # rounds and candidates already researched in Cycle 2, without rerunning them.
        peers=[(x['programme_id'],OpportunityVector(**x['vector'])) for x in ranked if x['eligible_for_comparison'] and x['programme_id']!=row['programme_id']]
        if not entry['eligible_for_comparison']:
            decision,target,reason='INSUFFICIENT_EVIDENCE',None,'Cycle 1 needs official identity, degree and M1 evidence'
        else:
            challenger=OpportunityVector(**entry['vector'])
            decision,target,reason=compare(challenger,peers)
            # Choose one deterministic leader when equally strong new leads tie.
            if decision=='NOT_IMPROVE_POOL' and entry['rank']==1 and not any(dominates(v,challenger) for _,v in peers):
                decision,reason='COMPLEMENT_EXISTING','Highest ranked representative of equivalent saved Cycle 1 candidates'
        details=dict(decision=decision,compared_against=[pid for pid,_ in peers],compared_count=len(peers),
                     compared_stage='SAVED_CYCLE1',rank=entry['rank'],pareto_tier=entry['pareto_tier'],
                     target=target,reason=reason,profile_fit=entry['profile_fit'],evidence_confidence=entry['evidence_confidence'])
        conn.execute('UPDATE programme_workflow SET cycle1_comparison_json=? WHERE programme_id=?',(json.dumps(details),row['programme_id']))
        decisions.append((row,details))
    conn.commit()
    return decisions


def write_cycle1_reports(conn,output_dir,intake):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    ranked=rank_cycle1(conn)
    evaluations=[ProgrammeEvaluation.model_validate(x['evaluation']) for x in ranked]
    survivors=[e for e in evaluations if not e.rejected]
    rejected=[e for e in evaluations if e.rejected]
    shortlist=[e for e in survivors if cycle1_outcome(e)=='PASSED' and e.group in ('A_FULLY_VERIFIED','B_CALENDAR_PENDING','C_LANGUAGE_VERIFICATION_REQUIRED')]
    # Reuse the original detailed Cycle 1 card renderer without replacing archived reports.
    text=build_markdown_report(final_shortlist=shortlist,evaluations=survivors,rejected=rejected,
          stop_reason='Incremental Cycle 1: saved research reused; incomplete evidence stays in review.',target_intake=intake)
    lines=['# Saved Cycle 1 Comparison and Ranking','',
           'Ranks cover evidence-eligible candidates only. Pareto tiers precede score tie-breaks; this is not an admission probability.','',
           '| Rank | Tier | Programme ID | University / Track | State | Fit | Evidence |','|---|---|---|---|---|---:|---:|']
    for x in ranked:
        lines.append(f"| {x['rank'] or 'REVIEW'} | {x['pareto_tier'] or '-'} | {x['programme_id']} | {x['university']} / {x['track'] or 'Unspecified'} | {x['status']} | {x['profile_fit']:.1f} | {x['evidence_confidence']:.1f} |")
    for row in conn.execute('SELECT programme_id,cycle1_comparison_json FROM programme_workflow WHERE cycle1_comparison_json IS NOT NULL'):
        d=json.loads(row['cycle1_comparison_json'])
        lines+=['',f"- {row['programme_id']}: {d['decision']}; compared with {d['compared_count']} saved Cycle 1 candidates. {d['reason']}"]
    (out/'Cycle1-Ranking.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'Cycle1-Detailed-Latest.md').write_text(text,encoding='utf-8')
    (out/'Cycle1-Ranking.json').write_text(json.dumps(ranked,indent=2,ensure_ascii=False),encoding='utf-8')
    return {'cycle1_details':str(out/'Cycle1-Detailed-Latest.md'),'cycle1_ranking':str(out/'Cycle1-Ranking.md')}


def repair_previous_cycle1(conn):
    """Reopen premature v1 passes once, preserving research and event history."""
    from .state import VERSION, now
    count=0
    for row in conn.execute("SELECT * FROM programme_workflow WHERE cycle1_version='incremental-1' AND cycle1_json IS NOT NULL AND cycle2_processed_at IS NULL").fetchall():
        e=ProgrammeEvaluation.model_validate_json(row['cycle1_json'])
        if cycle1_outcome(e)=='REVIEW_REQUIRED':
            p=e.programme
            state='CYCLE1_PENDING' if p.programme_url and official(p,str(p.programme_url)) else 'CYCLE1_REVIEW_REQUIRED'
            conn.execute("UPDATE programme_workflow SET state=?,cycle1_status=?,cycle1_version=?,pool_status='NOT_REVIEWED',cycle1_processed_at=NULL WHERE programme_id=?",(state,state[len('CYCLE1_'):],VERSION,row['programme_id']))
            conn.execute('INSERT INTO pipeline_events(programme_id,from_state,to_state,reason) VALUES (?,?,?,?)',(row['programme_id'],row['state'],state,'Repair premature v1 pass; preserved research; official identity and eligibility need verification'))
            count+=1
    conn.commit()
    return count
