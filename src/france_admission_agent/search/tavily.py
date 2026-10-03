from __future__ import annotations

import os
from typing import Iterable

import httpx

from .models import SearchBatch, SearchResult


class TavilySearchClient:
    """Minimal Tavily REST client.

    We intentionally call the REST API directly instead of adding LangChain wrappers.
    This keeps the search layer independent from the orchestration framework.
    """

    SEARCH_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured.")

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
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
            "include_answer": False,
        }
        if include_domains:
            payload["include_domains"] = list(include_domains)
        if exclude_domains:
            payload["exclude_domains"] = list(exclude_domains)

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.post(self.SEARCH_URL, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            print(f"[!] Warning: Tavily search query timed out or failed: '{query[:60]}...' ({e})")
            return SearchBatch(query=query, results=[])

        results = []
        for item in data.get("results", []):
            url = item.get("url")
            title = item.get("title") or url or "Untitled"
            if not url:
                continue

            raw = item.get("raw_content")
            if raw and isinstance(raw, str):
                # Clean excessive HTML tags/scripts to conserve tokens and disk cache
                import re
                raw = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
                raw = re.sub(r"<[^>]+>", " ", raw)
                raw = re.sub(r"\s+", " ", raw).strip()

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=item.get("content") or "",
                    raw_content=raw,
                    score=item.get("score"),
                )
            )

        return SearchBatch(query=query, results=results)
