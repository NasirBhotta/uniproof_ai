"""
Efficiency Governor: Deterministic Search and Token Optimization Engine
Author: Nasir Bhutta
Description: Enforces strict resolution hierarchy, semantic query deduplication, dynamic search budgeting,
             evidence-gain estimation, context slicing, and provider independence.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..memory.database import get_connection
from ..research.evidence_caches import normalize_query, normalize_university_key

logger = logging.getLogger(__name__)

# Field importance weights for expected evidence gain calculation
FIELD_IMPORTANCE_WEIGHTS: dict[str, float] = {
    "teaching_language": 1.0,
    "accepted_degree_fields": 1.0,
    "application_route": 0.9,
    "programme_structure": 0.8,
    "capacity": 0.7,
    "admission_statistics": 0.7,
    "explicit_prerequisites": 0.6,
    "ielts_requirements": 0.6,
    "french_requirements": 0.6,
    "calendar_dates": 0.4,
    "general_overview": 0.2,
}

MAX_TARGETED_ATTEMPTS = 3


@dataclass
class GovernorMetrics:
    external_search_calls: int = 0
    searches_by_provider: dict[str, int] = field(default_factory=lambda: {"tavily": 0, "cache": 0, "memory": 0})
    page_fetches: int = 0
    provider_calls_attempted: int = 0
    provider_calls_successful: int = 0
    provider_failures: int = 0
    cache_hits: int = 0
    memory_hits: int = 0
    duplicate_queries_blocked: int = 0
    queries_rewritten: int = 0
    new_frontiers_generated: int = 0
    searches_saved_by_memory: int = 0
    fields_resolved: int = 0
    fields_resolved_per_search: float = 0.0
    evidence_gain_per_search: float = 0.0
    total_evidence_gain: float = 0.0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_per_programme: float = 0.0
    searches_per_programme: float = 0.0
    verified_claims_added: int = 0
    verified_claims_reused: int = 0
    stale_claims_refreshed: int = 0

    def compute_averages(self, total_programmes: int):
        if self.external_search_calls > 0:
            self.fields_resolved_per_search = round(self.fields_resolved / self.external_search_calls, 2)
            self.evidence_gain_per_search = round(self.total_evidence_gain / self.external_search_calls, 2)
        else:
            self.fields_resolved_per_search = 0.0
            self.evidence_gain_per_search = 0.0
        
        if total_programmes > 0:
            self.searches_per_programme = round(self.external_search_calls / total_programmes, 2)
            self.tokens_per_programme = round((self.input_tokens + self.output_tokens) / total_programmes, 1)


class EfficiencyGovernor:
    """Deterministic planning layer for search, memory, and token efficiency."""

    def __init__(self, db_conn: sqlite3.Connection | None = None, db_path: str | Path = "data/france_research.db"):
        self.conn = db_conn or get_connection(db_path)
        self.metrics = GovernorMetrics()
        self._fetched_pages_cache: dict[str, str] = {}  # url -> extracted text
        self._attempt_counter: dict[str, int] = {}      # (programme_id, field) -> count

    def can_resolve_from_memory(self, institution_id: str, field_name: str) -> tuple[bool, Any]:
        """Hierarchy Step 1: Check verified local memory for reusable institution-wide facts."""
        row = self.conn.execute(
            "SELECT claim_value, source_url FROM evidence WHERE institution_id = ? AND claim_type = ? AND verification_status IN ('VERIFIED_CURRENT', 'VERIFIED_HISTORICAL')",
            (institution_id, field_name)
        ).fetchone()

        if row:
            self.metrics.memory_hits += 1
            self.metrics.searches_saved_by_memory += 1
            self.metrics.verified_claims_reused += 1
            return True, row["claim_value"]
        return False, None

    def should_search(
        self,
        programme_id: str,
        institution_id: str,
        target_field: str,
        current_evidence_confidence: float = 0.0,
    ) -> tuple[bool, str]:
        """Evaluates whether another external search is justified based on value function and attempt caps."""
        # 1. Check if memory has it verified
        has_mem, _ = self.can_resolve_from_memory(institution_id, target_field)
        if has_mem:
            return False, f"Resolved via verified persistent memory for institution {institution_id}."

        # 2. Check attempt counter
        key = f"{programme_id}::{target_field}"
        attempts = self._attempt_counter.get(key, 0)
        if attempts >= MAX_TARGETED_ATTEMPTS:
            return False, f"Maximum search attempts ({MAX_TARGETED_ATTEMPTS}) reached for {target_field} on {programme_id}."

        # 3. Check field weight
        weight = FIELD_IMPORTANCE_WEIGHTS.get(target_field, 0.3)
        if weight < 0.3 and current_evidence_confidence >= 70.0:
            return False, f"Field {target_field} has low weight ({weight}) and programme already has sufficient confidence ({current_evidence_confidence})."

        return True, "Search justified by missing critical evidence."

    def check_duplicate_status(
        self,
        query: str,
        target_institution: str = "",
        target_field: str = "",
        search_purpose: str = "",
        region: str = "",
        city: str = "",
        ttl_days: int = 30,
    ) -> tuple[str, dict[str, Any] | None]:
        """
        Classifies query into three distinct states (Section 2):
        - EXACT_DUPLICATE: same normalized query + same target + same purpose + sufficiently recent (<= 30 days) => block
        - SEMANTICALLY_SIMILAR: similar wording but potentially different search space => rewrite query toward new dimension
        - NEW_FRONTIER: new institution / city / region / programme type / evidence field => allow
        """
        norm_q = normalize_query(query)

        # 1. Check exact duplicate in search_history
        row = self.conn.execute(
            """
            SELECT * FROM search_history
            WHERE normalized_query = ?
            ORDER BY id DESC LIMIT 1
            """,
            (norm_q,)
        ).fetchone()

        if row:
            ts_str = row["timestamp"]
            # Check freshness window (default 30 days)
            ttl_check = self.conn.execute(
                "SELECT (julianday('now') - julianday(?)) <= ? as is_recent",
                (ts_str, ttl_days)
            ).fetchone()
            is_recent = bool(ttl_check["is_recent"]) if ttl_check and ttl_check["is_recent"] is not None else True

            if is_recent:
                # Target match validation if specified
                target_match = True
                if target_institution and row["target_institution"]:
                    target_match = (target_institution == row["target_institution"])
                if search_purpose and row["search_purpose"]:
                    target_match = target_match and (search_purpose == row["search_purpose"])

                if target_match:
                    return "EXACT_DUPLICATE", dict(row)

        # 2. Check semantically similar (e.g. high token overlap within same region/city/field)
        q_tokens = set(re.findall(r'\w+', norm_q))
        if len(q_tokens) >= 3:
            recent_rows = self.conn.execute(
                "SELECT query, normalized_query, region, city, target_field FROM search_history ORDER BY id DESC LIMIT 30"
            ).fetchall()
            for r in recent_rows:
                r_tokens = set(re.findall(r'\w+', r["normalized_query"]))
                if not r_tokens:
                    continue
                overlap = len(q_tokens.intersection(r_tokens)) / max(len(q_tokens), len(r_tokens))
                if overlap >= 0.75:
                    if (region and r["region"] == region) or (city and r["city"] == city):
                        return "SEMANTICALLY_SIMILAR", dict(r)

        return "NEW_FRONTIER", None

    def is_exact_duplicate(
        self,
        query: str,
        target_institution: str = "",
        search_purpose: str = "",
        ttl_days: int = 30,
    ) -> tuple[bool, dict[str, Any] | None]:
        """Convenience method checking only for exact duplicates within TTL."""
        status, row = self.check_duplicate_status(
            query=query,
            target_institution=target_institution,
            search_purpose=search_purpose,
            ttl_days=ttl_days,
        )
        return (status == "EXACT_DUPLICATE"), row

    def check_semantic_duplicate(self, query: str) -> tuple[bool, dict[str, Any] | None]:
        """Detects exact duplicates already executed within 30 days to prevent duplicate external calls."""
        is_dup, row = self.is_exact_duplicate(query=query, ttl_days=30)
        if is_dup:
            self.metrics.duplicate_queries_blocked += 1
            return True, row
        return False, None

    def record_search_result(
        self,
        query: str,
        target_institution: str,
        target_programme: str,
        target_field: str,
        results_count: int,
        fields_resolved: int = 0,
        provider: str = "tavily",
        cost: float = 0.0,
        search_purpose: str = "targeted_verification",
        region: str = "",
        city: str = "",
        institution_id: str = "",
        programme_id: str = "",
        discovery_round: int = 1,
    ):
        """Records executed search in memory with full scope and updates metrics."""
        norm_q = normalize_query(query)
        weight = FIELD_IMPORTANCE_WEIGHTS.get(target_field, 0.5)
        ev_gain = fields_resolved * weight

        self.metrics.external_search_calls += 1
        self.metrics.searches_by_provider[provider] = self.metrics.searches_by_provider.get(provider, 0) + 1
        self.metrics.fields_resolved += fields_resolved
        self.metrics.total_evidence_gain += ev_gain

        key = f"{target_programme}::{target_field}"
        self._attempt_counter[key] = self._attempt_counter.get(key, 0) + 1

        self.conn.execute(
            """
            INSERT INTO search_history (
                query, normalized_query, provider, target_institution, target_programme, target_field,
                search_purpose, region, city, institution_id, programme_id, discovery_round,
                results_count, useful_results, official_results, fields_resolved, evidence_gain, duplicate_of, cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                norm_q,
                provider,
                target_institution,
                target_programme,
                target_field,
                search_purpose,
                region,
                city,
                institution_id or target_institution,
                programme_id or target_programme,
                discovery_round,
                results_count,
                1 if (fields_resolved > 0 or results_count > 0) else 0,
                1 if results_count > 0 else 0,
                fields_resolved,
                ev_gain,
                None,
                cost,
            )
        )
        self.conn.commit()

    def get_or_extract_page_content(self, url: str, raw_html_or_text: str | None = None) -> str:
        """Page fetch & text extraction cache: prevents re-fetching and truncates to relevant text."""
        if url in self._fetched_pages_cache:
            self.metrics.cache_hits += 1
            return self._fetched_pages_cache[url]

        if not raw_html_or_text:
            return ""

        self.metrics.page_fetches += 1
        # Extract clean text: strip scripts, styles, extra whitespace
        text = re.sub(r'<script.*?</script>', '', raw_html_or_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        clean_text = re.sub(r'\s+', ' ', text).strip()

        # Cache in memory and DB
        self._fetched_pages_cache[url] = clean_text
        c_hash = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
        try:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO source_documents (url, content_hash, extracted_text)
                VALUES (?, ?, ?)
                """,
                (url, c_hash, clean_text[:10000])  # Store first 10k chars in DB
            )
            self.conn.commit()
        except sqlite3.Error:
            pass

        return clean_text

    @staticmethod
    def slice_context_for_language(candidate_data: dict[str, Any]) -> dict[str, Any]:
        """Context slicing: provides ONLY language and nationality fields to language resolver."""
        return {
            "ielts": candidate_data.get("ielts"),
            "french": candidate_data.get("french"),
            "nationality": candidate_data.get("nationality"),
        }

    @staticmethod
    def slice_context_for_transcript(candidate_data: dict[str, Any]) -> dict[str, Any]:
        """Context slicing: provides ONLY degree coursework to transcript matcher."""
        return {
            "degree_title": candidate_data.get("degree", {}).get("title"),
            "cgpa": candidate_data.get("degree", {}).get("cgpa"),
            "credits": candidate_data.get("degree", {}).get("credits"),
            "transcript_courses": candidate_data.get("transcript_courses", []),
        }

    @staticmethod
    def slice_context_for_route(candidate_data: dict[str, Any]) -> dict[str, Any]:
        """Context slicing: provides ONLY country and target level to route resolver."""
        return {
            "nationality": candidate_data.get("nationality"),
            "country_of_residence": candidate_data.get("target", {}).get("country"),
            "target_level": candidate_data.get("target", {}).get("level"),
            "intake": candidate_data.get("target", {}).get("intake"),
        }

    @staticmethod
    def slice_context_for_historical_stats(programme_data: dict[str, Any]) -> dict[str, Any]:
        """Context slicing: provides ONLY programme identity and published statistics."""
        return {
            "university": programme_data.get("university"),
            "programme": programme_data.get("programme"),
            "track": programme_data.get("track"),
            "level": programme_data.get("level"),
            "capacity": programme_data.get("capacity"),
        }
