from __future__ import annotations

from typing import Iterable, Protocol

from .models import SearchBatch


class SearchClient(Protocol):
    """Provider-neutral web search boundary.

    Implement this with Tavily, Gemini grounding, another search API, or an internal
    browser service. Core admission logic does not depend on the provider.
    """

    def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        search_depth: str = "advanced",
        include_domains: Iterable[str] | None = None,
        exclude_domains: Iterable[str] | None = None,
        include_raw_content: bool = True,
    ) -> SearchBatch:
        ...
