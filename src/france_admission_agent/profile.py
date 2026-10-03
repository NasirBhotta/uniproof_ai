import json
from pathlib import Path
from .schemas import CandidateProfile

def load_candidate(path):
    return CandidateProfile.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
