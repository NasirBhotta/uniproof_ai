"""
Cycle 1 Entrypoint: Eligibility + Data Accuracy + Shortlisting
Author: Nasir Bhutta
Description: Executes Cycle 1 over the 19-programme pool, cleans evidence,
             verifies eligibility, validates scope isolation, computes evidence-based
             profile fit, and generates output/Final-Shortlist.md and output/cycle1_results.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.run_regression_test import rerun_regression


def run_legacy_snapshot():
    print("=" * 65)
    print(" [*] STARTING CYCLE 1: ELIGIBILITY + DATA ACCURACY + SHORTLISTING")
    print("=" * 65)
    rerun_regression()
    print("\n[+] Cycle 1 complete. Results saved to output/Final-Shortlist.md and output/cycle1_results.json")
    print("[!] STOPPING HERE FOR HUMAN REVIEW (Approval Boundary).")
    print("[!] Do NOT run Cycle 2 until Final-Shortlist.md has been reviewed and approved.")


if __name__ == "__main__":
    from france_admission_agent.pipeline.cli import main
    main("cycle1")
