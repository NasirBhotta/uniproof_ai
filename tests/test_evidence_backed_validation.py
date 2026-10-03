from france_admission_agent.profile import load_candidate
from france_admission_agent.schemas import EvidenceItem, LanguageRequirement, ProgrammeCandidate
from france_admission_agent.validators import is_final_ready, validate_hard_eligibility


def _e(claim):
    return EvidenceItem(
        claim=claim,
        value="x",
        source_url="https://www.univ-test.fr/master",
        source_type="official_university",
    )


def test_complete_core_evidence_can_be_final_ready():
    candidate = load_candidate("config/candidate_profile.json")
    p = ProgrammeCandidate(
        programme_id="p",
        university="Université Test",
        programme="Master Informatique",
        level="M1",
        city="Limoges",
        public=True,
        accepted_degree_fields=["Licence Informatique / Bachelor Computer Science"],
        application_route="Etudes en France",
        deadline="2027-02-15",
        deadline_cycle="2027",
        language=LanguageRequirement(teaching_language=["English"]),
        explicit_prerequisites=["Algorithms", "Databases"],
        official_sources=[
            _e("accepted_degree_fields"),
            _e("teaching_language"),
            _e("application_route"),
            _e("deadline"),
        ],
    )
    r = validate_hard_eligibility(candidate, p)
    assert not r.hard_fail
    assert is_final_ready(r, []) is True


def test_missing_route_is_not_final_ready():
    candidate = load_candidate("config/candidate_profile.json")
    p = ProgrammeCandidate(
        programme_id="p",
        university="Université Test",
        programme="Master Informatique",
        level="M1",
        city="Limoges",
        accepted_degree_fields=["Informatique"],
        deadline="2027-02-15",
        deadline_cycle="2027",
        language=LanguageRequirement(teaching_language=["English"]),
        official_sources=[_e("accepted_degree_fields"), _e("teaching_language"), _e("deadline")],
    )
    r = validate_hard_eligibility(candidate, p)
    assert r.hard_fail is False
    assert is_final_ready(r, []) is False
