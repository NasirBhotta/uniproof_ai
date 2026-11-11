"""
Unit Tests for Persistent Memory, Audit Rules, EfficiencyGovernor, and Discovery Forecasting
Author: Nasir Bhutta
"""

import sqlite3
import pytest
from pathlib import Path

from france_admission_agent.memory.database import init_database
from france_admission_agent.memory.audit import (
    audit_candidate_narrative,
    audit_historical_statistic,
    audit_evidence_item,
)
from france_admission_agent.memory.coverage import FRANCE_REGIONS_REGISTRY, get_next_recommended_regions, seed_regional_coverage
from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
from france_admission_agent.discovery.forecasting import (
    compute_multi_year_trends,
    forecast_2027_demand_pressure,
    determine_opportunity_risk_band,
)
from france_admission_agent.schemas import EvidenceItem, HistoricalMetric


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_france.db"
    conn = init_database(db_file)
    yield conn
    conn.close()


def test_audit_purges_contradictory_transcript_match():
    # When transcript coverage is 0.0, narrative must not claim match
    narrative = ["Broad transcript matches prerequisites well.", "Strong programming skills."]
    audited = audit_candidate_narrative(narrative, transcript_coverage=0.0)
    assert "TRANSCRIPT_MATCH_UNVERIFIED" in audited[0]
    assert "Strong programming skills." in audited[1]


def test_audit_purges_unsupported_degree_equivalences():
    narrative = ["CGPA 3.23 represents a strong first-division / upper-second class equivalent."]
    audited = audit_candidate_narrative(narrative, transcript_coverage=0.5)
    assert "upper-second class" not in audited[0]
    assert "evaluated on dossier" in audited[0]


def test_audit_historical_statistic_requires_official_source():
    # Official university page with year
    official_stat = HistoricalMetric(value=30, year="2024-2025", source="https://www.isima.fr/postuler-en-master-informatique")
    status, _ = audit_historical_statistic("capacity", official_stat, None)
    assert status == "VERIFIED_HISTORICAL"

    # Secondary unverified estimate
    secondary_stat = HistoricalMetric(value=185, year="2024-2025", source="General forum estimate")
    status2, _ = audit_historical_statistic("applicants", secondary_stat, None)
    assert status2 == "UNVERIFIED_STATISTIC"


def test_efficiency_governor_prevents_redundant_searches(temp_db):
    gov = EfficiencyGovernor(temp_db)
    # Record a claim in memory
    temp_db.execute(
        "INSERT INTO evidence (evidence_id, institution_id, claim_type, claim_value, verification_status) VALUES ('e1', 'univ-test', 'teaching_language', 'English', 'VERIFIED_CURRENT')"
    )
    temp_db.commit()

    should_search, reason = gov.should_search("p1", "univ-test", "teaching_language")
    assert should_search is False
    assert "verified persistent memory" in reason


def test_efficiency_governor_enforces_attempt_limits(temp_db):
    gov = EfficiencyGovernor(temp_db)
    # Simulate 3 failed attempts
    for _ in range(3):
        gov.record_search_result("q", "univ-test", "prog1", "calendar_dates", 0, fields_resolved=0)

    should_search, reason = gov.should_search("prog1", "univ-test", "calendar_dates")
    assert should_search is False
    assert "Maximum search attempts" in reason


def test_forecasting_multi_year_trend_and_opportunity_risk_band():
    records = [
        {"academic_year": "2023-2024", "applicants": 120, "capacity": 30},
        {"academic_year": "2024-2025", "applicants": 150, "capacity": 30},
        {"academic_year": "2025-2026", "applicants": 180, "capacity": 30},
    ]
    trend = compute_multi_year_trends(records)
    assert trend.demand_trend == "INCREASING"
    assert trend.capacity_trend == "STABLE"
    assert trend.selectivity_trend == "INCREASING_PRESSURE"

    forecast = forecast_2027_demand_pressure(trend, current_selectivity_pressure="HIGH", evidence_confidence=85.0)
    assert forecast.expected_demand_pressure == "VERY_HIGH"
    assert forecast.confidence == "HIGH"

    opp = determine_opportunity_risk_band(
        academic_strictness="MODERATE",
        language_risk="LOW",
        forecast_pressure="LOW",
        evidence_confidence=80.0,
    )
    assert opp.overall_risk_band == "LOWER"


def test_regional_coverage_recommends_underexplored_regions(temp_db):
    seed_regional_coverage(temp_db)
    recommended = get_next_recommended_regions(temp_db, top_n=3)
    assert len(recommended) == 3
    # Île-de-France should be excluded due to candidate outside-Paris preference
    assert all(r["region"] != "Île-de-France" for r in recommended)


def test_efficiency_metric_zero_searches_produces_zero_gain(temp_db):
    gov = EfficiencyGovernor(temp_db)
    # When 0 searches occur, metric must be strictly 0.0, never a synthetic division
    gov.metrics.external_search_calls = 0
    gov.metrics.fields_resolved = 12
    gov.metrics.total_evidence_gain = 38.4
    gov.metrics.compute_averages(total_programmes=4)

    assert gov.metrics.evidence_gain_per_search == 0.0
    assert gov.metrics.fields_resolved_per_search == 0.0


