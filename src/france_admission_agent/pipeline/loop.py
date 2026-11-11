"""Bounded orchestration of the existing incremental research stages."""
from __future__ import annotations

import json
from pathlib import Path

from ..discovery.round_runner import execute_discovery_round, get_default_search_client
from ..memory.database import get_connection
from .pool import current_pool
from .reporting import final_selection
from .service import run_pending
from .backlog import pending_priority, research_backlog, quarantine_discovery_noise


def verified_count(db_path):
    conn = get_connection(db_path)
    try:
        return sum(vector.credible for _, vector in current_pool(conn))
    finally:
        conn.close()


def run_research_loop(
    db_path='data/france_research.db', candidate_path='config/candidate_profile.json',
    output_dir='output', max_rounds=6, searches_per_round=12,
    search_client=None, stop_after_empty_rounds=2,
):
    if max_rounds < 1 or searches_per_round < 1 or stop_after_empty_rounds < 1:
        raise ValueError('Loop limits must be positive integers')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = search_client if search_client is not None else get_default_search_client()
    rounds = []
    reason = None
    empty_streak = 0

    # Clear previously promoted work before choosing between backlog and discovery.
    if client is not None:
        quarantine_discovery_noise(db_path)
        run_pending(db_path, candidate_path, output_dir, search=client, stage='cycle2')
    if verified_count(db_path) >= 7:
        reason = 'SEVEN_VERIFIED'
    elif client is None:
        reason = 'SEARCH_PROVIDER_UNAVAILABLE'

    while reason is None and len(rounds) < max_rounds:
        backlog = pending_priority(db_path)
        if backlog:
            batch = research_backlog(db_path,candidate_path,output_dir,client,
                                     max_candidates=min(3,len(backlog)),search_budget=max(1,searches_per_round//3))
            entry = {
                'stage': 'TARGETED_BACKLOG', 'round_number': None,
                'stop_reason': 'BATCH_COMPLETE', 'new_programmes': 0,
                'cycle1_processed': sum(x['state'] != 'CYCLE1_PENDING' for x in batch),
                'cycle2_processed': 0,
                'pool_additions': 0, 'pool_replacements': 0,
                'provider_calls_successful': sum(x['searches'] for x in batch),
                'verified_pool_size': verified_count(db_path),
            }
        else:
            result = execute_discovery_round(
                db_path=db_path, candidate_path=candidate_path, output_dir=output_dir,
                max_external_searches=searches_per_round, search_client=client,
                incremental=True,
            )
            pipeline = result.get('pipeline') or {}
            entry = {
                'stage': 'DISCOVERY', 'round_number': result['round_number'],
                'stop_reason': result['stop_reason'],
                'new_programmes': result.get('programmes_discovered', 0),
                'cycle1_processed': pipeline.get('cycle1_processed', 0),
                'cycle2_processed': pipeline.get('cycle2_processed', 0),
                'pool_additions': pipeline.get('pool_additions', 0),
                'pool_replacements': pipeline.get('pool_replacements', 0),
                'provider_calls_successful': result.get('provider_calls_successful', 0),
                'verified_pool_size': verified_count(db_path),
            }
        rounds.append(entry)
        if entry['verified_pool_size'] >= 7:
            reason = 'SEVEN_VERIFIED'
        elif entry['stop_reason'] in ('SEARCH_PROVIDER_UNAVAILABLE', 'SEARCH_PROVIDER_ERROR'):
            reason = entry['stop_reason']
        else:
            useful = any(entry[k] for k in ('new_programmes', 'cycle1_processed', 'cycle2_processed', 'pool_additions', 'pool_replacements'))
            empty_streak = 0 if useful else empty_streak + 1
            if empty_streak >= stop_after_empty_rounds:
                reason = 'REPEATED_ZERO_YIELD'

    reason = reason or 'MAX_ROUNDS'
    selection = final_selection(db_path, output_dir)
    summary = {
        'stop_reason': reason,
        'rounds_completed': len(rounds),
        'verified_pool_size': verified_count(db_path),
        'finalists': selection['finalists'],
        'rounds': rounds,
        'final_report': selection['report'],
    }
    (out / 'Research-Loop-Latest.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    return summary
