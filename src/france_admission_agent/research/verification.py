from __future__ import annotations

from dataclasses import dataclass, field

from ..research.evidence_caches import InstitutionEvidenceCache, ProgrammeEvidenceCache, SearchTracker
from ..research.queries import build_targeted_field_query, build_verification_queries
from ..research.source_policy import hostname, is_potential_verification_source
from ..schemas import CandidateProfile, ProgrammeCandidate
from ..search.base import SearchClient
from ..search.models import SearchResult


@dataclass
class VerificationBundle:
    programme_id: str
    sources: list[SearchResult] = field(default_factory=list)
    queries_run: int = 0


def collect_verification_sources(
    programme: ProgrammeCandidate,
    year: str,
    search: SearchClient,
    *,
    per_query: int = 4,
    institution_cache: InstitutionEvidenceCache | None = None,
    programme_cache: ProgrammeEvidenceCache | None = None,
    tracker: SearchTracker | None = None,
) -> VerificationBundle:
    bundle = VerificationBundle(programme_id=programme.programme_id)
    seen_urls: set[str] = set()

    # 1. Reuse existing evidence and cached pages from ProgrammeEvidenceCache
    if programme_cache:
        prog_ev = programme_cache.get(programme.university, programme.programme, programme.track) or programme_cache.get_by_id(programme.programme_id)
        if prog_ev and prog_ev.cached_pages:
            for url, val in prog_ev.cached_pages.items():
                content = val.content if hasattr(val, "content") else str(val or "")
                if url not in seen_urls and is_potential_verification_source(url):
                    seen_urls.add(url)
                    bundle.sources.append(SearchResult(
                        title=f"{programme.university} — {programme.programme}",
                        url=url,
                        snippet=content[:400],
                        raw_content=content,
                    ))

    # 2. Reuse institution-level cached pages
    if institution_cache:
        inst_ev = institution_cache.get(programme.university, programme.official_university_domain)
        if inst_ev and inst_ev.cached_pages:
            for url, val in inst_ev.cached_pages.items():
                content = val.content if hasattr(val, "content") else str(val or "")
                if url not in seen_urls and is_potential_verification_source(url):
                    seen_urls.add(url)
                    bundle.sources.append(SearchResult(
                        title=f"{programme.university} — Admissions Internationales",
                        url=url,
                        snippet=content[:400],
                        raw_content=content,
                    ))

    # If we already have sufficient official sources cached, avoid redundant web search!
    if len(bundle.sources) >= 3:
        return bundle

    # 3. Retrieve official sources
    queries = build_verification_queries(
        programme.university,
        programme.programme,
        year,
        official_domain=programme.official_university_domain,
    )

    for rq in queries:
        batch = search.search(rq.query, max_results=per_query, include_raw_content=True)
        bundle.queries_run += 1
        if tracker:
            tracker.record_search(rq.query, is_cache_hit=False)

        for result in batch.results:
            url = str(result.url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if is_potential_verification_source(url):
                bundle.sources.append(result)
                host = hostname(url)
                if institution_cache and host.endswith(".fr"):
                    institution_cache.update_policy(
                        programme.university,
                        domain=host,
                        page_url=url,
                        page_content=result.raw_content or result.snippet,
                    )
                if programme_cache and result.raw_content:
                    programme_cache.add_evidence_page(
                        target_university=programme.university,
                        target_programme=programme.programme,
                        target_track=programme.track,
                        source_university=programme.university,
                        source_programme=programme.programme,
                        source_track=programme.track,
                        page_url=url,
                        page_content=result.raw_content,
                    )

    return bundle


def resolve_unresolved_field(
    candidate: CandidateProfile,
    programme: ProgrammeCandidate,
    field_name: str,
    search: SearchClient,
    *,
    institution_cache: InstitutionEvidenceCache | None = None,
    programme_cache: ProgrammeEvidenceCache | None = None,
    tracker: SearchTracker | None = None,
) -> list[SearchResult]:
    """Targeted search for a single missing field to avoid broad expensive searches."""
    rq = build_targeted_field_query(
        programme.university,
        programme.programme,
        field_name,
        official_domain=programme.official_university_domain,
    )

    batch = search.search(rq.query, max_results=3, include_raw_content=True)
    if tracker:
        tracker.record_search(rq.query, is_cache_hit=False)

    results: list[SearchResult] = []
    for r in batch.results:
        url = str(r.url)
        if is_potential_verification_source(url):
            results.append(r)
            if programme_cache and r.raw_content:
                programme_cache.add_evidence_page(
                    target_university=programme.university,
                    target_programme=programme.programme,
                    target_track=programme.track,
                    source_university=programme.university,
                    source_programme=programme.programme,
                    source_track=programme.track,
                    page_url=url,
                    page_content=r.raw_content,
                )
    return results
