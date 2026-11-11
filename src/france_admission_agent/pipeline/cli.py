from __future__ import annotations
import argparse
import json
from .service import run_pending
from .reporting import final_selection
from .state import request_refresh, migrate, transition
from ..memory.database import get_connection


def main(stage):
    parser=argparse.ArgumentParser(description='Incremental pending-only research stages')
    parser.add_argument('--pending-only',action='store_true',help='Process pending work only (the default).')
    parser.add_argument('--db',default='data/france_research.db')
    parser.add_argument('--output-dir',default='output')
    parser.add_argument('--candidate',default='config/candidate_profile.json')
    parser.add_argument('--programme',metavar='PROGRAMME_ID',help='Research one pending Cycle 1 programme')
    parser.add_argument('--retry-review',metavar='PROGRAMME_ID',help='Retry a Cycle 1 record that needs more evidence')
    parser.add_argument('--refresh',metavar='PROGRAMME_ID')
    parser.add_argument('--fields',default='language',help='Comma-separated field groups for explicit refresh')
    parser.add_argument('--search-budget',type=int,default=6)
    args=parser.parse_args()
    if args.retry_review:
        conn=get_connection(args.db);migrate(conn,args.output_dir)
        transition(conn,args.retry_review,'CYCLE1_PENDING','Explicit retry of incomplete research');conn.commit();conn.close()
    if args.refresh:
        conn=get_connection(args.db);migrate(conn,args.output_dir)
        request_refresh(conn,args.refresh,args.fields.split(','),'Explicit user refresh');conn.close()
    if stage=='final': result=final_selection(args.db,args.output_dir)
    else:
        from ..discovery.round_runner import get_default_search_client
        result=run_pending(args.db,args.candidate,args.output_dir,search=get_default_search_client(),stage=stage,
                           cycle1_budget=args.search_budget,cycle2_budget=args.search_budget,programme_id=args.programme)
    print(json.dumps(result,indent=2,ensure_ascii=False))
