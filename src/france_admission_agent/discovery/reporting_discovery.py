"""
Reporting Engine for Research Knowledge Summary and Discovery Rounds
Author: Nasir Bhutta
Description: Formats output/Research-Knowledge-Summary.md and output/Discovery-Round-{N}.md.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..memory.coverage import FRANCE_REGIONS_REGISTRY, get_next_recommended_regions


def generate_research_knowledge_summary(conn: sqlite3.Connection, output_path: str | Path = "output/Research-Knowledge-Summary.md") -> str:
    lines: list[str] = []

    # 1. University counts
    univ_total = conn.execute("SELECT COUNT(*) as c FROM universities").fetchone()["c"]
    univ_researched = conn.execute("SELECT COUNT(*) as c FROM universities WHERE coverage_status != 'NOT_RESEARCHED'").fetchone()["c"]

    # 2. Programme counts
    prog_total = conn.execute("SELECT COUNT(*) as c FROM programmes").fetchone()["c"]
    prog_viable = conn.execute("SELECT COUNT(*) as c FROM programmes WHERE is_viable = 1").fetchone()["c"]
    prog_rejected = conn.execute("SELECT COUNT(*) as c FROM programmes WHERE is_rejected = 1").fetchone()["c"]

    # 3. Regional coverage
    reg_rows = conn.execute("SELECT * FROM regional_coverage ORDER BY universities_checked DESC").fetchall()
    covered_regions = sum(1 for r in reg_rows if r["universities_checked"] > 0)
    underexplored = [r["region"] for r in reg_rows if r["universities_checked"] == 0 and r["region"] != "Île-de-France"]

    # 4. Evidence & Historical statistics
    ev_total = conn.execute("SELECT COUNT(*) as c FROM evidence").fetchone()["c"]
    ev_verified = conn.execute("SELECT COUNT(*) as c FROM evidence WHERE verification_status IN ('VERIFIED_CURRENT', 'VERIFIED_HISTORICAL')").fetchone()["c"]

    cap_count = conn.execute("SELECT COUNT(DISTINCT programme_id) as c FROM programme_capacity").fetchone()["c"]
    app_count = conn.execute("SELECT COUNT(DISTINCT programme_id) as c FROM admission_statistics WHERE applicants IS NOT NULL").fetchone()["c"]
    adm_count = conn.execute("SELECT COUNT(DISTINCT programme_id) as c FROM admission_statistics WHERE admitted IS NOT NULL").fetchone()["c"]
    verified_stats = conn.execute("SELECT COUNT(*) as c FROM admission_statistics WHERE verification_status IN ('VERIFIED_CURRENT', 'VERIFIED_HISTORICAL')").fetchone()["c"]
    unverified_stats = conn.execute("SELECT COUNT(*) as c FROM admission_statistics WHERE verification_status = 'UNVERIFIED_STATISTIC'").fetchone()["c"]

    # 5. Language and Route stats
    eng_verified = conn.execute("SELECT COUNT(*) as c FROM programme_languages WHERE teaching_language_status = 'VERIFIED_ENGLISH'").fetchone()["c"]
    pak_route_verified = conn.execute("SELECT COUNT(*) as c FROM universities WHERE pakistan_route IS NOT NULL").fetchone()["c"]

    # 6. Efficiency stats
    search_count = conn.execute("SELECT COUNT(*) as c FROM search_history").fetchone()["c"]

    lines.append("# France Master's Research — Knowledge Base Summary")
    lines.append("")
    lines.append("> **Persistent Research Memory**: Local SQLite database (`data/france_research.db`)")
    lines.append("> **Objective**: Progressively accumulate verified France-wide public university Master's knowledge across bounded runs.")
    lines.append("")

    lines.append("## 1. Institutional & Regional Coverage")
    lines.append(f"- **Universities Known:** {univ_total}")
    lines.append(f"- **Universities Researched:** {univ_researched}")
    lines.append(f"- **Metropolitan Regions Covered:** {covered_regions} / {len(FRANCE_REGIONS_REGISTRY)}")
    lines.append(f"- **Top Underexplored Regions for Future Discovery:** {', '.join(underexplored[:4])}")
    lines.append("")

    lines.append("## 2. Programme Pool & Viability")
    lines.append(f"- **Programmes Known in Memory:** {prog_total}")
    lines.append(f"- **Academically Viable Programmes (Groups A + B + C):** {prog_viable}")
    lines.append(f"- **Incompatible / Rejected Programmes:** {prog_rejected}")
    lines.append(f"- **Programmes with Verified 100% English Instruction:** {eng_verified}")
    lines.append(f"- **Institutions with Verified Pakistan Études en France Route:** {pak_route_verified}")
    lines.append("")

    lines.append("## 3. Evidence & Historical Selectivity Audit")
    lines.append(f"- **Total Evidence Items in Ledger:** {ev_total}")
    lines.append(f"- **Officially Verified Evidence Claims:** {ev_verified}")
    lines.append(f"- **Programmes with Cohort Capacity Data:** {cap_count}")
    lines.append(f"- **Programmes with Applicant Volume Data:** {app_count}")
    lines.append(f"- **Programmes with Enrolled / Admitted Data:** {adm_count}")
    lines.append(f"- **Officially Verified Historical Statistics:** {verified_stats}")
    lines.append(f"- **Audited Secondary Estimates (UNVERIFIED_STATISTIC):** {unverified_stats}")
    lines.append("")

    lines.append("## 4. Regional Coverage Status Table")
    lines.append("")
    lines.append("| Region | Known Univs | Checked Univs | Known Programmes | Viable Programmes | Coverage Level | Exhaustion Status |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for r in reg_rows:
        r_dict = dict(r)
        cov_lvl = r_dict.get("coverage_level") or r_dict.get("saturation_estimate", "LOW")
        exh_st = r_dict.get("exhaustion_status", "PARTIAL")
        lines.append(
            f"| {r_dict['region']} | {r_dict['universities_known']} | {r_dict['universities_checked']} | {r_dict['programmes_known']} | {r_dict['programmes_viable']} | {cov_lvl} | {exh_st} |"
        )
    lines.append("")

    lines.append("## 5. Current Top Viable Candidates in Memory")
    lines.append("")
    viable_rows = conn.execute(
        """
        SELECT p.programme_name, p.track_name, u.canonical_name, u.city, p.profile_fit_score, p.academic_strictness, p.language_risk
        FROM programmes p
        JOIN universities u ON p.institution_id = u.institution_id
        WHERE p.is_viable = 1
        ORDER BY p.profile_fit_score DESC
        """
    ).fetchall()

    lines.append("| University | Programme / Track | City | Profile Fit | Academic Strictness | Language Risk |")
    lines.append("|---|---|---|---:|---|---|")
    for row in viable_rows:
        t_name = row["track_name"] or "General"
        lines.append(
            f"| {row['canonical_name']} | {row['programme_name']} ({t_name}) | {row['city']} | {row['profile_fit_score']:.1f}/100 | {row['academic_strictness']} | {row['language_risk']} |"
        )
    lines.append("")

    content = "\n".join(lines)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8")
    return content


def generate_discovery_round_report(
    round_num: int,
    discovered_universities: list[str],
    discovered_programmes: list[dict[str, Any]],
    viable_newcomers: list[dict[str, Any]],
    metrics: dict[str, Any],
    next_regions: list[str],
    output_path: str | Path = None,
) -> str:
    lines: list[str] = []

    lines.append(f"# France Master's Research — Discovery Round {round_num} Report")
    lines.append("")
    lines.append(f"> **Mode**: Single Bounded Iterative Discovery Round")
    lines.append(f"> **Strategy**: Expansion into under-explored regional public universities with lower competition pressure.")
    lines.append("")

    # Section 16 & 29: Report Stop Reason, Hard Preconditions, and Execution Details
    stop_reason = metrics.get("stop_reason", "TARGET_REACHED")
    selected_regs = metrics.get("selected_regions", [])
    univs_attempted = metrics.get("universities_attempted", len(discovered_universities))
    searches_attempted = metrics.get("searches_attempted", metrics.get("external_search_calls", 0))
    new_candidates_found = metrics.get("new_candidates_found", len(discovered_programmes))
    candidates_verified = metrics.get("candidates_deeply_verified", len(viable_newcomers))
    remaining_budget = metrics.get("remaining_search_budget", 0)

    lines.append("## 1. Round Execution & Stop Reason")
    lines.append(f"- **Round Stop Reason:** `{stop_reason}`")
    lines.append(f"- **Stop Preconditions Satisfied:** {'YES' if metrics.get('stop_preconditions_satisfied', True) else 'NO'}")
    if stop_reason == "DIMINISHING_RETURNS":
        lines.append(f"  - **Actual searches used:** {metrics.get('external_search_calls', searches_attempted)}")
        lines.append(f"  - **Actual low-value searches:** {metrics.get('consecutive_actual_low_value', 0)}")
        lines.append(f"  - **Distinct frontiers attempted:** {metrics.get('distinct_frontiers_attempted', 0)}")
    lines.append(f"- **Selected Regions:** {', '.join(selected_regs) if selected_regs else 'None'}")
    lines.append(f"- **Distinct Regions Actually Searched:** {metrics.get('distinct_regions_searched', len(selected_regs))}")
    lines.append(f"- **Distinct Cities Actually Searched:** {metrics.get('distinct_cities_searched', 0)}")
    lines.append(f"- **New Search Frontiers Generated:** {metrics.get('new_frontiers_generated', 0)}")
    lines.append(f"- **Universities Attempted:** {univs_attempted} ({', '.join(discovered_universities) if discovered_universities else 'None'})")
    lines.append(f"- **New Universities:** {metrics.get('new_universities_count', len(discovered_universities))}")
    lines.append(f"- **Known Universities With New Tracks:** {metrics.get('known_universities_new_tracks', 0)}")
    lines.append(f"- **New Programmes:** {new_candidates_found}")
    lines.append(f"- **Deeply Verified Programmes:** {candidates_verified}")
    lines.append(f"- **Remaining Search Budget:** {remaining_budget}")
    lines.append(f"- **Regions Recommended for Next Bounded Round:** {', '.join(next_regions)}")
    lines.append("")

    # Section 15 & 29: Validate efficiency metrics before rendering
    ext_searches = metrics.get("external_search_calls", searches_attempted)
    ev_gain_per_search = metrics.get("evidence_gain_per_search")
    if ext_searches == 0:
        ev_gain_display = "N/A (0 external searches)"
    elif ev_gain_per_search is not None:
        ev_gain_display = f"{ev_gain_per_search}"
    else:
        ev_gain_display = "0.0"

    lines.append("## 2. Search & Token Efficiency Metrics")
    lines.append(f"- **External Search Calls Actually Executed:** {ext_searches}")
    lines.append(f"- **Provider Calls Attempted:** {metrics.get('provider_calls_attempted', ext_searches)}")
    lines.append(f"- **Provider Calls Successful:** {metrics.get('provider_calls_successful', ext_searches)}")
    lines.append(f"- **Provider Failures:** {metrics.get('provider_failures', 0)}")
    lines.append(f"- **Queries Blocked as Exact Duplicates:** {metrics.get('duplicate_queries_blocked', 0)}")
    lines.append(f"- **Queries Rewritten After Duplication:** {metrics.get('queries_rewritten', 0)}")
    lines.append(f"- **Searches Saved by Verified Memory:** {metrics.get('searches_saved_by_memory', 0)}")
    lines.append(f"- **Cache Hits:** {metrics.get('cache_hits', 0)}")
    lines.append(f"- **Fields Resolved:** {metrics.get('fields_resolved', 0)}")
    lines.append(f"- **Evidence Gain per Search:** {ev_gain_display}")
    lines.append(f"- **Tokens Used:** {metrics.get('tokens_used', '0 (Local deterministic parsing)')}")
    lines.append("")

    lines.append("## 3. Discovered Programmes in This Round")
    lines.append("")
    if discovered_programmes:
        lines.append("| University | Programme / Track | Region | Degree Fit | Instruction Language | Profile Fit | Opportunity Quality |")
        lines.append("|---|---|---|---|---|---:|---|")
        for p in discovered_programmes:
            deg_fit = p.get('degree_status') or "UNVERIFIED"
            t_lang = p.get('teaching_language') or p.get('teaching_language_status') or "LANGUAGE_UNVERIFIED"
            p_fit = p.get('profile_fit', p.get('profile_fit_score'))
            opp_qual = p.get('pool_comparison') or "PENDING_PIPELINE"
            score_text = f"{p_fit:.1f}/100" if p_fit is not None else "UNASSESSED"
            lines.append(
                f"| {p.get('university')} | {p.get('programme')} ({p.get('track') or 'Core'}) | {p.get('region')} | {deg_fit} | {t_lang} | {score_text} | {opp_qual} |"
            )
    else:
        lines.append("No new viable programmes added in this round.")
    lines.append("")

    content = "\n".join(lines)
    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content, encoding="utf-8")
    return content
