from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str = ""
    raw_content: str | None = None
    score: float | None = None


class SearchBatch(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
