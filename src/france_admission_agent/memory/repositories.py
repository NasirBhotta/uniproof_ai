"""
SQLite Repositories for Research Memory
Author: Nasir Bhutta
Description: High-level repository functions for reading and writing entities, evidence,
             search effectiveness, and research runs in local SQLite memory.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class UniversityRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, data: dict[str, Any]):
        self.conn.execute(
            """
            INSERT INTO universities (
                institution_id, canonical_name, aliases, city, region, is_public,
                official_domains, international_admission_rules, etudes_en_france_policy,
                pakistan_route, foreign_degree_policy, tuition_policy, application_platforms,
                official_admissions_url, coverage_status, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(institution_id) DO UPDATE SET
                canonical_name = COALESCE(excluded.canonical_name, universities.canonical_name),
                aliases = COALESCE(excluded.aliases, universities.aliases),
                city = COALESCE(excluded.city, universities.city),
                region = COALESCE(excluded.region, universities.region),
                is_public = COALESCE(excluded.is_public, universities.is_public),
                official_domains = COALESCE(excluded.official_domains, universities.official_domains),
                international_admission_rules = COALESCE(excluded.international_admission_rules, universities.international_admission_rules),
                etudes_en_france_policy = COALESCE(excluded.etudes_en_france_policy, universities.etudes_en_france_policy),
                pakistan_route = COALESCE(excluded.pakistan_route, universities.pakistan_route),
                foreign_degree_policy = COALESCE(excluded.foreign_degree_policy, universities.foreign_degree_policy),
                tuition_policy = COALESCE(excluded.tuition_policy, universities.tuition_policy),
                application_platforms = COALESCE(excluded.application_platforms, universities.application_platforms),
                official_admissions_url = COALESCE(excluded.official_admissions_url, universities.official_admissions_url),
                coverage_status = COALESCE(excluded.coverage_status, universities.coverage_status),
                last_verified = COALESCE(excluded.last_verified, universities.last_verified)
            """,
            (
                data["institution_id"],
                data["canonical_name"],
                json.dumps(data.get("aliases", []), ensure_ascii=False),
                data.get("city"),
                data.get("region"),
                1 if data.get("is_public", True) else 0,
                json.dumps(data.get("official_domains", []), ensure_ascii=False),
                data.get("international_admission_rules"),
                data.get("etudes_en_france_policy"),
                data.get("pakistan_route"),
                data.get("foreign_degree_policy"),
                data.get("tuition_policy"),
                json.dumps(data.get("application_platforms", []), ensure_ascii=False),
                data.get("official_admissions_url"),
                data.get("coverage_status", "PARTIALLY_RESEARCHED"),
                data.get("last_verified"),
            )
        )
        self.conn.commit()

    def get(self, institution_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM universities WHERE institution_id = ?", (institution_id,)).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM universities ORDER BY canonical_name ASC").fetchall()
        return [dict(r) for r in rows]


class ProgrammeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_programme(self, data: dict[str, Any]):
        self.conn.execute(
            """
            INSERT INTO programmes (
                programme_id, institution_id, track_id, programme_name, track_name, level,
                m1_m2_structure, campus, city, official_url, admissions_url,
                academic_strictness, degree_strictness, prerequisite_strictness,
                selectivity_pressure, international_complexity, language_risk, candidate_fit_strength,
                candidate_strengths, candidate_weaknesses, reasons_competitive, reasons_fail,
                unresolved_fields, profile_fit_score, evidence_confidence_score, score_status,
                cycle1_group, is_viable, is_rejected, rejection_reasons, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(programme_id) DO UPDATE SET
                institution_id = excluded.institution_id,
                track_id = excluded.track_id,
                programme_name = excluded.programme_name,
                track_name = excluded.track_name,
                level = excluded.level,
                m1_m2_structure = COALESCE(excluded.m1_m2_structure, programmes.m1_m2_structure),
                campus = COALESCE(excluded.campus, programmes.campus),
                city = COALESCE(excluded.city, programmes.city),
                official_url = COALESCE(excluded.official_url, programmes.official_url),
                admissions_url = COALESCE(excluded.admissions_url, programmes.admissions_url),
                academic_strictness = COALESCE(excluded.academic_strictness, programmes.academic_strictness),
                degree_strictness = COALESCE(excluded.degree_strictness, programmes.degree_strictness),
                prerequisite_strictness = COALESCE(excluded.prerequisite_strictness, programmes.prerequisite_strictness),
                selectivity_pressure = COALESCE(excluded.selectivity_pressure, programmes.selectivity_pressure),
                international_complexity = COALESCE(excluded.international_complexity, programmes.international_complexity),
                language_risk = COALESCE(excluded.language_risk, programmes.language_risk),
                candidate_fit_strength = COALESCE(excluded.candidate_fit_strength, programmes.candidate_fit_strength),
                candidate_strengths = COALESCE(excluded.candidate_strengths, programmes.candidate_strengths),
                candidate_weaknesses = COALESCE(excluded.candidate_weaknesses, programmes.candidate_weaknesses),
                reasons_competitive = COALESCE(excluded.reasons_competitive, programmes.reasons_competitive),
                reasons_fail = COALESCE(excluded.reasons_fail, programmes.reasons_fail),
                unresolved_fields = COALESCE(excluded.unresolved_fields, programmes.unresolved_fields),
                profile_fit_score = COALESCE(excluded.profile_fit_score, programmes.profile_fit_score),
                evidence_confidence_score = COALESCE(excluded.evidence_confidence_score, programmes.evidence_confidence_score),
                score_status = COALESCE(excluded.score_status, programmes.score_status),
                cycle1_group = COALESCE(excluded.cycle1_group, programmes.cycle1_group),
                is_viable = excluded.is_viable,
                is_rejected = excluded.is_rejected,
                rejection_reasons = excluded.rejection_reasons,
                last_verified = excluded.last_verified
            """,
            (
                data["programme_id"],
                data["institution_id"],
                data.get("track_id", "core"),
                data["programme_name"],
                data.get("track_name"),
                data.get("level", "M1"),
                data.get("m1_m2_structure"),
                data.get("campus"),
                data.get("city"),
                data.get("official_url"),
                data.get("admissions_url"),
                data.get("academic_strictness", "UNKNOWN"),
                data.get("degree_strictness", "UNKNOWN"),
                data.get("prerequisite_strictness", "UNKNOWN"),
                data.get("selectivity_pressure", "UNKNOWN"),
                data.get("international_complexity", "UNKNOWN"),
                data.get("language_risk", "UNKNOWN"),
                data.get("candidate_fit_strength", "UNKNOWN"),
                json.dumps(data.get("candidate_strengths", []), ensure_ascii=False),
                json.dumps(data.get("candidate_weaknesses", []), ensure_ascii=False),
                json.dumps(data.get("reasons_competitive", []), ensure_ascii=False),
                json.dumps(data.get("reasons_fail", []), ensure_ascii=False),
                json.dumps(data.get("unresolved_fields", []), ensure_ascii=False),
                data.get("profile_fit_score", 0.0),
                data.get("evidence_confidence_score", 0.0),
                data.get("score_status", "PROVISIONAL"),
                data.get("cycle1_group"),
                1 if data.get("is_viable", False) else 0,
                1 if data.get("is_rejected", False) else 0,
                json.dumps(data.get("rejection_reasons", []), ensure_ascii=False),
                data.get("last_verified"),
            )
        )
        self.conn.commit()

    def get(self, programme_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM programmes WHERE programme_id = ?", (programme_id,)).fetchone()
        return dict(row) if row else None

    def list_viable(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM programmes WHERE is_viable = 1 ORDER BY profile_fit_score DESC").fetchall()
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM programmes ORDER BY programme_name ASC").fetchall()
        return [dict(r) for r in rows]


class EvidenceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_evidence(self, data: dict[str, Any]):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO evidence (
                evidence_id, institution_id, programme_id, track_id, claim_type, claim_value,
                source_url, source_title, source_type, source_year, target_cycle,
                retrieved_at, verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["evidence_id"],
                data["institution_id"],
                data.get("programme_id"),
                data.get("track_id"),
                data["claim_type"],
                data.get("claim_value"),
                data.get("source_url"),
                data.get("source_title"),
                data.get("source_type", "official_university"),
                data.get("source_year"),
                data.get("target_cycle"),
                data.get("retrieved_at"),
                data.get("verification_status", "UNVERIFIED"),
            )
        )
        self.conn.commit()

    def list_for_programme(self, programme_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM evidence WHERE programme_id = ?", (programme_id,)).fetchall()
        return [dict(r) for r in rows]

    def list_verified_for_institution(self, institution_id: str, claim_type: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE institution_id = ? AND claim_type = ? AND verification_status IN ('VERIFIED_CURRENT', 'VERIFIED_HISTORICAL')",
            (institution_id, claim_type)
        ).fetchall()
        return [dict(r) for r in rows]


class SearchHistoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record_search(self, data: dict[str, Any]):
        self.conn.execute(
            """
            INSERT INTO search_history (
                query, normalized_query, provider, target_institution, target_programme, target_field,
                results_count, useful_results, official_results, fields_resolved, evidence_gain, duplicate_of, cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["query"],
                data["normalized_query"],
                data.get("provider", "tavily"),
                data.get("target_institution"),
                data.get("target_programme"),
                data.get("target_field"),
                data.get("results_count", 0),
                data.get("useful_results", 0),
                data.get("official_results", 0),
                data.get("fields_resolved", 0),
                data.get("evidence_gain", 0.0),
                data.get("duplicate_of"),
                data.get("cost", 0.0),
            )
        )
        # Update query effectiveness
        pattern = data.get("target_field") or "general_discovery"
        self.conn.execute(
            """
            INSERT INTO query_effectiveness (pattern, times_used, times_successful, fields_resolved_count, avg_evidence_gain, effectiveness_rating, last_used)
            VALUES (?, 1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(pattern) DO UPDATE SET
                times_used = query_effectiveness.times_used + 1,
                times_successful = query_effectiveness.times_successful + excluded.times_successful,
                fields_resolved_count = query_effectiveness.fields_resolved_count + excluded.fields_resolved_count,
                avg_evidence_gain = (query_effectiveness.avg_evidence_gain * query_effectiveness.times_used + excluded.avg_evidence_gain) / (query_effectiveness.times_used + 1),
                effectiveness_rating = CASE
                    WHEN (query_effectiveness.fields_resolved_count + excluded.fields_resolved_count) >= 3 THEN 'HIGH'
                    WHEN (query_effectiveness.fields_resolved_count + excluded.fields_resolved_count) >= 1 THEN 'MODERATE'
                    ELSE 'LOW'
                END,
                last_used = CURRENT_TIMESTAMP
            """,
            (
                pattern,
                1 if data.get("fields_resolved", 0) > 0 else 0,
                data.get("fields_resolved", 0),
                data.get("evidence_gain", 0.0),
                "HIGH" if data.get("fields_resolved", 0) > 1 else ("MODERATE" if data.get("fields_resolved", 0) == 1 else "LOW")
            )
        )
        self.conn.commit()

    def find_equivalent_search(self, normalized_query: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM search_history WHERE normalized_query = ? ORDER BY id DESC LIMIT 1",
            (normalized_query,)
        ).fetchone()
        return dict(row) if row else None


class ResearchRunRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record_run(self, data: dict[str, Any]):
        self.conn.execute(
            """
            INSERT OR REPLACE INTO research_runs (
                run_id, run_type, started_at, finished_at, programmes_evaluated, viable_count,
                external_searches, memory_hits, cache_hits, duplicate_searches_blocked,
                searches_saved_by_memory, fields_resolved, evidence_gain, llm_calls, tokens_used, summary_markdown,
                distinct_frontiers, distinct_regions, distinct_cities, stop_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["run_id"],
                data["run_type"],
                data.get("started_at"),
                data.get("finished_at"),
                data.get("programmes_evaluated", 0),
                data.get("viable_count", 0),
                data.get("external_searches", 0),
                data.get("memory_hits", 0),
                data.get("cache_hits", 0),
                data.get("duplicate_searches_blocked", 0),
                data.get("searches_saved_by_memory", 0),
                data.get("fields_resolved", 0),
                data.get("evidence_gain", 0.0),
                data.get("llm_calls", 0),
                str(data.get("tokens_used", "0")),
                data.get("summary_markdown", ""),
                data.get("distinct_frontiers", 0),
                data.get("distinct_regions", 0),
                data.get("distinct_cities", 0),
                data.get("stop_reason"),
            )
        )
        self.conn.commit()
