from __future__ import annotations

from dataclasses import dataclass
from ..schemas import CandidateProfile


@dataclass(frozen=True)
class ResearchQuery:
    purpose: str
    query: str
    language: str


# Regional university hubs prioritizing smaller/medium cities outside Paris
REGIONAL_TARGETS = [
    ("Centre-Val de Loire", ["Tours", "Orléans"]),
    ("Bourgogne-Franche-Comté", ["Besançon", "Dijon"]),
    ("Normandie", ["Caen", "Rouen", "Le Havre"]),
    ("Bretagne", ["Rennes", "Brest", "Vannes"]),
    ("Grand Est", ["Nancy", "Metz", "Reims", "Strasbourg"]),
    ("Hauts-de-France", ["Lille", "Amiens", "Arras"]),
    ("Nouvelle-Aquitaine", ["Poitiers", "Limoges", "Pau"]),
    ("Auvergne", ["Clermont-Ferrand", "Aubière", "Saint-Étienne"]),
    ("Pays de la Loire", ["Nantes", "Angers", "Le Mans"]),
    ("Occitanie", ["Montpellier", "Perpignan", "Nîmes"]),
]


def build_discovery_queries(candidate: CandidateProfile) -> list[ResearchQuery]:
    queries: list[ResearchQuery] = []

    # 1. REGIONAL-FIRST DISCOVERY (Core requirement #3)
    # Target regional French universities with heavy French search terms
    for region_name, cities in REGIONAL_TARGETS:
        joined_cities = '" OR "'.join(cities)
        city_term = f'("{joined_cities}")'
        queries.append(ResearchQuery(
            purpose="regional_discovery",
            language="fr",
            query=f'"Master Informatique" M1 université {region_name} {city_term} admission',
        ))
        queries.append(ResearchQuery(
            purpose="regional_discovery",
            language="fr",
            query=f'"Master Informatique" M1 {region_name} "candidats internationaux" "Études en France"',
        ))
        queries.append(ResearchQuery(
            purpose="regional_discovery",
            language="fr",
            query=f'"Master génie logiciel" OR "Master systèmes distribués" M1 {region_name} université',
        ))

    # Regional English-taught queries
    queries.append(ResearchQuery(
        purpose="regional_discovery",
        language="en",
        query='Master "Computer Science" M1 France regional public university English taught admission',
    ))

    # 2. National Official Portals with regional/outside-Paris filters
    queries.extend([
        ResearchQuery(
            purpose="official_catalogue",
            language="fr",
            query='site:monmaster.gouv.fr "Master" "Informatique" M1 "capacité d\'accueil"',
        ),
        ResearchQuery(
            purpose="official_catalogue",
            language="fr",
            query='site:monmaster.gouv.fr "Master" "Génie logiciel" M1',
        ),
        ResearchQuery(
            purpose="campus_france",
            language="fr",
            query='site:campusfrance.org master informatique M1 universite "candidature"',
        ),
    ])

    # 3. Specific specialized programme queries matching candidate's profile
    queries.extend([
        ResearchQuery(
            purpose="specialization_discovery",
            language="fr",
            query='"Master informatique" "systèmes distribués" M1 université "candidats étrangers"',
        ),
        ResearchQuery(
            purpose="specialization_discovery",
            language="fr",
            query='"Master informatique" "génie logiciel" M1 université "candidature M1"',
        ),
        ResearchQuery(
            purpose="specialization_discovery",
            language="fr",
            query='"Master informatique" "intelligence artificielle" M1 université "prérequis"',
        ),
    ])

    return queries


def build_verification_queries(
    university: str,
    programme: str,
    year: str = "2027",
    official_domain: str | None = None,
) -> list[ResearchQuery]:
    """Generates targeted verification queries.
    Crucial: Do not force year '2027' into every requirement query because 2027 dates
    are pending publication and would miss active admission requirement pages.
    """
    base = f'"{university}" "{programme}"'
    queries: list[ResearchQuery] = []

    if official_domain:
        queries.append(ResearchQuery(
            purpose="official_domain_admissions",
            query=f'site:{official_domain} "{programme}" M1 admission prérequis',
            language="fr",
        ))
        queries.append(ResearchQuery(
            purpose="official_domain_international",
            query=f'site:{official_domain} "international" OR "candidats internationaux" "etudes en france" langue',
            language="fr",
        ))
    else:
        queries.append(ResearchQuery(
            purpose="official_programme",
            query=f'{base} M1 site officiel admission prérequis licence',
            language="fr",
        ))
        queries.append(ResearchQuery(
            purpose="international_admissions",
            query=f'{base} admission "candidats internationaux" "Études en France" langue',
            language="fr",
        ))

    return queries


def build_targeted_field_query(
    university: str,
    programme: str,
    field_name: str,
    official_domain: str | None = None,
) -> ResearchQuery:
    """Generates the narrowest possible search query for an unresolved field."""
    prefix = f"site:{official_domain} " if official_domain else f'"{university}" '

    if field_name in ("ielts_speaking_min", "english_requirement", "teaching_language"):
        return ResearchQuery(
            purpose="targeted_language",
            query=f'{prefix}"{programme}" "IELTS" OR "TOEFL" OR "anglais" OR "English" niveau',
            language="fr",
        )
    elif field_name in ("french_level_required", "french_requirement"):
        return ResearchQuery(
            purpose="targeted_french",
            query=f'{prefix}"{programme}" "DELF" OR "TCF" OR "DALF" OR "niveau de français" B2',
            language="fr",
        )
    elif field_name in ("application_route", "etudes_en_france"):
        return ResearchQuery(
            purpose="targeted_route",
            query=f'{prefix}"candidats internationaux" "Études en France" OR "Campus France" OR "eCandidat"',
            language="fr",
        )
    elif field_name in ("capacity", "applicant_count", "selectivity"):
        return ResearchQuery(
            purpose="targeted_capacity",
            query=f'{prefix}"{programme}" "capacité d\'accueil" OR "places"',
            language="fr",
        )
    else:
        return ResearchQuery(
            purpose=f"targeted_{field_name}",
            query=f'{prefix}"{programme}" M1 prérequis admission',
            language="fr",
        )
