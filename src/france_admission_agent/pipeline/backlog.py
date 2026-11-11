"""Spend one Cycle 1 search budget on one credible discovery lead at a time."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse, unquote
import re

from ..memory.database import get_connection
from ..schemas import ProgrammeCandidate
from .research import official, parse_claims
from .service import run_pending
from .state import pipeline_lock, transition


def identity_problem(p):
    track=(p.track or '').strip()
    url=str(p.programme_url or '')
    path=urlparse(url).path.casefold()
    decoded=unquote(unquote(path))
    if not official(p,url) or not url.startswith('https://'):
        return 'No secure official programme URL'
    if any(x in path for x in ('/licence-', '/bachelor-', '/m2-', '/video')):
        return 'Source page is not an M1 programme page'
    if ('licence' in decoded and 'master' not in decoded) or re.search(r'20(?:1\d|2[0-3])',decoded):
        return 'Source page is a licence or outdated catalogue'
    if not track or track.casefold()=='unspecified track':
        return 'Track identity unspecified'
    if '\n' in track or len(track)>75 or track.casefold().startswith('m2 '):
        return 'Track label is malformed or M2-only'
    if track.casefold() in ('types','type','suivant','suivants') or (' et ' in track.casefold() and 'en formation' in track.casefold()):
        return 'Several tracks or prose were combined into one label'
    fragments=('proposés','disponibles','suivants','de toutes les',"s'organise",'parmi deux',
               'ouverts ','et la p',' met en ','type ','responsable','clairement identifiés',
               'du master ','en master','à partir du semestre')
    if any(word in track.casefold() for word in fragments):
        return 'Search prose was mistaken for a track name'
    return None


def quarantine_discovery_noise(db_path='data/france_research.db',dry_run=False):
    """Preserve noisy leads in review rather than repeatedly searching them."""
    with pipeline_lock(db_path):
        conn=get_connection(db_path)
        try:
            bad=[]
            for row in conn.execute("SELECT * FROM programme_workflow WHERE state='CYCLE1_PENDING'").fetchall():
                p=ProgrammeCandidate.model_validate_json(row['candidate_json'])
                problem=identity_problem(p)
                if not problem:
                    continue
                bad.append(dict(programme_id=row['programme_id'],track=p.track,reason=problem))
                if not dry_run:
                    transition(conn,row['programme_id'],'CYCLE1_PROCESSING','Discovery identity audit')
                    transition(conn,row['programme_id'],'CYCLE1_REVIEW_REQUIRED',problem)
            if not dry_run:
                conn.commit()
            return bad
        finally:
            conn.close()


def pending_priority(db_path):
    conn = get_connection(db_path)
    try:
        leads = []
        for row in conn.execute("SELECT * FROM programme_workflow WHERE state='CYCLE1_PENDING'"):
            p = ProgrammeCandidate.model_validate_json(row['candidate_json'])
            url = str(p.programme_url or '')
            path = urlparse(url).path.casefold()
            if identity_problem(p):
                continue
            track=(p.track or '').strip()
            sources = len([e for e in p.official_sources if e.source_url and official(p, str(e.source_url))])
            has_master = int(('master' in path or 'm1' in path) and ('parcours-' in path or 'm1-' in path))
            english_cue = int(any(word in (p.programme+' '+track).casefold() for word in ('international', 'english', 'mosig', 'ics')))
            page=conn.execute('SELECT extracted_text FROM source_documents WHERE url=?',(url,)).fetchone()
            language='UNKNOWN'
            if page and has_master:
                claims=parse_claims('language',page['extracted_text'])
                language=claims.get('teaching_language','UNKNOWN')
            # A verified programme-page instruction language beats a suggestive
            # name such as "International"; French leads remain reviewable.
            language_rank=2 if language=='English' else (0 if language=='French' else 1)
            leads.append((language_rank,sources,has_master,english_cue,row['discovered_round'] or 0,
                          row['programme_id'],p.university,track,url,language))
        leads.sort(key=lambda x:(-x[0],-x[1],-x[2],-x[3],x[4],x[5]))
        return [dict(programme_id=x[5],university=x[6],track=x[7],url=x[8],
                     prior_sources=x[1],teaching_language_hint=x[9]) for x in leads]
    finally:
        conn.close()


def research_backlog(db_path='data/france_research.db',candidate_path='config/candidate_profile.json',
                     output_dir='output',search=None,max_candidates=5,search_budget=6):
    if max_candidates < 1 or search_budget < 1:
        raise ValueError('Backlog limits must be positive')
    results=[]
    for lead in pending_priority(db_path)[:max_candidates]:
        metrics=run_pending(db_path,candidate_path,output_dir,search=search,stage='cycle1',
                            programme_id=lead['programme_id'],cycle1_limit=1,cycle1_budget=search_budget,
                            promotion_limit=1)
        conn=get_connection(db_path)
        try:
            row=conn.execute('SELECT state,cycle1_status,cycle1_comparison_json FROM programme_workflow WHERE programme_id=?',(lead['programme_id'],)).fetchone()
            results.append(dict(lead=lead,state=row['state'],cycle1_status=row['cycle1_status'],
                                comparison=json.loads(row['cycle1_comparison_json']) if row['cycle1_comparison_json'] else None,
                                searches=metrics['cycle1_searches']))
        finally:
            conn.close()
    if results:
        run_pending(db_path,candidate_path,output_dir,search=search,stage='cycle2',
                    cycle2_limit=max_candidates,cycle2_budget=search_budget)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'Targeted-Backlog-Latest.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    return results
