"""Prioritize existing pending candidates before further broad discovery."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from france_admission_agent.pipeline.backlog import pending_priority, research_backlog
from france_admission_agent.discovery.round_runner import get_default_search_client


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--max-candidates',type=int,default=5)
    parser.add_argument('--search-budget',type=int,default=6)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    db=ROOT/'data/france_research.db'
    if args.dry_run:
        result=pending_priority(db)[:args.max_candidates]
    else:
        client=get_default_search_client()
        if client is None:
            raise SystemExit('Search provider unavailable; no candidate state changed')
        result=research_backlog(db,ROOT/'config/candidate_profile.json',ROOT/'output',client,args.max_candidates,args.search_budget)
    print(json.dumps(result,indent=2,ensure_ascii=False))
