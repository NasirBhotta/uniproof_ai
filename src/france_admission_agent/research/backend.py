from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from ..extraction.models import ProgrammeSeedBatch, ProgrammeVerification
from ..extraction.prompts import BASE_SYSTEM, discovery_prompt, skeptic_prompt, verification_prompt
from ..llm import StructuredLLM
from ..schemas import (
    ApplicationRouteInfo,
    CandidateProfile,
    CheckStatus,
    CycleStatus,
    EvidenceItem,
    EvidenceMatrixItem,
    LanguageRequirement,
    ProgrammeCandidate,
    ProgrammeEvidenceMatrix,
    ProgrammeEvaluation,
    SkepticReview,
    TranscriptMatchResultInfo,
)

from ..search.base import SearchClient
from ..transcript_matcher import match_transcript, match_transcript_structured
from .application_route import resolve_application_route
from .discovery import discover_programme_leads
from .evidence_caches import InstitutionEvidenceCache, ProgrammeEvidenceCache, SearchTracker
from .source_policy import hostname, is_trusted_national_source, source_is_eligible_for_final_claim
from .verification import collect_verification_sources, resolve_unresolved_field


def _stable_id(university: str, programme: str, track: str | None, level: str) -> str:
    raw = "|".join([university.strip().lower(), programme.strip().lower(), (track or "").strip().lower(), level])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


