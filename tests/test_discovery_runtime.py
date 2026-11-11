"""Exercise real orchestration, history and cache without network access."""
import os
import time
from pathlib import Path

import httpx
import pytest

from france_admission_agent.discovery import round_runner as runner
from france_admission_agent.governor.efficiency_governor import EfficiencyGovernor
from france_admission_agent.memory.database import init_database
from france_admission_agent.search.cache import CachedSearchClient
from france_admission_agent.search.models import SearchBatch, SearchResult
from france_admission_agent.search.tavily import TavilySearchClient


class Provider:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def search(self, query, **kwargs):
        self.calls.append(query)
        assert kwargs.get("include_raw_content") is False
        return SearchBatch(query=query, error=self.error)


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    db = tmp_path / "memory.db"
    conn = init_database(db)
    for i in range(43):
        conn.execute("INSERT INTO universities (institution_id, canonical_name) VALUES (?, ?)",
                     (f"known-{i}", f"Known University {i}"))
    conn.commit()
    monkeypatch.setattr(runner, "COMPREHENSIVE_FRANCE_CATALOG", [])
    monkeypatch.setattr(runner, "get_next_recommended_regions", lambda *a, **k: [{"region": "Grand Est"}])
    cities = runner.FRENCH_REGIONAL_CITIES["Grand Est"][:3]
    monkeypatch.setattr(runner, "FRENCH_REGIONAL_CITIES", {"Grand Est": cities})
    frontiers = [runner.DiscoveryFrontier(region="Grand Est", city=c["city"],
                 institution_id=c["institution_id"], university_name=c["university"],
                 domain=next(u["domain"] for u in runner.FRANCE_REGIONS_REGISTRY["Grand Est"]
                             if u["id"] == c["institution_id"])) for c in cities]
    def run(provider, **kwargs):
        return runner.execute_discovery_round(db_path=db, search_client=provider,
                    output_dir=tmp_path / "reports", **kwargs)
    yield conn, frontiers, run
    conn.close()


def remember(conn, frontier, steps):
    gov = EfficiencyGovernor(conn)
    for step in steps:
        query, purpose = runner.generate_frontier_query(frontier, step)
        gov.record_search_result(query, frontier.institution_id, "discovery", "programme_discovery",
                                 0, search_purpose=purpose, region=frontier.region, city=frontier.city)


def test_nine_duplicates_and_43_known_universities_still_search(scenario):
    conn, frontiers, run = scenario
    remember(conn, frontiers[0], range(6))
    remember(conn, frontiers[1], range(3))
    provider = Provider()
    result = run(provider)
    assert result["duplicate_queries_blocked"] == 9
    assert provider.calls[0] == runner.generate_frontier_query(frontiers[1], 3)[0]
    assert result["searches_attempted"] == 2
    assert result["remaining_budget"] == 10
    assert result["stop_reason"] != "DIMINISHING_RETURNS"
    assert result["universities_discovered"] > 0
    assert conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0] == 43


def test_three_duplicate_blocks_and_cache_hits_are_not_failed_searches(scenario, tmp_path):
    conn, frontiers, run = scenario
    provider = Provider()
    cache = CachedSearchClient(provider, tmp_path / "cache", ttl_days=30)
    for frontier in frontiers:
        remember(conn, frontier, [0])
        for step in range(1, 6):
            query, _ = runner.generate_frontier_query(frontier, step)
            cache.search(query, max_results=5, search_depth="basic", include_raw_content=False)
    provider.calls.clear()
    result = run(cache)
    assert provider.calls == []
    assert result["duplicate_queries_blocked"] == 3
    assert result["cache_hits"] == 15
    assert result["searches_attempted"] == result["provider_calls_successful"] == 0
    assert result["consecutive_actual_low_value"] == 0
    assert result["remaining_budget"] == 12
    assert result["stop_reason"] == "FRONTIERS_DEFERRED"


def test_three_real_empty_searches_allow_diminishing_returns(scenario):
    conn, frontiers, run = scenario
    provider = Provider()
    result = run(provider)
    assert len(provider.calls) == 3
    assert result["searches_attempted"] == result["provider_calls_successful"] == 3
    assert result["consecutive_actual_low_value"] == 3
    assert result["frontiers_attempted"] == 3
    assert result["remaining_budget"] == 9
    assert result["stop_reason"] == "DIMINISHING_RETURNS"
    saved = conn.execute("SELECT stop_reason, distinct_frontiers FROM research_runs").fetchone()
    assert tuple(saved) == ("DIMINISHING_RETURNS", 3)


def test_provider_failures_consume_budget_but_are_not_low_value_or_cached(scenario, tmp_path):
    conn, frontiers, run = scenario
    provider = Provider(error="HTTPStatusError (HTTP 429)")
    result = run(CachedSearchClient(provider, tmp_path / "cache"))
    assert result["searches_attempted"] == result["provider_failures"] == 3
    assert result["provider_calls_successful"] == result["consecutive_actual_low_value"] == 0
    assert result["stop_reason"] == "SEARCH_PROVIDER_ERROR"
    assert not list((tmp_path / "cache").glob("*.json"))
    assert conn.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 0


def test_missing_provider_is_not_saturation(scenario, monkeypatch):
    _, _, run = scenario
    monkeypatch.setattr(runner, "get_default_search_client", lambda: None)
    result = run(None)
    assert result["stop_reason"] == "SEARCH_PROVIDER_UNAVAILABLE"
    assert result["remaining_budget"] == 12


