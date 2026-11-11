"""
Unit Tests for Cycle 2 Competitiveness and Loading Architecture
Author: Nasir Bhutta
"""

import pytest
from pathlib import Path

from france_admission_agent.cycle2.loader import load_cycle1_shortlist
from france_admission_agent.cycle2.competitiveness import analyze_admission_competitiveness
from france_admission_agent.cycle2.reporting2 import generate_cycle2_report
from france_admission_agent.profile import load_candidate
from france_admission_agent.schemas import (
    CandidateProfile,
    CheckStatus,
    CycleStatus,
    HardEligibilityResult,
    LanguageRequirement,
    ProgrammeCandidate,
    ProgrammeEvaluation,
    ScoreBreakdown,
)


def test_cycle2_loader_extracts_viable_programmes():
    viable = load_cycle1_shortlist("output/Final-Shortlist.md", "output/cycle1_results.json")
    assert len(viable) > 0
    for e in viable:
        assert e.group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED")
        assert not e.rejected
        assert e.programme.programme_id is not None


def test_cycle2_derived_ratio_does_not_invent_fake_numbers():
    candidate = load_candidate("config/candidate_profile.json")
    prog = ProgrammeCandidate(
        programme_id="test_p1",
        university="Clermont Auvergne INP",
        programme="Master Informatique",
        track="International of Computer Science (ICS)",
        level="M1",
        city="Aubière",
        public=True,
    )
    eval_obj = ProgrammeEvaluation(
        programme=prog,
        eligibility=HardEligibilityResult(),
        score=ScoreBreakdown(profile_fit_score=80.0),
        group="B_CALENDAR_PENDING",
    )
    c2_eval = analyze_admission_competitiveness(candidate, eval_obj)
    s = c2_eval.selectivity

    assert s.capacity.value == 30
    assert s.historical_applicants.value == 185
    assert s.historical_admitted.value == 26
    # 26 / 185 = 14.1%
    assert "14.1%" in s.historical_admission_ratio.value
    assert "derived historical admission ratio" in s.historical_admission_ratio.metric_definition
    assert s.historical_admission_ratio.year == "2024-2025"


def test_cycle2_missing_stats_sets_unknown_without_fabrication():
    candidate = load_candidate("config/candidate_profile.json")
    prog = ProgrammeCandidate(
        programme_id="test_unknown",
        university="Université Inconnue",
        programme="Master Informatique",
        level="M1",
        city="Nowhere",
        public=True,
    )
    eval_obj = ProgrammeEvaluation(
        programme=prog,
        eligibility=HardEligibilityResult(),
        score=ScoreBreakdown(profile_fit_score=70.0),
        group="C_LANGUAGE_VERIFICATION_REQUIRED",
    )
    c2_eval = analyze_admission_competitiveness(candidate, eval_obj)
    s = c2_eval.selectivity

    assert "HISTORICAL_SELECTIVITY_DATA_NOT_FOUND" in s.unknowns
    assert s.historical_admission_ratio is None
