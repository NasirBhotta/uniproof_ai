from france_admission_agent.profile import load_candidate
from france_admission_agent.research.queries import build_discovery_queries


def test_query_plan_has_french_and_english_and_official_catalogues():
    candidate = load_candidate("config/candidate_profile.json")
    queries = build_discovery_queries(candidate)
    assert any(q.language == "fr" for q in queries)
    assert any(q.language == "en" for q in queries)
    assert any("monmaster.gouv.fr" in q.query for q in queries)
    assert any("campusfrance.org" in q.query for q in queries)
