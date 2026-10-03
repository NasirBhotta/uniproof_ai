from __future__ import annotations

from pydantic import BaseModel, Field

from .source_policy import source_is_eligible_for_final_claim


class EvidenceLedgerEntry(BaseModel):
    programme_id: str
    claim_key: str
    claim_value: str | int | float | bool | None = None
    source_url: str
    source_title: str | None = None
    excerpt: str | None = None
    retrieved_at: str | None = None
    eligible_for_final_claim: bool = False


class EvidenceLedger(BaseModel):
    entries: list[EvidenceLedgerEntry] = Field(default_factory=list)

    def add(self, entry: EvidenceLedgerEntry, official_university_domains: set[str] | None = None) -> None:
        entry.eligible_for_final_claim = source_is_eligible_for_final_claim(
            entry.source_url,
            official_university_domains=official_university_domains,
        )
        self.entries.append(entry)

    def final_claim_evidence(self, programme_id: str, claim_key: str) -> list[EvidenceLedgerEntry]:
        return [
            e for e in self.entries
            if e.programme_id == programme_id
            and e.claim_key == claim_key
            and e.eligible_for_final_claim
        ]
