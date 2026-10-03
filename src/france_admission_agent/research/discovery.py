from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import CandidateProfile
from ..search.base import SearchClient
from .queries import build_discovery_queries
from .source_policy import is_discovery_only_source


@dataclass
class DiscoveryLead:
    title: str
    url: str
    snippet: str
    query: str
    discovery_only: bool = False


@dataclass
class DiscoveryReport:
    leads: list[DiscoveryLead] = field(default_factory=list)
    queries_run: int = 0


def discover_programme_leads(
    candidate: CandidateProfile,
    search: SearchClient,
    *,
    per_query: int = 8,
    query_start: int = 0,
    max_queries: int | None = None,
) -> DiscoveryReport:
    queries = build_discovery_queries(candidate)
    if queries:
        query_start = query_start % len(queries)
        queries = queries[query_start:] + queries[:query_start]
    if max_queries is not None:
        queries = queries[:max_queries]

    report = DiscoveryReport()
    seen: set[str] = set()

    for rq in queries:
        batch = search.search(rq.query, max_results=per_query, include_raw_content=False)
        report.queries_run += 1

        for r in batch.results:
            url = str(r.url)
            if url in seen:
                continue
            seen.add(url)
            report.leads.append(DiscoveryLead(
                title=r.title,
                url=url,
                snippet=r.snippet,
                query=rq.query,
                discovery_only=is_discovery_only_source(url),
            ))

    return report