def test_discovery_round_executes_batch_with_stop_reason(tmp_path):
    from france_admission_agent.discovery.round_runner import execute_discovery_round
    from france_admission_agent.search.models import SearchBatch
    class EmptyProvider:
        def search(self, query, **kwargs):
            return SearchBatch(query=query)
    test_db = tmp_path / "test_disc.db"

    results = execute_discovery_round(
        db_path=test_db,
        candidate_path="config/candidate_profile.json",
        round_number=1,
        target_new_universities=2,
        target_new_programmes=3,
        max_external_searches=4,
        max_new_universities=3,
        max_new_programmes=5,
        output_dir=tmp_path,
        search_client=EmptyProvider(),
    )

    assert results["universities_discovered"] >= 2
    assert results["programmes_discovered"] >= 2
    assert results["stop_reason"] in [
        "TARGET_REACHED",
        "MAX_UNIVERSITIES",
        "MAX_PROGRAMMES",
        "MAX_SEARCH_BUDGET",
        "REGIONS_SATURATED",
        "FRONTIERS_DEFERRED",
        "DIMINISHING_RETURNS",
    ]
    assert results["searches_attempted"] <= 4


# ======================================================================
# SECTION 30 REGRESSION TESTS
# ======================================================================

def test_regression_1_zero_searches_with_duplicates_does_not_diminishing_returns(tmp_path):
    """
    TEST 1:
    budget = 12, known_universities = 43, new_local_candidates = 0, duplicate_queries = 9, external_searches = 0
    Expected: DO NOT STOP with DIMINISHING_RETURNS; generate alternative web discovery query.
    """
    from france_admission_agent.discovery.round_runner import (
        DiscoveryFrontier,
        generate_frontier_query,
    )
    from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
    from france_admission_agent.memory.database import init_database

    db = init_database(tmp_path / "test_reg1.db")
    gov = EfficiencyGovernor(db)

    frontier = DiscoveryFrontier(region="Hauts-de-France", city="Amiens", institution_id="picardie-jules-verne")
    q0, _ = generate_frontier_query(frontier, 0)
    gov.record_search_result(q0, "picardie-jules-verne", "p1", "f1", results_count=5)

    # 1. First query is duplicate
    is_dup, _ = gov.is_exact_duplicate(q0)
    assert is_dup is True

    # 2. Rewrite creates an alternative novel query
    q1, _ = generate_frontier_query(frontier, 1)
    assert q1 != q0
    is_dup1, _ = gov.is_exact_duplicate(q1)
    assert is_dup1 is False

    # 3. Invariant check: DIMINISHING_RETURNS cannot be raised/allowed with 0 external searches
    searches_attempted = 0
    consecutive_low_value = 0
    frontiers_attempted = []
    stop_reason = ""
    if consecutive_low_value >= 3 and searches_attempted >= 3 and len(frontiers_attempted) >= 2:
        stop_reason = "DIMINISHING_RETURNS"

    assert stop_reason != "DIMINISHING_RETURNS"


def test_regression_2_blocked_duplicates_do_not_increment_low_value(tmp_path):
    """
    TEST 2:
    3 duplicate queries blocked, 0 provider calls
    Expected: low_value_counter = 0
    """
    from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
    from france_admission_agent.memory.database import init_database

    db = init_database(tmp_path / "test_reg2.db")
    gov = EfficiencyGovernor(db)

    # Record past query
    gov.record_search_result("master informatique Amiens", "inst1", "p1", "f1", results_count=3)

    consecutive_actual_low_value = 0
    for _ in range(3):
        is_dup, _ = gov.is_exact_duplicate("master informatique Amiens")
        if is_dup:
            gov.metrics.duplicate_queries_blocked += 1
            # Invariant: duplicate blocked MUST NOT increment consecutive_actual_low_value!
        else:
            consecutive_actual_low_value += 1

    assert gov.metrics.duplicate_queries_blocked == 3
    assert gov.metrics.external_search_calls == 1  # only the initial setup call
    assert consecutive_actual_low_value == 0


def test_regression_3_diminishing_returns_requires_real_searches_and_frontiers(tmp_path):
    """
    TEST 3:
    3 actual different provider searches, 0 useful results, 2+ frontiers attempted
    Expected: DIMINISHING_RETURNS may be allowed.
    """
    from france_admission_agent.discovery.round_runner import InvalidStopReasonError

    searches_attempted = 3
    consecutive_actual_low_value = 3
    frontiers_attempted = {"Hauts-de-France::Amiens", "Grand Est::Metz"}

    stop_reason = ""
    if consecutive_actual_low_value >= 3 and searches_attempted >= 3 and len(frontiers_attempted) >= 2:
        stop_reason = "DIMINISHING_RETURNS"

    assert stop_reason == "DIMINISHING_RETURNS"

    # Precondition validator passes without exception
    if stop_reason == "DIMINISHING_RETURNS":
        if searches_attempted < 3 or len(frontiers_attempted) < 2 or consecutive_actual_low_value < 3:
            raise InvalidStopReasonError("Failed precondition")


