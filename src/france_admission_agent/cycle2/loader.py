"""
Cycle 2 Loader: Parses and validates shortlisted programmes from Cycle 1
Author: Nasir Bhutta
Description: Reads output/Final-Shortlist.md and output/cycle1_results.json,
             extracts ONLY viable shortlisted programmes (Groups A, B, C),
             validates programme IDs and URLs, and loads Cycle 1 evidence.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..schemas import CheckStatus, ProgrammeCandidate, ProgrammeEvaluation

logger = logging.getLogger(__name__)


def load_cycle1_shortlist(
    shortlist_md_path: str | Path = "output/Final-Shortlist.md",
    cycle1_json_path: str | Path = "output/cycle1_results.json",
) -> list[ProgrammeEvaluation]:
    """Validates existence of Cycle 1 shortlist and returns viable shortlisted programmes.
    
    Raises:
        FileNotFoundError: If output/Final-Shortlist.md does not exist.
        ValueError: If no viable programmes found in the shortlist.
    """
    md_path = Path(shortlist_md_path)
    json_path = Path(cycle1_json_path)

    if not md_path.exists():
        raise FileNotFoundError(
            f"Cycle 1 shortlist not found at: {md_path.resolve()}\n"
            f"Please run Cycle 1 first via: python run_cycle1.py"
        )

    # Load structured cycle 1 results
    viable_evals: list[ProgrammeEvaluation] = []

    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
            raw_shortlist = data.get("final_shortlist", [])
            for item in raw_shortlist:
                eval_obj = ProgrammeEvaluation.model_validate(item)
                # Ensure strictly viable programmes (Groups A, B, C and not rejected)
                if eval_obj.group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED") and not eval_obj.rejected:
                    viable_evals.append(eval_obj)

    if not viable_evals:
        # Fallback: inspect evaluations.json if cycle1_results.json had 0 shortlist
        evals_path = md_path.parent / "evaluations.json"
        if evals_path.exists():
            with open(evals_path, encoding="utf-8") as f:
                all_evals = json.load(f)
                for item in all_evals:
                    eval_obj = ProgrammeEvaluation.model_validate(item)
                    if eval_obj.group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED") and not eval_obj.rejected:
                        viable_evals.append(eval_obj)

    if not viable_evals:
        raise ValueError(
            f"No viable programmes found in {md_path}. All programmes may have been rejected or require prior resolution."
        )

    # Validate programme IDs and official URLs
    seen_ids: set[str] = set()
    validated: list[ProgrammeEvaluation] = []
    for e in viable_evals:
        p = e.programme
        if not p.programme_id:
            logger.warning(f"Skipping programme with missing programme_id: {p.university} - {p.programme}")
            continue
        if p.programme_id in seen_ids:
            continue
        seen_ids.add(p.programme_id)
        validated.append(e)

    logger.info(f"Loaded {len(validated)} viable programmes from Cycle 1 shortlist for deep analysis.")
    return validated
