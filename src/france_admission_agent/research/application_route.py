from __future__ import annotations

import re
from typing import Any

from ..schemas import ApplicationRouteInfo, CandidateProfile, CheckStatus, ProgrammeCandidate
from .evidence_caches import InstitutionEvidenceCache
from .source_policy import hostname, source_is_eligible_for_final_claim


# Official Études en France countries (Pakistan is an EEF country)
EEF_COUNTRIES = {"pakistan", "pakistanais", "pakistanaise"}


def resolve_application_route(
    candidate: CandidateProfile,
    programme: ProgrammeCandidate,
    institution_cache: InstitutionEvidenceCache,
    cached_pages: dict[str, str] | None = None,
) -> ApplicationRouteInfo:
    """Dedicated application route resolver for non-EU candidate (Pakistan).
    Reuses InstitutionEvidenceCache whenever possible to prevent duplicate searches.
    """
    info = ApplicationRouteInfo(
        candidate_country_rule="Pakistan is an Études en France (EEF) procedure country under Campus France.",
    )

    # 1. Check InstitutionEvidenceCache
    inst_evidence = institution_cache.get(programme.university, programme.official_university_domain)
    if inst_evidence and inst_evidence.etudes_en_france_policy:
        info.platform = "Études en France"
        info.status = CheckStatus.PASS
        info.university_instruction = inst_evidence.etudes_en_france_policy
        info.evidence = inst_evidence.etudes_en_france_policy
        return info

    # 2. Inspect supplied official pages for explicit application instructions
    pages = cached_pages or {}
    for ev in programme.official_sources:
        if ev.source_url and ev.evidence_text:
            pages[str(ev.source_url)] = ev.evidence_text

    for url, text in pages.items():
        if not source_is_eligible_for_final_claim(url, {programme.official_university_domain} if programme.official_university_domain else None):
            continue

        lower_text = text.lower()

        # Check for Études en France / Campus France instructions
        if "études en france" in lower_text or "etudes en france" in lower_text or "campus france" in lower_text:
            indicators = [
                "pays à procédure",
                "pays relevant",
                "procédure eef",
                "procedure eef",
                "hors dap",
                "candidats étrangers",
                "candidats etrangers",
                "candidats internationaux",
                "candidature",
                "obligatoire",
                "non-eu",
                "international",
            ]
            if any(term in lower_text for term in indicators):
                info.platform = "Études en France"
                info.status = CheckStatus.PASS
                info.university_instruction = "Candidature via plateforme Études en France pour les candidats des pays à procédure EEF (dont Pakistan)."
                info.source_url = url
                info.evidence = text[:300]

                # Update institution cache so other programmes from this university benefit
                institution_cache.update_policy(
                    programme.university,
                    domain=programme.official_university_domain,
                    eef_policy=info.university_instruction,
                    page_url=url,
                    page_content=text[:1000],
                )
                return info

        # Check for eCandidat or direct portal
        if "ecandidat" in lower_text:
            if "pays à procédure études en france" not in lower_text:
                info.platform = "eCandidat"
                info.status = CheckStatus.PASS
                info.university_instruction = "Candidature via le portail eCandidat de l'université."
                info.source_url = url
                info.evidence = text[:300]
                return info

        # Check for Mon Master
        if "monmaster.gouv.fr" in lower_text or "mon master" in lower_text:
            # Mon Master is generally for students with a French/EU licence or already resident in France
            if "étudiants internationaux" in lower_text or "ressortissants" in lower_text:
                info.platform = "Mon Master"
                info.status = CheckStatus.PASS
                info.university_instruction = "Candidature via plateforme nationale Mon Master."
                info.source_url = url
                info.evidence = text[:300]
                return info

    # If already recorded on programme
    if programme.application_route:
        info.platform = programme.application_route
        info.status = CheckStatus.PASS
        info.evidence = f"Verified route: {programme.application_route}"
        return info

    # If route could not be definitively verified from official source
    info.status = CheckStatus.UNVERIFIED
    info.unresolved_items.append(
        "Candidate-specific route (Études en France vs direct university portal) not yet verified from official university pages."
    )
    return info
