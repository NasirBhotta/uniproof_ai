import pytest
pytest.importorskip("langgraph")

from france_admission_agent.graph import build_graph
from france_admission_agent.profile import load_candidate
from france_admission_agent.schemas import (
    EvidenceItem,
    LanguageRequirement,
    ProgrammeCandidate,
    SkepticReview,
)


def _e(claim):
    return EvidenceItem(
        claim=claim,
        value="x",
        source_url="https://www.univ-test.fr/master",
        source_type="official_university",
    )


def make_programme(i: int, *, speaking_min=None, french=None):
    return ProgrammeCandidate(
        programme_id=f"p{i}",
        university=f"Université Régionale {i}",
        programme="Master Informatique",
        level="M1",
        city=f"Regional City {i}",
        public=True,
        accepted_degree_fields=["Informatique"],
        application_route="Etudes en France",
        deadline="2027-02-15",
        deadline_cycle="2027",
        language=LanguageRequirement(
            teaching_language=["English"],
            ielts_speaking_min=speaking_min,
            french_level_required=french,
        ),
        explicit_prerequisites=["Algorithms", "Databases", "Operating Systems"],
        official_sources=[
            _e("accepted_degree_fields"),
            _e("teaching_language"),
            _e("application_route"),
            _e("deadline"),
        ],
    )


class FakeBackend:
    def __init__(self):
        self.items = [make_programme(i) for i in range(1, 8)] + [
            make_programme(8, speaking_min=6.0),
            make_programme(9, french="B2"),
        ]

    def discover_programmes(self, candidate, limit, already_seen_ids):
        return [p for p in self.items if p.programme_id not in already_seen_ids][:limit]

    def enrich_and_verify(self, candidate, programme):
        return programme

    def transcript_coverage(self, candidate, programme):
        return 1.0

    def skeptic_review(self, candidate, evaluation):
        return SkepticReview()


def test_graph_returns_7_and_rejects_language_failures():
    candidate = load_candidate("config/candidate_profile.json")
    graph = build_graph(FakeBackend())
    result = graph.invoke({
        "candidate": candidate,
        "target_count": 7,
        "discovery_batch_size": 20,
        "max_discovery_rounds": 2,
        "discovery_round": 0,
        "programmes": [],
        "evaluations": [],
        "rejected": [],
    })
    assert len(result["final_shortlist"]) == 7
    rejected_ids = {e.programme.programme_id for e in result["rejected"]}
    assert "p8" in rejected_ids
    assert "p9" in rejected_ids
