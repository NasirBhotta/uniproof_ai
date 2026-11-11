"""
France Public-University Regional & Institutional Coverage Map
Author: Nasir Bhutta
Description: Tracks research coverage across all 13 French metropolitan administrative regions
             and public universities, identifying under-explored territory to direct new discovery.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

# Complete registry of French metropolitan regions and their primary public universities
FRANCE_REGIONS_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "Grand Est": [
        {"id": "strasbourg", "name": "Université de Strasbourg", "city": "Strasbourg", "domain": "unistra.fr"},
        {"id": "lorraine", "name": "Université de Lorraine", "city": "Nancy / Metz", "domain": "univ-lorraine.fr"},
        {"id": "reims-urca", "name": "Université de Reims Champagne-Ardenne", "city": "Reims", "domain": "univ-reims.fr"},
        {"id": "haute-alsace", "name": "Université de Haute-Alsace", "city": "Mulhouse", "domain": "uha.fr"},
    ],
    "Hauts-de-France": [
        {"id": "lille", "name": "Université de Lille", "city": "Lille", "domain": "univ-lille.fr"},
        {"id": "artois", "name": "Université d'Artois", "city": "Arras / Lens", "domain": "univ-artois.fr"},
        {"id": "picardie-jules-verne", "name": "Université de Picardie Jules Verne", "city": "Amiens", "domain": "u-picardie.fr"},
        {"id": "littoral-cote-d-opale", "name": "Université du Littoral Côte d'Opale (ULCO)", "city": "Calais / Dunkerque", "domain": "univ-littoral.fr"},
        {"id": "polytechnique-hauts-de-france", "name": "Université Polytechnique Hauts-de-France", "city": "Valenciennes", "domain": "uphf.fr"},
    ],
    "Nouvelle-Aquitaine": [
        {"id": "bordeaux", "name": "Université de Bordeaux", "city": "Bordeaux", "domain": "u-bordeaux.fr"},
        {"id": "poitiers", "name": "Université de Poitiers", "city": "Poitiers", "domain": "univ-poitiers.fr"},
        {"id": "limoges", "name": "Université de Limoges", "city": "Limoges", "domain": "unilim.fr"},
        {"id": "pau-pays-de-l-adour", "name": "Université de Pau et des Pays de l'Adour (UPPA)", "city": "Pau", "domain": "univ-pau.fr"},
        {"id": "la-rochelle", "name": "La Rochelle Université", "city": "La Rochelle", "domain": "univ-larochelle.fr"},
    ],
    "Pays de la Loire": [
        {"id": "nantes", "name": "Nantes Université", "city": "Nantes", "domain": "univ-nantes.fr"},
        {"id": "angers", "name": "Université d'Angers", "city": "Angers", "domain": "univ-angers.fr"},
        {"id": "le-mans", "name": "Le Mans Université", "city": "Le Mans", "domain": "univ-lemans.fr"},
    ],
    "Centre-Val de Loire": [
        {"id": "tours", "name": "Université de Tours", "city": "Tours", "domain": "univ-tours.fr"},
        {"id": "orleans", "name": "Université d'Orléans", "city": "Orléans", "domain": "univ-orleans.fr"},
    ],
    "Bourgogne-Franche-Comté": [
        {"id": "bourgogne", "name": "Université de Bourgogne", "city": "Dijon", "domain": "ube.fr"},
        {"id": "franche-comt", "name": "Université de Franche-Comté", "city": "Besançon", "domain": "univ-fcomte.fr"},
    ],
    "Auvergne-Rhône-Alpes": [
        {"id": "clermont-auvergne-inp", "name": "Clermont Auvergne INP", "city": "Aubière", "domain": "isima.fr"},
        {"id": "grenoble-alpes", "name": "Université Grenoble Alpes", "city": "Grenoble", "domain": "univ-grenoble-alpes.fr"},
        {"id": "lyon-1", "name": "Université Claude Bernard Lyon 1", "city": "Villeurbanne / Lyon", "domain": "univ-lyon1.fr"},
        {"id": "lyon-2", "name": "Université Lumière Lyon 2", "city": "Lyon", "domain": "univ-lyon2.fr"},
        {"id": "lyon-3", "name": "Université Jean Moulin Lyon 3", "city": "Lyon", "domain": "univ-lyon3.fr"},
        {"id": "saint-etienne", "name": "Université Jean Monnet", "city": "Saint-Étienne", "domain": "univ-st-etienne.fr"},
        {"id": "savoie-mont-blanc", "name": "Université Savoie Mont Blanc", "city": "Chambéry / Annecy", "domain": "univ-smb.fr"},
    ],
    "Occitanie": [
        {"id": "montpellier", "name": "Université de Montpellier", "city": "Montpellier", "domain": "umontpellier.fr"},
        {"id": "toulouse-3", "name": "Université Toulouse III - Paul Sabatier", "city": "Toulouse", "domain": "univ-tlse3.fr"},
        {"id": "toulouse-1", "name": "Université Toulouse Capitole", "city": "Toulouse", "domain": "ut-capitole.fr"},
        {"id": "nimes", "name": "Université de Nîmes", "city": "Nîmes", "domain": "unimes.fr"},
        {"id": "perpignan", "name": "Université de Perpignan Via Domitia", "city": "Perpignan", "domain": "univ-perp.fr"},
    ],
    "Provence-Alpes-Côte d'Azur": [
        {"id": "c-te-d-azur", "name": "Université Côte d'Azur", "city": "Nice", "domain": "univ-cotedazur.fr"},
        {"id": "aix-marseille", "name": "Aix-Marseille Université", "city": "Marseille / Aix-en-Provence", "domain": "univ-amu.fr"},
        {"id": "avignon", "name": "Avignon Université", "city": "Avignon", "domain": "univ-avignon.fr"},
        {"id": "toulon", "name": "Université de Toulon", "city": "Toulon", "domain": "univ-tln.fr"},
    ],
    "Normandie": [
        {"id": "rouen-normandie", "name": "Université de Rouen Normandie", "city": "Saint-Étienne-du-Rouvray / Rouen", "domain": "univ-rouen.fr"},
        {"id": "caen-normandie", "name": "Université de Caen Normandie", "city": "Caen", "domain": "unicaen.fr"},
        {"id": "le-havre-normandie", "name": "Université Le Havre Normandie", "city": "Le Havre", "domain": "univ-lehavre.fr"},
    ],
    "Bretagne": [
        {"id": "rennes", "name": "Université de Rennes", "city": "Rennes", "domain": "univ-rennes.fr"},
        {"id": "rennes-2", "name": "Université Rennes 2", "city": "Rennes", "domain": "univ-rennes2.fr"},
        {"id": "bretagne-occidentale", "name": "Université de Bretagne Occidentale (UBO)", "city": "Brest", "domain": "univ-brest.fr"},
        {"id": "bretagne-sud", "name": "Université Bretagne Sud", "city": "Vannes / Lorient", "domain": "univ-ubs.fr"},
    ],
    "Île-de-France": [
        {"id": "sorbonne-universite", "name": "Sorbonne Université", "city": "Paris", "domain": "sorbonne-universite.fr"},
        {"id": "paris-cite", "name": "Université Paris Cité", "city": "Paris", "domain": "u-paris.fr"},
        {"id": "paris-saclay", "name": "Université Paris-Saclay", "city": "Orsay / Gif-sur-Yvette", "domain": "universite-paris-saclay.fr"},
        {"id": "sorbonne-paris-nord", "name": "Université Sorbonne Paris Nord", "city": "Villetaneuse", "domain": "univ-paris13.fr"},
        {"id": "paris-nanterre", "name": "Université Paris Nanterre", "city": "Nanterre", "domain": "parisnanterre.fr"},
        {"id": "paris-8", "name": "Université Paris 8 Vincennes - Saint-Denis", "city": "Saint-Denis", "domain": "univ-paris8.fr"},
        {"id": "evry", "name": "Université d'Évry Val-d'Essonne", "city": "Évry", "domain": "univ-evry.fr"},
        {"id": "gustave-eiffel", "name": "Université Gustave Eiffel", "city": "Champs-sur-Marne", "domain": "univ-gustave-eiffel.fr"},
        {"id": "versailles-sqy", "name": "Université de Versailles Saint-Quentin-en-Yvelines", "city": "Versailles", "domain": "uvsq.fr"},
    ],
    "Corse": [
        {"id": "corse", "name": "Université de Corse Pasquale Paoli", "city": "Corte", "domain": "universita.corsica"},
    ],
}


def seed_regional_coverage(conn: sqlite3.Connection):
    """Initializes regional_coverage table with known French public university metrics, distinguishing coverage from exhaustion."""
    for region, univs in FRANCE_REGIONS_REGISTRY.items():
        total_known = len(univs)
        # Check how many universities are checked in DB
        placeholders = ",".join("?" for _ in univs)
        u_ids = [u["id"] for u in univs]
        row = conn.execute(
            f"SELECT COUNT(DISTINCT institution_id) as cnt FROM universities WHERE institution_id IN ({placeholders}) AND coverage_status != 'NOT_RESEARCHED'",
            u_ids
        ).fetchone()
        checked = row["cnt"] if row else 0

        # Check programmes evaluated in this region
        prog_row = conn.execute(
            f"SELECT COUNT(*) as known, SUM(CASE WHEN is_viable = 1 THEN 1 ELSE 0 END) as viable "
            f"FROM programmes WHERE institution_id IN ({placeholders})",
            u_ids
        ).fetchone()
        p_known = prog_row["known"] if prog_row and prog_row["known"] else 0
        p_viable = prog_row["viable"] if prog_row and prog_row["viable"] else 0

        # Existing coverage record for strategies_tested and exhaustion
        existing = conn.execute(
            "SELECT coverage_level, exhaustion_status, strategies_tested FROM regional_coverage WHERE region = ?",
            (region,)
        ).fetchone()

        # Section 6 & 17: Separate coverage from exhaustion and distinguish Paris
        if region == "Île-de-France":
            coverage_level = "INTENTIONALLY_DEPRIORITIZED"
            saturation = "INTENTIONALLY_DEPRIORITIZED"
            exhaustion = "PARTIAL"
        elif checked == 0:
            coverage_level = "LOW"
            saturation = "LOW"
            exhaustion = "NOT_TESTED"
        elif checked >= total_known:
            coverage_level = "HIGH"
            saturation = "HIGH"
            # Section 7: Never mark exhausted merely because known universities were checked.
            # Only mark LIKELY_EXHAUSTED after multiple distinct discovery strategies fail.
            exhaustion = existing["exhaustion_status"] if existing and existing["exhaustion_status"] in ("LIKELY_EXHAUSTED", "EXHAUSTED") else "PARTIAL"
        else:
            coverage_level = "MODERATE"
            saturation = "MODERATE"
            exhaustion = "PARTIAL"

        strategies_str = existing["strategies_tested"] if existing and existing["strategies_tested"] else "[]"

        conn.execute(
            """
            INSERT INTO regional_coverage (
                region, universities_known, universities_checked, programmes_known, programmes_viable,
                saturation_estimate, coverage_level, exhaustion_status, strategies_tested, last_searched
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(region) DO UPDATE SET
                universities_known = excluded.universities_known,
                universities_checked = excluded.universities_checked,
                programmes_known = excluded.programmes_known,
                programmes_viable = excluded.programmes_viable,
                saturation_estimate = excluded.saturation_estimate,
                coverage_level = excluded.coverage_level,
                exhaustion_status = excluded.exhaustion_status,
                last_searched = CURRENT_TIMESTAMP
            """,
            (region, total_known, checked, p_known, p_viable, saturation, coverage_level, exhaustion, strategies_str)
        )
    conn.commit()


def get_next_recommended_regions(conn: sqlite3.Connection, top_n: int = 3) -> list[dict[str, Any]]:
    """Identifies the 2-4 most promising under-explored regions (Section 16)."""
    # Exclude Île-de-France (deprioritized) and fully exhausted regions
    rows = conn.execute(
        """
        SELECT region, universities_known, universities_checked, programmes_known, programmes_viable,
               saturation_estimate, coverage_level, exhaustion_status, strategies_tested
        FROM regional_coverage
        WHERE region != 'Île-de-France' AND exhaustion_status != 'EXHAUSTED'
        ORDER BY 
            CASE 
                WHEN exhaustion_status = 'NOT_TESTED' THEN 0
                WHEN universities_checked < universities_known THEN 1
                WHEN programmes_viable < 2 THEN 2
                ELSE 3
            END ASC,
            universities_checked ASC,
            programmes_viable ASC,
            universities_known DESC,
            last_searched ASC
        LIMIT ?
        """,
        (top_n,)
    ).fetchall()

    return [dict(r) for r in rows]
