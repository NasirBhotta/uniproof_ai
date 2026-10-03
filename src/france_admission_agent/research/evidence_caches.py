from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def normalize_query(query: str) -> str:
    """Normalizes search query to prevent redundant duplicate queries."""
    q = query.lower().strip()
    q = re.sub(r'["\']', '', q)
    q = re.sub(r'\s+', ' ', q)
    return q


def normalize_university_key(name: str) -> str:
    n = name.lower()
    n = re.sub(r'^(université|universite|univ|ecole|institut)\s+(de\s+|d\'\s+|)', '', n)
    n = re.sub(r'[^a-z0-9]', '-', n)
    n = re.sub(r'-+', '-', n).strip('-')
    return n or "unknown-univ"


def normalize_programme_key(name: str) -> str:
    n = name.lower()
    n = re.sub(r'^(master|msc|mention)\s+(en\s+|de\s+|d\'\s+|)', '', n)
    n = re.sub(r'[^a-z0-9]', '-', n)
    n = re.sub(r'-+', '-', n).strip('-')
    return n or "general-cs"


def normalize_track_key(track: str | None) -> str:
    if not track:
        return "core"
    t = track.lower()
    t = re.sub(r'^(parcours|track|option|spécialité|specialite)\s+', '', t)
    t = re.sub(r'[^a-z0-9]', '-', t)
    t = re.sub(r'-+', '-', t).strip('-')
    return t or "core"


def build_programme_cache_key(university: str, programme: str, track: str | None) -> str:
    u = normalize_university_key(university)
    p = normalize_programme_key(programme)
    t = normalize_track_key(track)
    return f"{u}::{p}::{t}"


@dataclass
class CachedEvidenceSource:
    url: str
    content: str
    source_university: str
    source_programme: str
    source_track: str | None = None
    retrieved_at: str | None = None


@dataclass
class InstitutionEvidence:
    institution_name: str
    official_domains: set[str] = field(default_factory=set)
    international_admissions_url: str | None = None
    etudes_en_france_policy: str | None = None
    campus_france_instructions: str | None = None
    general_english_requirements: dict[str, Any] = field(default_factory=dict)
    general_french_requirements: dict[str, Any] = field(default_factory=dict)
    academic_calendar_summary: str | None = None
    general_m1_policy: str | None = None
    country_specific_rules: dict[str, str] = field(default_factory=dict)
    cached_pages: dict[str, CachedEvidenceSource] = field(default_factory=dict)


@dataclass
class ProgrammeEvidence:
    cache_key: str
    university: str
    programme: str
    track: str | None = None
    level: str = "M1"
    explicit_prerequisites: list[str] = field(default_factory=list)
    accepted_degree_fields: list[str] = field(default_factory=list)
    teaching_language: list[str] = field(default_factory=list)
    teaching_language_status: str = "LANGUAGE_UNVERIFIED"
    ielts_requirements: dict[str, Any] = field(default_factory=dict)
    french_requirements: str | None = None
    m1_entry_verified: bool | None = None
    specialization_starts_in: str = "UNVERIFIED"
    capacity: int | None = None
    deadline: str | None = None
    deadline_cycle: str | None = None
    application_route: str | None = None
    cached_pages: dict[str, CachedEvidenceSource] = field(default_factory=dict)


class EvidenceScopeMismatchError(ValueError):
    """Raised when evidence from one university/programme is attempted to be merged into another."""
    pass


class InstitutionEvidenceCache:
    """Stores reusable university-level facts with strict university domain isolation."""

    def __init__(self):
        self._institutions: dict[str, InstitutionEvidence] = {}
        self._domain_to_inst: dict[str, str] = {}
        self.scope_mismatches_prevented: int = 0

    def get(self, institution_name: str, domain: str | None = None) -> InstitutionEvidence | None:
        key = normalize_university_key(institution_name)
        if key in self._institutions:
            return self._institutions[key]
        if domain and domain in self._domain_to_inst:
            inst_key = self._domain_to_inst[domain]
            # Safety: Ensure the key actually matches the requested institution
            if inst_key == key:
                return self._institutions.get(inst_key)
        return None

    def register_official_domain(self, institution_name: str, domain: str):
        key = normalize_university_key(institution_name)
        # Prevent generic or third party portals from being claimed by a single university
        excluded_domains = {
            "monmaster.gouv.fr",
            "campusfrance.org",
            "enseignementsup-recherche.gouv.fr",
            "service-public.fr",
            "etudiant.gouv.fr",
            "optionmetier.fr",
            "wakatepe.fr",
        }
        clean_d = domain.lower().removeprefix("www.").strip()
        if clean_d in excluded_domains or any(clean_d.endswith("." + excl) for excl in excluded_domains):
            return

        # Ensure domain token has a connection to the university name
        univ_tokens = key.split("-")
        domain_tokens = clean_d.split(".")[0].split("-")
        # Accept if at least one meaningful token matches or contains univ-
        if any(tok in clean_d for tok in univ_tokens if len(tok) > 3) or "univ" in clean_d or "inp" in clean_d:
            self._domain_to_inst[clean_d] = key
            inst = self.get_or_create(institution_name)
            inst.official_domains.add(clean_d)

    def get_or_create(self, institution_name: str, domain: str | None = None) -> InstitutionEvidence:
        existing = self.get(institution_name, domain)
        if existing:
            if domain:
                self.register_official_domain(institution_name, domain)
            return existing

        key = normalize_university_key(institution_name)
        inst = InstitutionEvidence(institution_name=institution_name)
        self._institutions[key] = inst
        if domain:
            self.register_official_domain(institution_name, domain)
        return inst

    def update_policy(
        self,
        institution_name: str,
        *,
        domain: str | None = None,
        eef_policy: str | None = None,
        english_req: dict | None = None,
        french_req: dict | None = None,
        calendar: str | None = None,
        m1_policy: str | None = None,
        page_url: str | None = None,
        page_content: str | None = None,
        source_university: str | None = None,
    ):
        # Scope validation: source university must match institution_name
        if source_university:
            src_key = normalize_university_key(source_university)
            target_key = normalize_university_key(institution_name)
            if src_key != target_key:
                self.scope_mismatches_prevented += 1
                logger.warning(
                    f"EVIDENCE_SCOPE_MISMATCH: Prevented merging institution policy from '{source_university}' into '{institution_name}'"
                )
                return

        inst = self.get_or_create(institution_name, domain)
        if eef_policy:
            inst.etudes_en_france_policy = eef_policy
        if english_req:
            inst.general_english_requirements.update(english_req)
        if french_req:
            inst.general_french_requirements.update(french_req)
        if calendar:
            inst.academic_calendar_summary = calendar
        if m1_policy:
            inst.general_m1_policy = m1_policy
        if page_url and page_content:
            inst.cached_pages[page_url] = CachedEvidenceSource(
                url=page_url,
                content=page_content,
                source_university=institution_name,
                source_programme="institution-wide",
            )


