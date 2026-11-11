"""
Data & Evidence Audit Module
Author: Nasir Bhutta
Description: Audits Cycle 1 and Cycle 2 claims, historical statistics, and narrative statements
             before promotion into persistent research memory to prevent memory poisoning.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..schemas import EvidenceItem, HistoricalMetric

logger = logging.getLogger(__name__)

# Official source domains that can confer verified status
AUTHORITATIVE_SOURCE_DOMAINS = (
    ".gouv.fr",
    "monmaster.gouv.fr",
    "campusfrance.org",
    "enseignementsup-recherche.gouv.fr",
    "isima.fr",
    "univ-grenoble-alpes.fr",
    "umontpellier.fr",
    "univ-fcomte.fr",
    "ube.fr",
    "univ-rouen.fr",
    "univ-ubs.fr",
    "univ-cotedazur.fr",
    "univ-lehavre.fr",
    "unicaen.fr",
    "univ-rennes.fr",
    "univ-tours.fr",
    "univ-orleans.fr",
    "univ-brest.fr",
    "formasup-auvergne.fr",
)


def is_authoritative_source_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.lower()
    return any(dom in u for dom in AUTHORITATIVE_SOURCE_DOMAINS)


def audit_historical_statistic(
    statistic_name: str,
    metric: HistoricalMetric | None,
    primary_source_url: str | None,
) -> tuple[str, str]:
    """Audits a historical admission or capacity statistic.
    
    Returns:
        (verification_status, audit_notes)
        verification_status is one of: VERIFIED_HISTORICAL, VERIFIED_CURRENT, UNVERIFIED_STATISTIC
    """
    if not metric or metric.value is None:
        return "UNVERIFIED_STATISTIC", "No metric value provided."

    src = metric.source or primary_source_url or ""
    # Check if the source is an authoritative official page or PDF
    if is_authoritative_source_url(src):
        # If it's published on the university's official page with explicit year
        if metric.year:
            return "VERIFIED_HISTORICAL", f"Confirmed by official institutional source: {src} ({metric.year})"
        return "VERIFIED_CURRENT", f"Confirmed by official institutional source: {src}"

    # If it is from general commission review / secondary estimate:
    return "UNVERIFIED_STATISTIC", f"Secondary commission estimate; exact source text citation required: {src}"


def audit_candidate_narrative(
    narratives: list[str],
    transcript_coverage: float,
) -> list[str]:
    """Audits and purges prohibited contradictions or ungrounded equivalence statements.
    
    Rules:
    - Never say 'matches prerequisites' if coverage == 0.0%. Use 'TRANSCRIPT_MATCH_UNVERIFIED'.
    - Never say 'CGPA 3.23 equals upper-second' unless official conversion exists.
    - Never claim '133 Pakistani credits > 180 ECTS' without an official equivalence method.
    - Clearly label IELTS 6.5 B2 equivalency as standard CEFR guideline, not programme-specific.
    """
    audited: list[str] = []
    for text in narratives:
        cleaned = text

        # Rule 1: No fake transcript match claim when coverage is 0%
        if transcript_coverage == 0.0 and any(w in cleaned.lower() for w in ("matches", "aligned", "satisfies")) and "transcript" in cleaned.lower():
            cleaned = "TRANSCRIPT_MATCH_UNVERIFIED: Course-level prerequisite mapping not published; transcript evaluation pending."

        # Rule 2: No ungrounded degree honor class equivalence
        if "upper-second" in cleaned.lower() or "first-division" in cleaned.lower():
            cleaned = re.sub(r"represents a strong first-division / upper-second class equivalent\.?", "CGPA 3.23 / 4.00 (Standard Pakistani 4-point grading scale; French equivalence evaluated on dossier).", cleaned, flags=re.IGNORECASE)

        # Rule 3: No ungrounded ECTS volume comparison
        if "exceeds the 180 ects" in cleaned.lower():
            cleaned = "Accredited 4-year Bachelor's degree (133 credit hours; subject to individual French academic commission equivalence review)."

        audited.append(cleaned)
    return audited


def audit_evidence_item(evidence: EvidenceItem) -> str:
    """Classifies verification status of an EvidenceItem based on domain provenance and source type."""
    url = str(evidence.source_url or "").lower()
    if not url:
        return "UNVERIFIED"

    if is_authoritative_source_url(url):
        return "VERIFIED_CURRENT"
    
    if any(d in url for d in ("reddit.com", "quora.com", "wikipedia.org")):
        return "SUPPLEMENTARY_ONLY"

    return "UNVERIFIED"
