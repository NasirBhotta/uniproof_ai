from typing import Any, TypedDict
from .schemas import CandidateProfile, ProgrammeCandidate, ProgrammeEvaluation

class ResearchState(TypedDict, total=False):
    candidate: CandidateProfile
    target_count: int
    discovery_batch_size: int
    max_discovery_rounds: int
    discovery_round: int
    programmes: list[ProgrammeCandidate]
    evaluations: list[ProgrammeEvaluation]
    rejected: list[ProgrammeEvaluation]
    final_shortlist: list[ProgrammeEvaluation]
    stop_reason: str
    metrics: dict[str, Any]