def test_history_and_disk_cache_expire_together(scenario, tmp_path):
    conn, frontiers, run = scenario
    provider = Provider()
    cache = CachedSearchClient(provider, tmp_path / "cache", ttl_days=30)
    for frontier in frontiers:
        remember(conn, frontier, [0])
        query, _ = runner.generate_frontier_query(frontier)
        cache.search(query, max_results=5, search_depth="basic", include_raw_content=False)
    conn.execute("UPDATE search_history SET timestamp=datetime('now', '-31 day')")
    conn.commit()
    for path in (tmp_path / "cache").glob("*.json"):
        old = time.time() - 31 * 86400
        os.utime(path, (old, old))
    provider.calls.clear()
    result = run(cache)
    assert len(provider.calls) == 3
    assert result["cache_hits"] == 0


def test_round_counters_reset_and_known_tracks_do_not_exhaust_cities(scenario):
    _, _, run = scenario
    first = run(Provider())
    provider = Provider()
    second = run(provider)
    assert second["round_number"] == first["round_number"] + 1
    assert second["searches_attempted"] == 3
    assert second["remaining_budget"] == 9
    assert second["duplicate_queries_blocked"] == 3
    assert second["queries_rewritten"] == 3


def test_planner_moves_past_recent_regions(tmp_path, monkeypatch):
    db = tmp_path / "memory.db"
    conn = init_database(db)
    runner.seed_regional_coverage(conn)
    ranked = runner.get_next_recommended_regions(conn, top_n=13)
    first = ranked[0]["region"]
    for c in runner.FRENCH_REGIONAL_CITIES[first]:
        domain = next(u["domain"] for u in runner.FRANCE_REGIONS_REGISTRY[first] if u["id"] == c["institution_id"])
        remember(conn, runner.DiscoveryFrontier(region=first, city=c["city"], domain=domain), range(6))
    monkeypatch.setattr(runner, "COMPREHENSIVE_FRANCE_CATALOG", [])
    result = runner.execute_discovery_round(db_path=db, search_client=Provider(), output_dir=tmp_path)
    assert first not in result["selected_regions"]
    assert len(result["selected_regions"]) == 3
    assert result["searches_attempted"] > 0
    conn.close()


def test_result_parser_uses_provider_snippet(scenario):
    conn, frontiers, _ = scenario
    item = SearchResult(title="Programme", url="https://www.unistra.fr/formation/example",
                        snippet="Master informatique parcours Cloud")
    found = runner.extract_candidates_from_search_results([item], frontiers[0], conn, set(), set())
    assert len(found) == 1
    assert found[0]["track"] == "Cloud"


def test_discovery_primary_query_targets_university_domain(scenario):
    _,frontiers,_=scenario
    q,purpose=runner.generate_frontier_query(frontiers[0])
    assert q.startswith('site:'+frontiers[0].domain)
    assert 'monmaster.gouv.fr' not in q


def test_tavily_preserves_real_http_error_type_without_secret(monkeypatch):
    def fail(self, url, **kwargs):
        request = httpx.Request("POST", url)
        response = httpx.Response(401, request=request)
        response.raise_for_status()
    monkeypatch.setattr(httpx.Client, "post", fail)
    result = TavilySearchClient(api_key="test-secret").search("test")
    assert result.error == "HTTPStatusError (HTTP 401)"
    assert "test-secret" not in result.model_dump_json()


def test_region_query_does_not_block_distinct_city_queries(scenario):
    conn, _, _ = scenario
    gov = EfficiencyGovernor(conn)
    gov.record_search_result("Master Informatique Hauts-de-France", "", "", "programme_discovery", 0)
    for query in ["Master Informatique Amiens", "Master G?nie Logiciel Lens", "Master Informatique Valenciennes"]:
        assert not gov.is_exact_duplicate(query)[0]


def test_discovery_rejects_aggregator_identity(scenario):
    conn,frontiers,_=scenario
    item=SearchResult(title='Master informatique parcours Cloud',url='https://www.educations.com/masters',snippet='Master informatique data')
    assert runner.extract_candidates_from_search_results([item],frontiers[0],conn,set(),set())==[]


def test_discovery_does_not_invent_data_track(scenario):
    conn,frontiers,_=scenario
    item=SearchResult(title='Master informatique',url='https://www.unistra.fr/master',snippet='Data and software research')
    found=runner.extract_candidates_from_search_results([item],frontiers[0],conn,set(),set())
    assert found==[]


def test_discovery_rejects_prose_as_track(scenario):
    conn,frontiers,_=scenario
    item=SearchResult(title='Master informatique',url='https://www.unistra.fr/master-informatique',
                      snippet='Master informatique parcours proposés aux étudiants à partir du semestre 3')
    assert runner.extract_candidates_from_search_results([item],frontiers[0],conn,set(),set())==[]


def test_discovery_rejects_m2_page_as_m1_lead(scenario):
    conn,frontiers,_=scenario
    item=SearchResult(title='Master informatique parcours Data Science',
                      url='https://www.unistra.fr/master-informatique/m2-data-science',snippet='Master informatique')
    assert runner.extract_candidates_from_search_results([item],frontiers[0],conn,set(),set())==[]