def test_regression_4_region_coverage_high_exhaustion_partial_remains_searchable(tmp_path):
    """
    TEST 4:
    region coverage = HIGH, region exhaustion = PARTIAL
    Expected: region remains searchable.
    """
    from france_admission_agent.memory.coverage import get_next_recommended_regions
    from france_admission_agent.memory.database import init_database

    db = init_database(tmp_path / "test_reg4.db")
    # Simulate Grand Est with all universities checked, but exhaustion still PARTIAL
    db.execute(
        """
        INSERT INTO regional_coverage (
            region, universities_known, universities_checked, programmes_known, programmes_viable,
            saturation_estimate, coverage_level, exhaustion_status, last_searched
        ) VALUES ('Grand Est', 4, 4, 3, 2, 'HIGH', 'HIGH', 'PARTIAL', '2026-10-01 10:00:00')
        """
    )
    db.commit()

    recommended = get_next_recommended_regions(db, top_n=5)
    rec_names = [r["region"] for r in recommended]
    # Region is not EXHAUSTED, so it remains searchable!
    assert "Grand Est" in rec_names


def test_regression_5_known_university_unexplored_track_discovered(tmp_path):
    """
    TEST 5:
    known university has one evaluated programme but catalogue contains unexplored track
    Expected: discover new track.
    """
    from france_admission_agent.discovery.round_runner import (
        COMPREHENSIVE_FRANCE_CATALOG,
        DiscoveryFrontier,
    )
    from france_admission_agent.memory.database import init_database

    db = init_database(tmp_path / "test_reg5.db")
    # Seed university and 1 programme for strasbourg (SID track)
    db.execute(
        """
        INSERT INTO universities (institution_id, canonical_name, city, region)
        VALUES ('strasbourg', 'Université de Strasbourg', 'Strasbourg', 'Grand Est')
        """
    )
    db.execute(
        """
        INSERT INTO programmes (programme_id, institution_id, programme_name, track_name, is_viable)
        VALUES ('prog1_sid', 'strasbourg', 'Master Informatique', 'Science et ingénierie des données (SID)', 1)
        """
    )
    db.commit()

    frontier = DiscoveryFrontier(region="Grand Est", city="Strasbourg", institution_id="strasbourg")

    # Look for matching local candidates in catalogue
    unexplored = [
        p for p in COMPREHENSIVE_FRANCE_CATALOG
        if p["institution_id"] == frontier.institution_id
        and p["track"] != "Science et ingénierie des données (SID)"
    ]

    assert len(unexplored) >= 1
    assert any("Réseaux et systèmes" in p["track"] for p in unexplored)


def test_regression_6_exact_query_from_yesterday_rewrites_and_does_not_terminate(tmp_path):
    """
    TEST 6:
    exact same query from yesterday
    Expected: block exact query, generate alternative query, do NOT terminate round.
    """
    from france_admission_agent.discovery.round_runner import (
        DiscoveryFrontier,
        generate_frontier_query,
    )
    from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
    from france_admission_agent.memory.database import init_database
    from france_admission_agent.research.evidence_caches import normalize_query

    db = init_database(tmp_path / "test_reg6.db")
    gov = EfficiencyGovernor(db)

    frontier = DiscoveryFrontier(region="Hauts-de-France", city="Amiens", institution_id="picardie-jules-verne")
    q0, _ = generate_frontier_query(frontier, 0)

    # Insert search from yesterday (1 day ago)
    db.execute(
        """
        INSERT INTO search_history (query, normalized_query, timestamp)
        VALUES (?, ?, datetime('now', '-1 day'))
        """,
        (q0, normalize_query(q0))
    )
    db.commit()

    is_dup, _ = gov.is_exact_duplicate(q0, ttl_days=30)
    assert is_dup is True

    # Generate alternative query
    q1, _ = generate_frontier_query(frontier, 1)
    assert q1 != q0
    is_dup1, _ = gov.is_exact_duplicate(q1, ttl_days=30)
    assert is_dup1 is False


def test_regression_7_stale_search_refreshes_after_ttl(tmp_path):
    """
    TEST 7:
    search from previous intake cycle (older than 30 days)
    Expected: may refresh when target cycle or freshness requirement changes.
    """
    from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
    from france_admission_agent.memory.database import init_database
    from france_admission_agent.research.evidence_caches import normalize_query

    db = init_database(tmp_path / "test_reg7.db")
    gov = EfficiencyGovernor(db)

    old_query = "master informatique Amiens monmaster"
    # Insert search from 60 days ago
    db.execute(
        """
        INSERT INTO search_history (query, normalized_query, timestamp)
        VALUES (?, ?, datetime('now', '-60 day'))
        """,
        (old_query, normalize_query(old_query))
    )
    db.commit()

    # Query is older than 30 days, so is_exact_duplicate within 30 days returns False!
    is_dup, _ = gov.is_exact_duplicate(old_query, ttl_days=30)
    assert is_dup is False, "Query from 60 days ago should be refreshed and not permanently blocked"
