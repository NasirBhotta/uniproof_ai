from __future__ import annotations

from typing import Protocol

from .schemas import CandidateProfile, ProgrammeCandidate, ProgrammeEvaluation, SkepticReview


class ResearchBackend(Protocol):
    def discover_programmes(
        self,
        candidate: CandidateProfile,
        limit: int,
        already_seen_ids: set[str],
    ) -> list[ProgrammeCandidate]:
        ...

    def enrich_and_verify(
        self,
        candidate: CandidateProfile,
        programme: ProgrammeCandidate,
    ) -> ProgrammeCandidate:
        ...

    def transcript_coverage(
        self,
        candidate: CandidateProfile,
        programme: ProgrammeCandidate,
    ) -> float:
        ...

    def skeptic_review(
        self,
        candidate: CandidateProfile,
        evaluation: ProgrammeEvaluation,
    ) -> SkepticReview:
        ...


class NotConfiguredBackend:
    def _fail(self):
        raise RuntimeError(
            "Research backend not configured. Inject EvidenceFirstResearchBackend "
            "with your StructuredLLM (for example Gemini) and SearchClient."
        )

    def discover_programmes(self, *a, **k):
        self._fail()

    def enrich_and_verify(self, *a, **k):
        self._fail()

    def transcript_coverage(self, *a, **k):
        self._fail()

    def skeptic_review(self, *a, **k):
        self._fail()
