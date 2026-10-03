from __future__ import annotations

import re
from urllib.parse import urlparse


TRUSTED_NATIONAL_DOMAINS = {
    "campusfrance.org",
    "monmaster.gouv.fr",
    "enseignementsup-recherche.gouv.fr",
    "service-public.fr",
    "etudiant.gouv.fr",
    "france-education-international.fr",
}

DISCOVERY_ONLY_DOMAINS = {
    "mastersportal.com",
    "studyportals.com",
    "reddit.com",
    "quora.com",
    "findamasters.com",
    "masterstudies.com",
    "educations.com",
    "diplomeo.com",
    "letudiant.fr",
    "studyrama.com",
}

# Known regional French university and engineering school official base domains
REGIONAL_UNIVERSITY_DOMAINS = {
    "uca.fr",
    "u-bordeaux.fr",
    "u-bourgogne.fr",
    "u-picardie.fr",
    "unicaen.fr",
    "unilim.fr",
    "unistra.fr",
    "unimes.fr",
    "umontpellier.fr",
    "univ-fcomte.fr",
    "univ-nantes.fr",
    "univ-rennes.fr",
    "univ-rennes1.fr",
    "univ-brest.fr",
    "univ-ubs.fr",
    "univ-lorraine.fr",
    "univ-reims.fr",
    "univ-lille.fr",
    "univ-artois.fr",
    "univ-littoral.fr",
    "univ-tours.fr",
    "univ-orleans.fr",
    "univ-rouen.fr",
    "univ-lehavre.fr",
    "univ-angers.fr",
    "univ-lemans.fr",
    "univ-poitiers.fr",
    "univ-pau.fr",
    "univ-smb.fr",
    "univ-st-etienne.fr",
    "univ-perp.fr",
    "isima.fr",
    "grenoble-inp.fr",
    "inp-toulouse.fr",
    "inp-bordeaux.fr",
    "cnam.fr",
    "eurecom.fr",
    "centralesupelec.fr",
    "sorbonne-universite.fr",
    "universite-paris-saclay.fr",
    "u-paris.fr",
    "univ-paris8.fr",
    "univ-paris13.fr",
}


def hostname(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def is_trusted_national_source(url: str) -> bool:
    host = hostname(url)
    return any(domain_matches(host, d) for d in TRUSTED_NATIONAL_DOMAINS)


def is_discovery_only_source(url: str) -> bool:
    host = hostname(url)
    return any(domain_matches(host, d) for d in DISCOVERY_ONLY_DOMAINS)


def looks_like_official_french_university(url: str) -> bool:
    """Conservative check for official French university / public institution websites."""
    host = hostname(url)
    if not host or is_discovery_only_source(url):
        return False

    if not host.endswith(".fr"):
        return False

    # Check known domain list
    if any(domain_matches(host, d) for d in REGIONAL_UNIVERSITY_DOMAINS):
        return True

    # Standard institutional naming patterns in France:
    tokens = (
        "univ-",
        "univ.",
        "universite",
        "u-",
        "inp-",
        "insa-",
        "polytech",
        "ecole",
        "institut",
    )
    return any(token in host for token in tokens)


def source_is_eligible_for_final_claim(url: str, official_university_domains: set[str] | None = None) -> bool:
    if is_discovery_only_source(url):
        return False

    host = hostname(url)
    if is_trusted_national_source(url):
        return True

    if official_university_domains:
        if any(domain_matches(host, d.lower().removeprefix("www.")) for d in official_university_domains if d):
            return True

    return looks_like_official_french_university(url)


def is_potential_verification_source(url: str) -> bool:
    if is_discovery_only_source(url):
        return False
    if is_trusted_national_source(url):
        return True
    host = hostname(url)
    return bool(host and host.endswith(".fr"))
