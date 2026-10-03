from france_admission_agent.schemas import CandidateProfile,ProgrammeCandidate,LanguageRequirement
from france_admission_agent.validators import validate_hard_eligibility

def candidate():
    return CandidateProfile.model_validate({"candidate_id":"t","nationality":"Pakistani","target":{"country":"France","level":"M1","intake":"2027","preferred_fields":[],"preferences":{}},"degree":{"title":"BSCS","institution":"COMSATS","duration_years":4,"credits":133,"cgpa":3.23,"scale":4,"completed":"2026-01"},"ielts":{"overall":6.5,"listening":7.5,"reading":6,"writing":6.5,"speaking":5.5},"french":{},"coursework":[]})

def test_speaking_6_is_hard_fail():
    p=ProgrammeCandidate(programme_id="x",university="U",programme="MSc CS",level="M1",city="C",application_route="Etudes en France",deadline="2027-01-01",language=LanguageRequirement(teaching_language=["English"],ielts_overall_min=6.5,ielts_speaking_min=6.0))
    r=validate_hard_eligibility(candidate(),p)
    assert r.hard_fail
    assert any("speaking" in x.lower() for x in r.reasons)
