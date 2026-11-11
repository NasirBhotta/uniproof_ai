from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Iterable

from .base import SearchClient
from .models import SearchBatch


class CachedSearchClient:
    """Disk cache around any SearchClient to reduce repeated API calls and cost."""

    def __init__(
        self,
        inner: SearchClient,
        cache_dir: str | Path = ".cache/search",
        tracker: Any | None = None,
        ttl_days: float | None = None,
    ):
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = tracker
        self.ttl_days = ttl_days

    def _key(self, payload: dict) -> Path:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return self.cache_dir / f"{hashlib.sha256(raw).hexdigest()}.json"

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
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_domains": sorted(include_domains or []),
            "exclude_domains": sorted(exclude_domains or []),
            "include_raw_content": include_raw_content,
        }
        path = self._key(payload)
        if path.exists() and (
            self.ttl_days is None
            or time.time() - path.stat().st_mtime < self.ttl_days * 86400
        ):
            if self.tracker:
                self.tracker.record_search(query, is_cache_hit=True)
            return SearchBatch.model_validate_json(path.read_text(encoding="utf-8")).model_copy(
                update={"cache_hit": True}
            )

        if self.tracker:
            self.tracker.record_search(query, is_cache_hit=False)

        result = self.inner.search(
            query,
            max_results=max_results,
            search_depth=search_depth,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_raw_content=include_raw_content,
        )
        if not result.error:
            path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
