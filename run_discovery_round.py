"""
Iterative Discovery Round Entrypoint: Bounded Knowledge Accumulation
Author: Nasir Bhutta
Description: Executes a single bounded iterative discovery round.
             Loads persistent SQLite memory, targets under-explored regions,
             evaluates new public university Master's programmes,
             updates research memory, and outputs research summaries.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add project root and src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from france_admission_agent.discovery.round_runner import execute_discovery_round


def main():
    import argparse
    parser = argparse.ArgumentParser(description="One bounded incremental discovery round")
    parser.add_argument("--discovery-only", action="store_true", help="Enqueue new delta without running downstream stages")
    args = parser.parse_args()
    print("=" * 70)
    print(" [*] STARTING ITERATIVE DISCOVERY ROUND (Bounded Regional Expansion)")
    print("=" * 70)

    db_path = PROJECT_ROOT / "data" / "france_research.db"
    candidate_path = PROJECT_ROOT / "config" / "candidate_profile.json"

    print(f"[+] Loading Persistent Local Research Memory: {db_path}")
    print("[+] Identifying under-explored regions and unresearched universities...")

    # Execute one single bounded discovery round
    results = execute_discovery_round(
        db_path=db_path,
        candidate_path=candidate_path,
        incremental=not args.discovery_only,
    )

    print("\n" + "=" * 70)
    print(f" DISCOVERY ROUND {results['round_number']} EXECUTION SUMMARY")
    print("=" * 70)
    print(f" Round Stop Reason: {results['stop_reason']}")
    print(f" Selected Priority Regions: {', '.join(results['selected_regions'])}")
    print(f" Discovery Frontiers Attempted: {results.get('frontiers_attempted', 0)}")
    print(f" External Search Calls Actually Executed: {results['searches_attempted']}")
    print(f" Provider Calls (Attempted/Successful): {results.get('provider_calls_attempted', results['searches_attempted'])}/{results.get('provider_calls_successful', results['searches_attempted'])}")
    print(f" Queries Blocked as Exact Duplicates: {results.get('duplicate_queries_blocked', 0)}")
    print(f" Queries Rewritten After Duplication: {results.get('queries_rewritten', 0)}")
    print(f" Universities Attempted: {results['universities_discovered']}")
    print(f" New Universities: {results.get('new_universities_count', 0)}")
    print(f" Known Universities With New Tracks: {results.get('known_universities_new_tracks', 0)}")
    print(f" New Programmes Found: {results['programmes_discovered']}")
    print(f" Candidates Deeply Verified: {results['candidates_deeply_verified']}")
    print(f" Remaining Search Budget: {results['remaining_budget']}")
    for key, value in results.get("pipeline", {}).items():
        if not isinstance(value, (dict, list)):
            print(f" Pipeline {key}: {value}")
    print(f" Summary Knowledge Base: {results['summary_report']}")
    print(f" Detailed Round Report: {results['round_report']}")
    print(f" Latest Round Report: {results.get('latest_report', 'output/Discovery-Latest.md')}")
    print("=" * 70)
    print(f"\n[+] Bounded round complete (Reason: {results['stop_reason']}). Memory updated. STOPPING.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