class ProgrammeEvidenceCache:
    """Stores programme-specific prerequisites and cached pages with strict scope validation."""

    def __init__(self):
        self._programmes: dict[str, ProgrammeEvidence] = {}
        self.scope_mismatches_prevented: int = 0

    def get(self, university_or_id: str, programme: str | None = None, track: str | None = None) -> ProgrammeEvidence | None:
        if programme is None:
            return self.get_by_id(university_or_id)
        key = build_programme_cache_key(university_or_id, programme, track)
        return self._programmes.get(key)

    def get_by_id(self, cache_key: str) -> ProgrammeEvidence | None:
        return self._programmes.get(cache_key)


    def get_or_create(
        self,
        university: str,
        programme: str,
        track: str | None = None,
        level: str = "M1",
    ) -> ProgrammeEvidence:
        key = build_programme_cache_key(university, programme, track)
        if key not in self._programmes:
            self._programmes[key] = ProgrammeEvidence(
                cache_key=key,
                university=university,
                programme=programme,
                track=track,
                level=level,
            )
        return self._programmes[key]

    def add_page_evidence(
        self,
        target_university: str,
        target_programme: str,
        target_track: str | None,
        page_url: str,
        page_content: str,
        *,
        source_university: str,
        source_programme: str,
        source_track: str | None = None,
    ) -> bool:
        """Validates scope before adding page evidence. Rejects cross-university contamination."""
        t_u = normalize_university_key(target_university)
        s_u = normalize_university_key(source_university)
        if t_u != s_u:
            self.scope_mismatches_prevented += 1
            logger.warning(
                f"EVIDENCE_SCOPE_MISMATCH: Cross-university contamination blocked. Source: '{source_university}' -> Target: '{target_university}'"
            )
            return False

        t_p = normalize_programme_key(target_programme)
        s_p = normalize_programme_key(source_programme)
        if t_p != s_p:
            # Allow only if source is general CS and target is specialized CS within the SAME university
            if not ("informatique" in t_p and "informatique" in s_p):
                self.scope_mismatches_prevented += 1
                return False

        prog = self.get_or_create(target_university, target_programme, target_track)
        prog.cached_pages[page_url] = CachedEvidenceSource(
            url=page_url,
            content=page_content,
            source_university=source_university,
            source_programme=source_programme,
            source_track=source_track,
        )
        return True

    def add_evidence_page(
        self,
        target_university: str,
        target_programme: str,
        target_track: str | None = None,
        page_url: str = "",
        page_content: str = "",
        *,
        source_university: str | None = None,
        source_programme: str | None = None,
        source_track: str | None = None,
        **kwargs,
    ) -> bool:
        """Alias for add_page_evidence with flexible keyword arguments."""
        return self.add_page_evidence(
            target_university=target_university,
            target_programme=target_programme,
            target_track=target_track,
            page_url=page_url or kwargs.get("url", ""),
            page_content=page_content or kwargs.get("content", ""),
            source_university=source_university or target_university,
            source_programme=source_programme or target_programme,
            source_track=source_track or target_track,
        )



@dataclass
class SearchTracker:
    """Tracks search efficiency metrics."""
    external_searches_used: int = 0
    cache_hits: int = 0
    duplicate_searches_prevented: int = 0
    page_fetches: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seen_queries: set[str] = field(default_factory=set)

    def record_search(self, query: str, is_cache_hit: bool, is_duplicate: bool = False):
        norm = normalize_query(query)
        if is_duplicate:
            self.duplicate_searches_prevented += 1
            return
        if norm in self.seen_queries and not is_cache_hit:
            self.duplicate_searches_prevented += 1
            return
        self.seen_queries.add(norm)
        if is_cache_hit:
            self.cache_hits += 1
        else:
            self.external_searches_used += 1

    def record_llm(self, input_chars: int = 0, output_chars: int = 0):
        self.llm_calls += 1
        # Approx 4 chars per token
        self.input_tokens += max(1, input_chars // 4)
        self.output_tokens += max(1, output_chars // 4)
