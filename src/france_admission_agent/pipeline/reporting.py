from __future__ import annotations
import json
from pathlib import Path
from ..memory.database import get_connection
from ..memory.coverage import FRANCE_REGIONS_REGISTRY
from ..schemas import ProgrammeEvaluation
from .pool import current_pool, vector
from .state import transition, migrate, pipeline_lock


def convergence(conn):
    streak=0
    for row in conn.execute('SELECT * FROM pipeline_rounds ORDER BY round_number DESC'):
        if row['pool_improvements'] or row['successful_searches']<3 or row['distinct_frontiers']<2: break
        streak+=1
    explored=conn.execute('SELECT COUNT(DISTINCT region) FROM discovery_frontiers WHERE attempts>0').fetchone()[0]
    pool=current_pool(conn)
    ready=sum(v.credible for _,v in pool)>=7 and explored>=9 and streak>=3
    return dict(consecutive_rounds_without_pool_improvement=streak,regions_explored=explored,
                final_selection_ready=ready)


def finish_round(db_path,result,output_dir):
    conn=get_connection(db_path)
    try:
        metrics=result['pipeline'];improvements=metrics['pool_additions']+metrics['pool_replacements']
        metrics['new_programmes_per_round']=result['programmes_discovered']
        metrics['promoted_programmes_per_round']=metrics['promoted_to_cycle2']
        metrics['pool_replacements_per_round']=metrics['pool_replacements']
        legacy={r['programme_id'] for r in conn.execute('SELECT programme_id FROM programme_workflow WHERE discovered_round IS NULL')}
        metrics['legacy_records_reviewed_without_cycle1_rerun']=len({e['programme_id'] for e in metrics['stage_events'] if e['programme_id'] in legacy})
        metrics['legacy_first_cycle2_processed']=sum(e['programme_id'] in legacy and e['to_state']=='CYCLE2_PROCESSING' for e in metrics['stage_events'])
        metrics['new_delta_promoted_to_cycle2']=sum(e['programme_id'] not in legacy and e['to_state']=='CYCLE2_PENDING' for e in metrics['stage_events'])
        if result['stop_reason']=='DIMINISHING_RETURNS': result['stop_reason']='BOUNDED_LOW_YIELD'
        conn.execute('''INSERT OR REPLACE INTO pipeline_rounds(round_number,metrics_json,actual_searches,successful_searches,distinct_frontiers,pool_improvements,stop_reason)
            VALUES (?,?,?,?,?,?,?)''',(result['round_number'],json.dumps(metrics),result['searches_attempted'],result['provider_calls_successful'],result['frontiers_attempted'],improvements,result['stop_reason']))
        conn.commit();status=convergence(conn);result.update(status)
        if status['final_selection_ready']: result['stop_reason']='DIMINISHING_RETURNS'
        conn.execute('UPDATE pipeline_rounds SET stop_reason=? WHERE round_number=?',(result['stop_reason'],result['round_number']))
        conn.execute('UPDATE research_runs SET stop_reason=? WHERE run_id=?',(result['stop_reason'],f"discovery_round_{result['round_number']}"));conn.commit()
        lines=['','## Incremental pipeline','', '| Metric | Value |','|---|---:|']
        for k,v in metrics.items():
            if not isinstance(v,(dict,list)): lines.append(f'| {k} | {v} |')
        for k,v in status.items(): lines.append(f'| {k} | {v} |')
        lines+=['',f"Pipeline stop reason: `{result['stop_reason']}`. No next discovery round was started.",'',
                '### Exact stage transitions','', '| Programme ID | From | To | Reason |','|---|---|---|---|']
        for ev in metrics['stage_events']:
            lines.append('| '+' | '.join(str(ev[k] or '').replace('|','/') for k in ('programme_id','from_state','to_state','reason'))+' |')
        path=Path(result['round_report']);text=path.read_text(encoding='utf-8').split('\n## Incremental pipeline\n',1)[0]
        import re
        text=re.sub(r'(\*\*Round Stop Reason:\*\* `)[^`]+',lambda m:m[1]+result['stop_reason'],text)
        text=re.sub(r'(\*\*Deeply Verified Programmes:\*\* )\d+',lambda m:m[1]+str(metrics['cycle2_verified']),text)
        text+='\n'.join(lines)+'\n';path.write_text(text,encoding='utf-8');Path(result['latest_report']).write_text(text,encoding='utf-8')
        (Path(output_dir)/f"Pipeline-Round-{result['round_number']:03d}.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        (Path(output_dir)/'Pipeline-Latest.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
        return result
    finally: conn.close()


def final_selection(db_path='data/france_research.db',output_dir='output',intake='2027'):
    """Read verified pool only; no search provider or discovery dependency."""
    with pipeline_lock(db_path):
        conn=get_connection(db_path)
        try:
            migrate(conn,output_dir,intake)
            from .service import schedule_changes
            schedule_changes(conn,intake)
            eligible=[];manual=[]
            for row in conn.execute("SELECT w.*,u.canonical_name,u.city FROM programme_workflow w JOIN universities u USING(institution_id) WHERE w.pool_status='POOL_RETAINED' AND w.superseded_by IS NULL"):
                payload=json.loads(row['cycle2_json'])['cycle1_evaluation'] if row['cycle2_json'] else json.loads(row['cycle1_json'])
                e=ProgrammeEvaluation.model_validate(payload);v=vector(conn,e)
                if row['needs_refresh'] or not v.credible:
                    manual.append(f"{row['canonical_name']} / {e.programme.track}: critical evidence needs targeted refresh.");continue
                eligible.append((row,e,v))
            # Diversity first, then evidence dimensions; score is never the comparator.
            eligible.sort(key=lambda x:(-(x[2].evidence_confidence or 0),-(x[2].language_compatibility or 0),x[0]['programme_id']))
            chosen=[];regions=set()
            for item in eligible:
                if item[2].region not in regions and len(chosen)<7:
                    chosen.append(item);regions.add(item[2].region)
            for item in eligible:
                if len(chosen)>=7: break
                if item not in chosen: chosen.append(item)
            chosen_ids={item[0]['programme_id'] for item in chosen}
            for row in conn.execute("SELECT programme_id FROM programme_workflow WHERE state='FINAL_CANDIDATE'").fetchall():
                if row['programme_id'] not in chosen_ids: transition(conn,row['programme_id'],'POOL_RETAINED','No longer in current final comparison set')
            review_count=conn.execute("SELECT COUNT(*) FROM programme_workflow WHERE cycle1_status='REVIEW_REQUIRED' AND superseded_by IS NULL").fetchone()[0]
            lines=['# Final Selection','',f'Target intake: {intake}. Verified comparison set: {len(chosen)} of up to 7.',
                'No applications submitted. These are options, not admission probabilities.','']
            if len(chosen)<7: lines+=['Fewer than seven programmes satisfy the current critical-evidence and freshness gates. Continue bounded research or resolve the listed checks.','']
            for row,e,v in chosen:
                p=e.programme;transition(conn,p.programme_id,'FINAL_CANDIDATE','Human comparison set; no automatic application')
                def label(value): return 'UNKNOWN' if value is None else {0:'LOW',1:'LIMITED',2:'MODERATE',3:'STRONG'}[value]
                lines += [f'## {p.university} — {p.programme} / {p.track or "General"}','',
                    f'- City: {p.city}',f'- Academic fit: {label(v.academic_fit)}',
                    f'- Language compatibility: {e.eligibility.language.value}',f'- Candidate position: {label(v.candidate_position)}',
                    f'- Historical pressure: '+({3:'LOW',2:'MODERATE',1:'HIGH'}.get(v.historical_opportunity,'UNKNOWN')),
                    '- Forecast pressure: UNKNOWN (no validated forecast)',f'- Evidence confidence: {label(v.evidence_confidence)}',
                    f'- Application complexity: '+('Verified route; administrative checks remain' if v.application_simplicity else 'UNKNOWN'),
                    f'- {intake} readiness: {e.cycle_readiness.value}',
                    '- Main strengths: verified eligibility dimensions and transcript alignment.',
                    '- Main risks: '+(', '.join(v.unknowns) or 'No additional identified hard incompatibility; admission remains competitive.'),
                    '- Remaining manual checks: '+('; '.join(p.unresolved_questions) or 'Confirm current deadlines, tuition and official requirements before applying.'),'']
            lines+=['## Pending critical checks','']
            if review_count:
                lines.append(f'{review_count} Cycle 1 candidates require programme-specific official evidence or manual review.')
            lines+=manual or ([] if review_count else ['No additional retained candidates awaiting refresh.'])
            conn.commit();out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
            path=out/'Final-Selection.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            return dict(finalists=len(chosen),report=str(path),**convergence(conn))
        finally: conn.close()
