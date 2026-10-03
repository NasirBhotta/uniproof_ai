from france_admission_agent.profile import load_candidate
from france_admission_agent.schemas import ProgrammeCandidate
from france_admission_agent.transcript_matcher import match_transcript


def test_french_prerequisites_map_to_transcript():
    candidate = load_candidate("config/candidate_profile.json")
    programme = ProgrammeCandidate(
        programme_id="p1",
        university="Test",
        programme="Master Informatique",
        level="M1",
        city="Test",
        explicit_prerequisites=[
            "Algorithmique et structures de données",
            "Bases de données",
            "Systèmes d'exploitation et réseaux",
            "Algèbre linéaire et probabilités",
        ],
    )
    result = match_transcript(candidate, programme)
    assert result.coverage >= 0.75
