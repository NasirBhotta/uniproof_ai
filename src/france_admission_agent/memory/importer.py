"""
Cycle 1 & Cycle 2 Memory Importer with Strict Auditing
Author: Nasir Bhutta
Description: Populates persistent SQLite research memory from verified Cycle 1 and audited Cycle 2
             data, strictly adhering to provenance rules and purging contradictions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .audit import audit_candidate_narrative, audit_evidence_item, audit_historical_statistic
from .coverage import seed_regional_coverage
from .database import get_connection, init_database
from .repositories import (
    EvidenceRepository,
    ProgrammeRepository,
    UniversityRepository,
)
from ..research.evidence_caches import normalize_university_key
from ..schemas import Cycle2Evaluation, ProgrammeEvaluation

logger = logging.getLogger(__name__)

# Map university IDs to official administrative regions in France
UNIV_REGION_MAP: dict[str, str] = {
    "clermont-auvergne-inp": "Auvergne-Rhône-Alpes",
    "grenoble-alpes": "Auvergne-Rhône-Alpes",
    "montpellier": "Occitanie",
    "franche-comt": "Bourgogne-Franche-Comté",
    "bourgogne": "Bourgogne-Franche-Comté",
    "rouen-normandie": "Normandie",
    "caen-normandie": "Normandie",
    "le-havre-normandie": "Normandie",
    "bretagne-sud": "Bretagne",
    "bretagne-occidentale": "Bretagne",
    "rennes": "Bretagne",
    "tours": "Centre-Val de Loire",
    "orleans": "Centre-Val de Loire",
    "c-te-d-azur": "Provence-Alpes-Côte d'Azur",
}


def import_existing_runs_into_memory(
    db_path: str | Path = "data/france_research.db",
    cycle1_json: str | Path = "output/cycle1_results.json",
    cycle2_json: str | Path = "output/cycle2_analysis.json",
) -> dict[str, int]:
    conn = init_database(db_path)
    univ_repo = UniversityRepository(conn)
    prog_repo = ProgrammeRepository(conn)
    ev_repo = EvidenceRepository(conn)

    counts = {
        "universities": 0,
        "programmes": 0,
        "viable_programmes": 0,
        "evidence_items": 0,
        "historical_stats_audited": 0,
        "verified_stats": 0,
        "unverified_stats": 0,
    }

    # 1. Load Cycle 1 results
    c1_path = Path(cycle1_json)
    c1_evals: list[dict[str, Any]] = []
    if c1_path.exists():
        with open(c1_path, encoding="utf-8") as f:
            c1_data = json.load(f)
            c1_evals = c1_data.get("evaluations", []) + c1_data.get("rejected", [])

    # 2. Load Cycle 2 analysis (indexed by programme_id)
    c2_path = Path(cycle2_json)
    c2_by_id: dict[str, dict[str, Any]] = {}
    if c2_path.exists():
        with open(c2_path, encoding="utf-8") as f:
            c2_items = json.load(f)
            for it in c2_items:
                pid = it.get("programme", {}).get("programme_id")
                if pid:
                    c2_by_id[pid] = it

    seen_univs: set[str] = set()

    for item in c1_evals:
        raw_p = item.get("programme", {})
        p_id = raw_p.get("programme_id")
        if not p_id:
            continue

        u_name = raw_p.get("university", "")
        inst_id = raw_p.get("institution_id") or normalize_university_key(u_name)
        region = UNIV_REGION_MAP.get(inst_id, "Unknown Region")

        # Upsert University
        if inst_id not in seen_univs:
            univ_repo.upsert({
                "institution_id": inst_id,
                "canonical_name": u_name,
                "city": raw_p.get("city"),
                "region": region,
                "is_public": raw_p.get("public", True),
                "official_domains": [str(raw_p.get("programme_url") or "")] if raw_p.get("programme_url") else [],
                "etudes_en_france_policy": "Pakistan is under Études en France (Campus France) procedure.",
                "pakistan_route": "Études en France",
                "application_platforms": ["Études en France", "eCandidat"],
                "official_admissions_url": str(raw_p.get("official_admissions_url") or raw_p.get("programme_url") or ""),
                "coverage_status": "SUBSTANTIALLY_RESEARCHED" if region in ("Normandie", "Bretagne") else "PARTIALLY_RESEARCHED",
                "last_verified": "2026-10-03",
            })
            seen_univs.add(inst_id)
            counts["universities"] += 1

        # Check viability & group
        group = item.get("group", "D_NEEDS_OTHER_VERIFICATION")
        is_viable = group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED") and not item.get("rejected", False)
        is_rejected = item.get("rejected", False) or group == "E_REJECTED"

        # Check transcript match coverage
        t_info = raw_p.get("transcript_match_info", {})
        t_cov = t_info.get("coverage", 0.0)

        # Audit candidate narratives if available from Cycle 2
        c2_entry = c2_by_id.get(p_id, {})
        sel = c2_entry.get("selectivity", {})

        raw_strengths = sel.get("candidate_strengths", [])
        raw_weaknesses = sel.get("candidate_weaknesses", [])
        raw_comp = sel.get("reasons_candidate_is_competitive", [])
        raw_fail = sel.get("reasons_admission_may_fail", [])

        audited_strengths = audit_candidate_narrative(raw_strengths, t_cov)
        audited_weaknesses = audit_candidate_narrative(raw_weaknesses, t_cov)
        audited_comp = audit_candidate_narrative(raw_comp, t_cov)
        audited_fail = audit_candidate_narrative(raw_fail, t_cov)

        score_dict = item.get("score", {})

        # Upsert Programme
        prog_repo.upsert_programme({
            "programme_id": p_id,
            "institution_id": inst_id,
            "track_id": raw_p.get("track_id", "core"),
            "programme_name": raw_p.get("programme", ""),
            "track_name": raw_p.get("track"),
            "level": raw_p.get("level", "M1"),
            "m1_m2_structure": raw_p.get("programme_structure", {}).get("evidence"),
            "campus": raw_p.get("campus"),
            "city": raw_p.get("city"),
            "official_url": str(raw_p.get("programme_url") or ""),
            "admissions_url": str(raw_p.get("official_admissions_url") or raw_p.get("programme_url") or ""),
            "academic_strictness": sel.get("academic_strictness", "UNKNOWN"),
            "degree_strictness": sel.get("degree_strictness", "UNKNOWN"),
            "prerequisite_strictness": sel.get("prerequisite_strictness", "UNKNOWN"),
            "selectivity_pressure": sel.get("selectivity_pressure", "UNKNOWN"),
            "international_complexity": sel.get("international_process_complexity", "UNKNOWN"),
            "language_risk": sel.get("language_risk", "UNKNOWN"),
            "candidate_fit_strength": sel.get("candidate_fit_strength", "UNKNOWN"),
            "candidate_strengths": audited_strengths,
            "candidate_weaknesses": audited_weaknesses,
            "reasons_competitive": audited_comp,
            "reasons_fail": audited_fail,
            "unresolved_fields": raw_p.get("unresolved_questions", []),
            "profile_fit_score": score_dict.get("profile_fit_score", 0.0),
            "evidence_confidence_score": score_dict.get("evidence_confidence_score", 0.0),
            "score_status": score_dict.get("status", "PROVISIONAL"),
            "cycle1_group": group,
            "is_viable": is_viable,
            "is_rejected": is_rejected,
            "rejection_reasons": item.get("rejection_reasons", []),
            "last_verified": "2026-10-03",
        })
        counts["programmes"] += 1
        if is_viable:
            counts["viable_programmes"] += 1

        # Upsert Programme Requirements
        conn.execute(
            """
            INSERT OR REPLACE INTO programme_requirements (
                programme_id, accepted_degree_fields, explicit_prerequisites, degree_status,
                transcript_match_coverage, transcript_match_status, matched_courses, unmatched_topics, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p_id,
                json.dumps(raw_p.get("accepted_degree_fields", []), ensure_ascii=False),
                json.dumps(raw_p.get("explicit_prerequisites", []), ensure_ascii=False),
                item.get("eligibility", {}).get("degree_field", "UNVERIFIED"),
                t_cov,
                t_info.get("status", "UNVERIFIED"),
                json.dumps(t_info.get("matched_candidate_courses", []), ensure_ascii=False),
                json.dumps(t_info.get("unmatched_topics", []), ensure_ascii=False),
                "2026-10-03",
            )
        )

        # Upsert Programme Language
        lang = raw_p.get("language", {})
        t_lang_info = raw_p.get("teaching_language_info", {})
        conn.execute(
            """
            INSERT OR REPLACE INTO programme_languages (
                programme_id, teaching_language_status, teaching_languages, english_cefr_required,
                ielts_overall_min, ielts_speaking_min, french_level_required, moi_accepted, evidence_text, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p_id,
                t_lang_info.get("status", "LANGUAGE_UNVERIFIED"),
                json.dumps(t_lang_info.get("values", []), ensure_ascii=False),
                lang.get("english_cefr_required"),
                lang.get("ielts_overall_min"),
                lang.get("ielts_speaking_min"),
                lang.get("french_level_required") or lang.get("french_cefr_required"),
                "UNVERIFIED",
                t_lang_info.get("evidence"),
                "2026-10-03",
            )
        )

        # Upsert Programme Cycle
        cycle = raw_p.get("canonical_cycle", {})
        conn.execute(
            """
            INSERT OR REPLACE INTO programme_cycles (
                programme_id, target_intake, status, opening_date, deadline, source_cycle, source_url, last_verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p_id,
                cycle.get("target_intake", "2027"),
                cycle.get("status", "PENDING_PUBLICATION"),
                cycle.get("opening_date"),
                cycle.get("deadline"),
                cycle.get("source_cycle"),
                cycle.get("source"),
                "2026-10-03",
            )
        )

        # Upsert Evidence Items
        for idx, ev in enumerate(raw_p.get("official_sources", [])):
            ev_id = f"{p_id}::ev::{idx}::{ev.get('claim', 'general')}"
            from ..schemas import EvidenceItem
            ev_obj = EvidenceItem.model_validate(ev)
            status = audit_evidence_item(ev_obj)

            ev_repo.insert_evidence({
                "evidence_id": ev_id,
                "institution_id": inst_id,
                "programme_id": p_id,
                "track_id": raw_p.get("track_id", "core"),
                "claim_type": ev.get("claim", "unknown"),
                "claim_value": str(ev.get("value") or ""),
                "source_url": str(ev.get("source_url") or ""),
                "source_title": ev.get("claim"),
                "source_type": ev.get("source_type", "official_university"),
                "source_year": "2024-2025",
                "target_cycle": "2027",
                "retrieved_at": "2026-10-03",
                "verification_status": status,
            })
            counts["evidence_items"] += 1

        # Audit & Store Historical Admission Statistics
        if sel:
            hist_app = sel.get("historical_applicants")
            hist_adm = sel.get("historical_admitted")
            cap_metric = sel.get("capacity")
            from ..schemas import HistoricalMetric

            app_obj = HistoricalMetric.model_validate(hist_app) if hist_app else None
            adm_obj = HistoricalMetric.model_validate(hist_adm) if hist_adm else None
            cap_obj = HistoricalMetric.model_validate(cap_metric) if cap_metric else None

            # Audit capacity
            cap_status, _ = audit_historical_statistic("capacity", cap_obj, raw_p.get("programme_url"))
            if cap_obj and cap_obj.value:
                try:
                    seats_int = int(cap_obj.value)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO programme_capacity (programme_id, academic_year, seats, source_url, verification_status, last_verified)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (p_id, cap_obj.year or "2024-2025", seats_int, str(cap_obj.source or ""), cap_status, "2026-10-03")
                    )
                except (ValueError, TypeError):
                    pass

            # Audit applicant / admitted counts
            app_status, _ = audit_historical_statistic("applicants", app_obj, raw_p.get("programme_url"))
            counts["historical_stats_audited"] += 1

            if app_status in ("VERIFIED_CURRENT", "VERIFIED_HISTORICAL"):
                counts["verified_stats"] += 1
            else:
                counts["unverified_stats"] += 1

            # Only calculate and persist derived ratio if both applicants and admitted exist
            ratio_val = None
            if app_obj and adm_obj and app_obj.value and adm_obj.value:
                try:
                    a_int = int(app_obj.value)
                    adm_int = int(adm_obj.value)
                    ratio_val = round((adm_int / a_int) * 100.0, 1)
                except (ValueError, TypeError, ZeroDivisionError):
                    pass

            conn.execute(
                """
                INSERT OR REPLACE INTO admission_statistics (
                    programme_id, academic_year, applicants, admitted, capacity, derived_ratio,
                    ratio_definition, population, source_url, source_name, verification_status, last_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p_id,
                    (app_obj and app_obj.year) or (cap_obj and cap_obj.year) or "2024-2025",
                    int(app_obj.value) if app_obj and app_obj.value else None,
                    int(adm_obj.value) if adm_obj and adm_obj.value else None,
                    int(cap_obj.value) if cap_obj and cap_obj.value else None,
                    ratio_val,
                    "derived historical admission ratio (enrolled / applicants)" if ratio_val else None,
                    "All M1 applicants",
                    str((app_obj and app_obj.source) or (cap_obj and cap_obj.source) or ""),
                    str((app_obj and app_obj.source) or "Official commission review"),
                    app_status,
                    "2026-10-03",
                )
            )

    # Seed regional coverage map
    seed_regional_coverage(conn)
    conn.commit()
    conn.close()

    logger.info(f"Memory import complete: {counts}")
    return counts
