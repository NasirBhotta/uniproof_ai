"""Run multiple bounded discovery-to-final-selection rounds on saved memory."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from france_admission_agent.pipeline.loop import run_research_loop


def main():
    parser = argparse.ArgumentParser(description='Bounded incremental research loop')
    parser.add_argument('--max-rounds', type=int, default=6)
    parser.add_argument('--searches-per-round', type=int, default=12)
    parser.add_argument('--stop-after-empty-rounds', type=int, default=2)
    args = parser.parse_args()
    result = run_research_loop(
        db_path=ROOT / 'data' / 'france_research.db',
        candidate_path=ROOT / 'config' / 'candidate_profile.json',
        output_dir=ROOT / 'output',
        max_rounds=args.max_rounds,
        searches_per_round=args.searches_per_round,
        stop_after_empty_rounds=args.stop_after_empty_rounds,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