class EvidenceFirstResearchBackend:
    """Concrete research backend with provider-neutral LLM + web search.
    Implements regional discovery, two evidence caches, targeted resolution loop,
    and deduplication for search efficiency.
    """

    def __init__(
        self,
        *,
        llm: StructuredLLM,
        search: SearchClient,
        discovery_max_queries: int = 14,
        discovery_per_query: int = 8,
        verification_per_query: int = 4,
    ):
        self.llm = llm
        self.search = search
        self.discovery_max_queries = discovery_max_queries
        self.discovery_per_query = discovery_per_query
        self.verification_per_query = verification_per_query
        self._discovery_round = 0

        # Two dedicated evidence caches (Section 5)
        self.institution_cache = InstitutionEvidenceCache()
        self.programme_cache = ProgrammeEvidenceCache()
        self.tracker = SearchTracker()
        if hasattr(self.search, "tracker") and getattr(self.search, "tracker") is None:
            self.search.tracker = self.tracker

    def get_metrics(self, programme_count: int = 0) -> dict[str, Any]:
        used = self.tracker.external_searches_used
        hits = self.tracker.cache_hits
        prevented = self.tracker.duplicate_searches_prevented
        avg = round(used / max(1, programme_count), 2)
        return {
            "external_searches_used": used,
            "cache_hits": hits,
            "duplicate_searches_prevented": prevented,
            "average_searches_per_programme": avg,
        }

    def discover_programmes(
        self,
        candidate: CandidateProfile,
        limit: int,
        already_seen_ids: set[str],
    ) -> list[ProgrammeCandidate]:
        query_start = self._discovery_round * self.discovery_max_queries
        self._discovery_round += 1

        report = discover_programme_leads(
            candidate,
            self.search,
            per_query=self.discovery_per_query,
            query_start=query_start,
            max_queries=self.discovery_max_queries,
        )

        leads = [
            {
                "title": x.title,
                "url": x.url,
                "snippet": x.snippet,
                "query": x.query,
                "discovery_only": x.discovery_only,
            }
            for x in report.leads[: max(limit * 5, 50)]
        ]

        extracted = self.llm.generate_structured(
            system=BASE_SYSTEM,
            prompt=discovery_prompt(candidate, leads),
            response_model=ProgrammeSeedBatch,
        )

        programmes: list[ProgrammeCandidate] = []
        local_seen: set[str] = set()

        for seed in extracted.programmes:
            pid = _stable_id(seed.university, seed.programme, seed.track, seed.level)
            if pid in already_seen_ids or pid in local_seen:
                continue
            local_seen.add(pid)
            programmes.append(ProgrammeCandidate(
                programme_id=pid,
                university=seed.university,
                programme=seed.programme,
                track=seed.track,
                level=seed.level,
                city=seed.city or "Regional City",
                campus=seed.campus,
                public=seed.likely_public if seed.likely_public is not None else True,
                programme_url=seed.source_url,
            ))
            if len(programmes) >= limit:
                break

        return programmes

    def enrich_and_verify(
        self,
        candidate: CandidateProfile,
        programme: ProgrammeCandidate,
    ) -> ProgrammeCandidate:
        # 1. Collect official verification sources using caches
        bundle = collect_verification_sources(
            programme,
            candidate.target.intake,
            self.search,
            per_query=self.verification_per_query,
            institution_cache=self.institution_cache,
            programme_cache=self.programme_cache,
            tracker=self.tracker,
        )

        if not bundle.sources:
            # Fall back to application route resolution and return unverified
            programme.application_route_info = resolve_application_route(
                candidate, programme, self.institution_cache
            )
            return programme

        # 2. Single-pass deep extraction across all available fields
        verified = self.llm.generate_structured(
            system=BASE_SYSTEM,
            prompt=verification_prompt(candidate, programme, bundle.sources),
            response_model=ProgrammeVerification,
        )

        allowed_urls = {str(s.url) for s in bundle.sources}
        official_domains: set[str] = set()
        claimed_domain = (verified.official_university_domain or "").lower().removeprefix("www.").strip("./ ")

        if claimed_domain.endswith(".fr"):
            official_domains.add(claimed_domain)
        for s in bundle.sources:
            host = hostname(str(s.url))
            if host.endswith(".fr"):
                official_domains.add(host)

        evidence: list[EvidenceItem] = []
        for claim in verified.claims:
            if claim.source_url not in allowed_urls:
                continue
            if not source_is_eligible_for_final_claim(
                claim.source_url, official_university_domains=official_domains or None
            ):
                continue
            host = _domain(claim.source_url) or ""
            if "campusfrance.org" in host:
                source_type = "campus_france"
            elif host.endswith("gouv.fr"):
                source_type = "official_government"
            else:
                source_type = "official_university"
            evidence.append(EvidenceItem(
                claim=claim.claim_key,
                value=claim.claim_value,
                source_url=claim.source_url,
                source_type=source_type,
                evidence_text=claim.excerpt,
            ))

        claim_keys = {item.claim for item in evidence}

        def backed(key: str) -> bool:
            return key in claim_keys

        if backed("university") and verified.university:
            programme.university = verified.university
        if backed("programme") and verified.programme:
            programme.programme = verified.programme
        if backed("track") and verified.track:
            programme.track = verified.track
        if backed("level") and verified.level:
            programme.level = verified.level
        if backed("city") and verified.city:
            programme.city = verified.city
        if backed("public") and verified.public is not None:
            programme.public = verified.public
        if backed("programme_url") and verified.programme_url:
            programme.programme_url = verified.programme_url

        programme.application_route = verified.application_route if backed("application_route") else programme.application_route
        programme.deadline = verified.deadline if backed("deadline") else None
        programme.deadline_cycle = verified.deadline_cycle if backed("deadline_cycle") else None

        programme.language = LanguageRequirement(
            teaching_language=verified.teaching_languages if backed("teaching_language") else (verified.teaching_languages or []),
            ielts_accepted=verified.ielts_accepted if backed("ielts_accepted") else None,
            ielts_overall_min=verified.ielts_overall_min if backed("ielts_overall_min") else None,
            ielts_listening_min=verified.ielts_listening_min if backed("ielts_listening_min") else None,
            ielts_reading_min=verified.ielts_reading_min if backed("ielts_reading_min") else None,
            ielts_writing_min=verified.ielts_writing_min if backed("ielts_writing_min") else None,
            ielts_speaking_min=verified.ielts_speaking_min if backed("ielts_speaking_min") else None,
            toefl_min=verified.toefl_min if backed("toefl_min") else None,
            english_cefr_required=verified.english_cefr_required if backed("english_cefr_required") else None,
            french_level_required=verified.french_level_required if backed("french_level_required") else None,
            french_cefr_required=verified.french_cefr_required if backed("french_cefr_required") else None,
            english_medium_waiver_possible=verified.english_medium_waiver_possible if backed("english_medium_waiver_possible") else None,
        )

        programme.explicit_prerequisites = (
            verified.explicit_prerequisites if backed("explicit_prerequisites") else (verified.explicit_prerequisites or [])
        )
        programme.accepted_degree_fields = (
            verified.accepted_degree_fields if backed("accepted_degree_fields") else (verified.accepted_degree_fields or [])
        )
        programme.minimum_gpa_text = verified.minimum_gpa_text if backed("minimum_gpa_text") else None
        programme.excellence_wording = verified.excellence_wording if backed("excellence_wording") else None
        programme.capacity = verified.capacity if backed("capacity") else None
        programme.applicant_count = verified.applicant_count if backed("applicant_count") else None
        programme.admitted_count = verified.admitted_count if backed("admitted_count") else None
        programme.entrance_exam_required = verified.entrance_exam_required if backed("entrance_exam_required") else None
        programme.interview_required = verified.interview_required if backed("interview_required") else None
        programme.official_university_domain = claimed_domain or programme.official_university_domain
        programme.official_sources = evidence
        programme.unresolved_questions = verified.unresolved_questions

        # 3. Dedicated Application Route Resolver
        pages_content = {str(s.url): (s.raw_content or s.snippet) for s in bundle.sources}
        route_info = resolve_application_route(
            candidate, programme, self.institution_cache, cached_pages=pages_content
        )
        programme.application_route_info = route_info
        if route_info.platform and not programme.application_route:
            programme.application_route = route_info.platform

        # 4. Target Cycle Assessment
        if programme.deadline_cycle == candidate.target.intake:
            programme.cycle_status = CycleStatus.OPEN
        else:
            programme.cycle_status = CycleStatus.PENDING_PUBLICATION

        # 5. Targeted Resolution Loop for unresolved fields (Section 7)
        unresolved: list[str] = []
        if not programme.language.teaching_language:
            unresolved.append("teaching_language")
        if not programme.application_route:
            unresolved.append("application_route")
        if programme.capacity is None:
            unresolved.append("capacity")
        programme.unresolved_fields = unresolved

        # Perform targeted resolution (up to 2 targeted queries if essential fields missing)
        if unresolved:
            self._run_targeted_resolution(candidate, programme, unresolved[:2])

        # 6. Build Structured Programme Evidence Matrix (Section 16)
        programme.evidence_matrix = self._build_evidence_matrix(candidate, programme)

        return programme

    def _run_targeted_resolution(
        self,
        candidate: CandidateProfile,
        programme: ProgrammeCandidate,
        fields_to_resolve: list[str],
    ):
        """Runs targeted resolution for specific unresolved fields without broad searches."""
        for field in fields_to_resolve:
            # Check institution cache first
            if field == "application_route":
                inst = self.institution_cache.get(programme.university, programme.official_university_domain)
                if inst and inst.etudes_en_france_policy:
                    programme.application_route = "Études en France"
                    continue

            results = resolve_unresolved_field(
                candidate,
                programme,
                field,
                self.search,
                institution_cache=self.institution_cache,
                programme_cache=self.programme_cache,
                tracker=self.tracker,
            )
            if not results:
                continue

            for r in results:
                txt = (r.raw_content or r.snippet).lower()
                if field == "teaching_language":
                    if "anglais" in txt or "english" in txt:
                        if "english" not in programme.language.teaching_language:
                            programme.language.teaching_language.append("English")
                    elif "français" in txt or "francais" in txt:
                        if "French" not in programme.language.teaching_language:
                            programme.language.teaching_language.append("French")
                elif field == "application_route":
                    if "études en france" in txt or "campus france" in txt:
                        programme.application_route = "Études en France"
                elif field == "capacity":
                    import re
                    cap_match = re.search(r'capacité\s*(?:d\'accueil)?\s*:\s*(\d{2,3})', txt)
                    if cap_match:
                        programme.capacity = int(cap_match.group(1))

    def _build_evidence_matrix(
        self, candidate: CandidateProfile, programme: ProgrammeCandidate
    ) -> ProgrammeEvidenceMatrix:
        matrix = ProgrammeEvidenceMatrix()

        # Degree compatibility
        has_degree = bool(programme.accepted_degree_fields)
        matrix.degree_compatibility = EvidenceMatrixItem(
            status=CheckStatus.PASS if has_degree else CheckStatus.UNVERIFIED,
            evidence=", ".join(programme.accepted_degree_fields) if has_degree else "Degree requirements standard for M1 CS",
        )

        # M1 eligibility
        matrix.m1_eligibility = EvidenceMatrixItem(
            status=CheckStatus.PASS if programme.level == "M1" else CheckStatus.FAIL,
            evidence=f"Programme verified level: {programme.level}",
        )

        # Academic prerequisites & Transcript Match
        t_match = match_transcript_structured(candidate, programme)
        matrix.transcript_match = t_match
        matrix.academic_prerequisites = EvidenceMatrixItem(
            status=CheckStatus.PASS if programme.explicit_prerequisites else CheckStatus.UNVERIFIED,
            evidence=f"{len(t_match.matched_candidate_courses)} matched courses ({round(t_match.coverage * 100)}%)",
        )

        # Teaching language
        has_lang = bool(programme.language.teaching_language)
        matrix.teaching_language = EvidenceMatrixItem(
            status=CheckStatus.PASS if has_lang else CheckStatus.UNVERIFIED,
            evidence=", ".join(programme.language.teaching_language) if has_lang else "Language under review",
        )

        # English requirement
        matrix.english_requirement = EvidenceMatrixItem(
            status=CheckStatus.PASS if (programme.language.ielts_overall_min or programme.language.english_cefr_required) else CheckStatus.UNVERIFIED,
            evidence=f"IELTS min: {programme.language.ielts_overall_min or 'B2 CEFR'}",
        )

        # French requirement
        matrix.french_requirement = EvidenceMatrixItem(
            status=CheckStatus.PASS if not programme.language.french_level_required else CheckStatus.UNVERIFIED,
            evidence=f"French requirement: {programme.language.french_level_required or 'None stated for English track'}",
        )

        # Application route
        route = programme.application_route or (programme.application_route_info.platform if programme.application_route_info else None)
        matrix.application_route = EvidenceMatrixItem(
            status=CheckStatus.PASS if route else CheckStatus.UNVERIFIED,
            evidence=route or "Under Études en France review",
        )

        # 2027 cycle
        matrix.cycle_2027 = EvidenceMatrixItem(
            status=programme.cycle_status,
            evidence=f"Status: {programme.cycle_status.value} (Target {candidate.target.intake})",
        )

        # Capacity & Selectivity
        matrix.capacity = EvidenceMatrixItem(
            status="VERIFIED" if programme.capacity is not None else "UNVERIFIED",
            evidence=f"Capacity: {programme.capacity} seats" if programme.capacity else "Not published",
        )
        matrix.selectivity = EvidenceMatrixItem(
            status="VERIFIED" if programme.applicant_count else "UNVERIFIED",
            evidence=f"Applicants: {programme.applicant_count}, Admitted: {programme.admitted_count}" if programme.applicant_count else "Historical selectivity not published",
        )

        return matrix

    def transcript_coverage(self, candidate: CandidateProfile, programme: ProgrammeCandidate) -> float:
        return match_transcript(candidate, programme).coverage

    def skeptic_review(
        self,
        candidate: CandidateProfile,
        evaluation: ProgrammeEvaluation,
    ) -> SkepticReview:
        deterministic_questions: list[str] = []
        p = evaluation.programme
        if p.unresolved_questions:
            deterministic_questions.extend(p.unresolved_questions)
        if not p.application_route:
            deterministic_questions.append("Candidate-specific application route is not verified.")
        if not p.deadline:
            deterministic_questions.append("Target-cycle calendar is pending publication.")

        review = self.llm.generate_structured(
            system=BASE_SYSTEM,
            prompt=skeptic_prompt(candidate, evaluation),
            response_model=SkepticReview,
        )
        review.unresolved_questions = list(dict.fromkeys(review.unresolved_questions + deterministic_questions))
        return review
