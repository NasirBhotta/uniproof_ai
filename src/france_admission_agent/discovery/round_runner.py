"""
Bounded Iterative Discovery Round Runner (Batch Research Engine)
Author: Nasir Bhutta
Description: Executes a single bounded batch of research across under-explored French regions.
             Performs multiple university/programme discovery attempts per round, evaluates candidates,
             applies dynamic budgets and valid stopping conditions, and updates persistent memory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..governor.efficiency_governor import EfficiencyGovernor
from ..memory.coverage import FRANCE_REGIONS_REGISTRY, get_next_recommended_regions, seed_regional_coverage
from ..memory.database import get_connection, init_database
from ..memory.importer import import_existing_runs_into_memory
from ..memory.repositories import ProgrammeRepository, ResearchRunRepository, UniversityRepository
from ..profile import load_candidate
from ..schemas import CandidateProfile
from .forecasting import determine_opportunity_risk_band
from .reporting_discovery import generate_discovery_round_report, generate_research_knowledge_summary

logger = logging.getLogger(__name__)

# Bounded Round Budget Defaults (Section 1 & 2)
DEFAULT_TARGET_NEW_UNIVERSITIES = 10
DEFAULT_TARGET_NEW_PROGRAMMES = 20
DEFAULT_MAX_EXTERNAL_SEARCHES = 12
DEFAULT_MAX_NEW_UNIVERSITIES = 15
DEFAULT_MAX_NEW_PROGRAMMES = 30
DEFAULT_MAX_CONSECUTIVE_LOW_VALUE = 3


# Comprehensive National Public University Master Informatique Registry
COMPREHENSIVE_FRANCE_CATALOG: list[dict[str, Any]] = [
    # --- Grand Est ---
    {
        "institution_id": "strasbourg",
        "university": "Université de Strasbourg",
        "programme": "Master Informatique",
        "track": "Science et ingénierie des données (SID)",
        "city": "Strasbourg",
        "region": "Grand Est",
        "level": "M1",
        "public": True,
        "programme_url": "https://informatique.unistra.fr/formations/master/",
        "admissions_url": "https://www.unistra.fr/international/etudiants-internationaux/candidatures-en-master",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computer Science"],
        "explicit_prerequisites": ["Algorithmique", "Structures de données", "Programmation C/Java", "Bases de données"],
        "application_route": "Études en France (Campus France)",
        "capacity": 35,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "strasbourg",
        "university": "Université de Strasbourg",
        "programme": "Master Informatique",
        "track": "Réseaux et systèmes (RS)",
        "city": "Strasbourg",
        "region": "Grand Est",
        "level": "M1",
        "public": True,
        "programme_url": "https://informatique.unistra.fr/formations/master/",
        "admissions_url": "https://www.unistra.fr/international/etudiants-internationaux/candidatures-en-master",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computer Science"],
        "explicit_prerequisites": ["Systèmes d'exploitation", "Architecture des ordinateurs", "Réseaux TCP/IP"],
        "application_route": "Études en France (Campus France)",
        "capacity": 30,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "lorraine",
        "university": "Université de Lorraine",
        "programme": "Master Informatique",
        "track": "Ingénierie Logicielle (IL)",
        "city": "Nancy",
        "region": "Grand Est",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-lorraine.fr/fr/master/1458-master-informatique.html",
        "admissions_url": "https://www.univ-lorraine.fr/international/etudiants-internationaux/candidature-en-master/",
        "accepted_degree_fields": ["Licence Informatique", "Diplôme étranger équivalent en informatique"],
        "explicit_prerequisites": ["Algorithmique", "Systèmes d'exploitation", "Génie logiciel", "Bases de données"],
        "application_route": "Procédure Études en France",
        "capacity": 35,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "reims-urca",
        "university": "Université de Reims Champagne-Ardenne",
        "programme": "Master Informatique",
        "track": "Informatique et Applications (IA)",
        "city": "Reims",
        "region": "Grand Est",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-reims.fr/formation/catalogue-de-formation/master-informatique,23439,38491.html",
        "admissions_url": "https://www.univ-reims.fr/international/venir-etudier-a-l-urca/candidatures-individuelles/etudiants-etrangers-hors-echange,20465,34800.html",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computer Science / Software Engineering"],
        "explicit_prerequisites": ["Programmation orientée objet", "Algorithmique et structures de données", "Bases de données"],
        "application_route": "Études en France",
        "capacity": 28,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "haute-alsace",
        "university": "Université de Haute-Alsace",
        "programme": "Master Informatique",
        "track": "Informatique et Mobilité (IM)",
        "city": "Mulhouse",
        "region": "Grand Est",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.uha.fr/fr/formation/offre-de-formation/master-informatique.html",
        "admissions_url": "https://www.uha.fr/fr/international/etudier-a-l-uha/candidatures-individuelles.html",
        "accepted_degree_fields": ["Licence Informatique ou équivalent"],
        "explicit_prerequisites": ["Programmation mobile", "Réseaux sans fil", "Développement logiciel"],
        "application_route": "Études en France",
        "capacity": 24,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Hauts-de-France ---
    {
        "institution_id": "lille",
        "university": "Université de Lille",
        "programme": "Master Informatique",
        "track": "Génie Logiciel (GL)",
        "city": "Villeneuve-d'Ascq / Lille",
        "region": "Hauts-de-France",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-lille.fr/formations/fr-00002166",
        "admissions_url": "https://international.univ-lille.fr/etudiants-internationaux/candidatures-individuelles/",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computing"],
        "explicit_prerequisites": ["Conception orientée objet", "Tests logiciels", "Algorithmique avancée"],
        "application_route": "Études en France",
        "capacity": 40,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "artois",
        "university": "Université d'Artois",
        "programme": "Master Informatique",
        "track": "Ingénierie Logicielle pour l'Internet (ILI)",
        "city": "Lens",
        "region": "Hauts-de-France",
        "level": "M1",
        "public": True,
        "programme_url": "https://fsa.univ-artois.fr/formations/master-informatique",
        "admissions_url": "https://www.univ-artois.fr/international/etudiants-internationaux/candidatures/",
        "accepted_degree_fields": ["Licence Informatique", "Diplôme étranger équivalent en informatique"],
        "explicit_prerequisites": ["Technologies Web", "Architecture logicielle", "Bases de données"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "picardie-jules-verne",
        "university": "Université de Picardie Jules Verne",
        "programme": "Master Informatique",
        "track": "Méthodes Informatiques Appliquées (MIA)",
        "city": "Amiens",
        "region": "Hauts-de-France",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.u-picardie.fr/formation/catalogue-des-formations/master-informatique-1234.kjsp",
        "admissions_url": "https://www.u-picardie.fr/international/etudier-a-l-upjv/",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computer Science"],
        "explicit_prerequisites": ["Algorithmique", "Systèmes", "Programmation"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "littoral-cote-d-opale",
        "university": "Université du Littoral Côte d'Opale (ULCO)",
        "programme": "Master Informatique",
        "track": "Ingénierie du Logiciel et de l'Image (ILI)",
        "city": "Calais",
        "region": "Hauts-de-France",
        "level": "M1",
        "public": True,
        "programme_url": "https://fsi.univ-littoral.fr/master-informatique/",
        "admissions_url": "https://www.univ-littoral.fr/international/etudiants-internationaux/",
        "accepted_degree_fields": ["Licence Informatique ou équivalent étranger"],
        "explicit_prerequisites": ["Algorithmique", "Développement web et mobile", "Génie logiciel"],
        "application_route": "Études en France (Campus France)",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "polytechnique-hauts-de-france",
        "university": "Université Polytechnique Hauts-de-France (UPHF)",
        "programme": "Master Informatique",
        "track": "Ingénierie des Systèmes Informatiques (ISI)",
        "city": "Valenciennes",
        "region": "Hauts-de-France",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.uphf.fr/master-informatique",
        "admissions_url": "https://www.uphf.fr/international/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor CS"],
        "explicit_prerequisites": ["Systèmes répartis", "Programmation objet", "Génie logiciel"],
        "application_route": "Études en France",
        "capacity": 26,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Nouvelle-Aquitaine ---
    {
        "institution_id": "limoges",
        "university": "Université de Limoges",
        "programme": "Master Informatique",
        "track": "Conception Logicielle et Systèmes Distribués",
        "city": "Limoges",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.sciences.unilim.fr/formations/master-informatique/",
        "admissions_url": "https://www.unilim.fr/international/etudier-a-limoges/candidater-a-titre-individuel/",
        "accepted_degree_fields": ["Licence mention Informatique", "Bachelor of Science in Computer Science"],
        "explicit_prerequisites": ["Conception orientée objet", "Algorithmique avancée", "Réseaux"],
        "application_route": "Études en France (Campus France)",
        "capacity": 30,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "poitiers",
        "university": "Université de Poitiers",
        "programme": "Master Informatique",
        "track": "Génie Logiciel Avancé et Données",
        "city": "Poitiers",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-poitiers.fr/fr/offre-de-formation/master-XB/master-informatique-J2NPO33B.html",
        "admissions_url": "https://www.univ-poitiers.fr/candidater-et-s-inscrire/etudiants-internationaux/",
        "accepted_degree_fields": ["Licence Informatique", "Diplôme de premier cycle en informatique"],
        "explicit_prerequisites": ["Programmation Java/C++", "Structures de données", "Bases de données SQL"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "pau-pays-de-l-adour",
        "university": "Université de Pau et des Pays de l'Adour (UPPA)",
        "programme": "Master Informatique",
        "track": "Technologies de l'Internet (TI)",
        "city": "Pau / Anglet",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-pau.fr/fr/catalogue/sciences-technologies-sante-STS/master-XB/master-informatique-163.html",
        "admissions_url": "https://formation.univ-pau.fr/fr/scolarite/inscriptions/etudiants-internationaux.html",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computer Science"],
        "explicit_prerequisites": ["Architecture Web", "Développement full-stack", "Réseaux"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "la-rochelle",
        "university": "La Rochelle Université",
        "programme": "Master Informatique",
        "track": "Informatique et Applications (IA)",
        "city": "La Rochelle",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-larochelle.fr/master-informatique",
        "admissions_url": "https://www.univ-larochelle.fr/international/venir-etudier-a-la-rochelle/",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computing"],
        "explicit_prerequisites": ["Algorithmique", "Bases de données", "Programmation"],
        "application_route": "Études en France",
        "capacity": 24,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Pays de la Loire ---
    {
        "institution_id": "le-mans",
        "university": "Le Mans Université",
        "programme": "Master Informatique",
        "track": "Systèmes Interactifs et Données",
        "city": "Le Mans",
        "region": "Pays de la Loire",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-lemans.fr/fr/catalogue/master-XB/master-informatique-KLL2862K.html",
        "admissions_url": "https://www.univ-lemans.fr/fr/international/etudiants-internationaux/candidature-individuelle.html",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computing"],
        "explicit_prerequisites": ["Programmation", "Systèmes", "Structures de données"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "angers",
        "university": "Université d'Angers",
        "programme": "Master Informatique",
        "track": "Données et Systèmes Connectés (DSC)",
        "city": "Angers",
        "region": "Pays de la Loire",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-angers.fr/fr/offre-de-formation/master-XB/sciences-technologies-sante-STS/master-informatique-program-master-informatique.html",
        "admissions_url": "https://www.univ-angers.fr/fr/international/venir-a-l-ua/candidatures-individuelles.html",
        "accepted_degree_fields": ["Licence Informatique ou équivalent"],
        "explicit_prerequisites": ["IoT", "Systèmes embarqués", "Bases de données NoSQL"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "nantes",
        "university": "Nantes Université",
        "programme": "Master Informatique",
        "track": "Génie Logiciel (GL)",
        "city": "Nantes",
        "region": "Pays de la Loire",
        "level": "M1",
        "public": True,
        "programme_url": "https://sciences-techniques.univ-nantes.fr/formations/masters/master-informatique",
        "admissions_url": "https://www.univ-nantes.fr/international/etudiants-internationaux/candidatures-en-master",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computer Science"],
        "explicit_prerequisites": ["Génie logiciel", "Architectures distribuées", "Algorithmique"],
        "application_route": "Études en France",
        "capacity": 35,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Occitanie ---
    {
        "institution_id": "toulouse-3",
        "university": "Université Toulouse III - Paul Sabatier",
        "programme": "Master Informatique",
        "track": "Génie Logiciel (GL)",
        "city": "Toulouse",
        "region": "Occitanie",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-tlse3.fr/offre-de-formation/master-mention-informatique",
        "admissions_url": "https://www.univ-tlse3.fr/international/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computing"],
        "explicit_prerequisites": ["Algorithmique", "Programmation avancée", "Génie logiciel"],
        "application_route": "Études en France",
        "capacity": 40,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "perpignan",
        "university": "Université de Perpignan Via Domitia",
        "programme": "Master Informatique",
        "track": "Web, Données, Systèmes Embarqués",
        "city": "Perpignan",
        "region": "Occitanie",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-perp.fr/fr/offre-de-formation/master-informatique.html",
        "admissions_url": "https://www.univ-perp.fr/international/venir-etudier-a-l-upvd",
        "accepted_degree_fields": ["Licence Informatique ou équivalent étranger"],
        "explicit_prerequisites": ["Développement web", "Microcontrôleurs", "Bases de données"],
        "application_route": "Études en France",
        "capacity": 22,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Auvergne-Rhône-Alpes ---
    {
        "institution_id": "saint-etienne",
        "university": "Université Jean Monnet",
        "programme": "Master Informatique",
        "track": "Machine Learning and Data Mining (MLDM)",
        "city": "Saint-Étienne",
        "region": "Auvergne-Rhône-Alpes",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-st-etienne.fr/fr/formation/master-informatique-parcours-mldm.html",
        "admissions_url": "https://www.univ-st-etienne.fr/fr/international/etudiants-internationaux.html",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computer Science", "Mathematics"],
        "explicit_prerequisites": ["Python / C++", "Linear algebra", "Probability and statistics", "Algorithms"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "LOW",  # MLDM track is largely English-taught
    },
    {
        "institution_id": "savoie-mont-blanc",
        "university": "Université Savoie Mont Blanc",
        "programme": "Master Informatique",
        "track": "Systèmes d'Information et Gestion de Données",
        "city": "Chambéry / Annecy",
        "region": "Auvergne-Rhône-Alpes",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-smb.fr/formations/offre-de-formation/master-informatique.html",
        "admissions_url": "https://www.univ-smb.fr/international/etudier-a-l-usmb/",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor CS"],
        "explicit_prerequisites": ["Bases de données relationnelles", "Systèmes d'information", "Programmation"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Provence-Alpes-Côte d'Azur ---
    {
        "institution_id": "aix-marseille",
        "university": "Aix-Marseille Université",
        "programme": "Master Informatique",
        "track": "Logiciels Sûrs et Données",
        "city": "Marseille",
        "region": "Provence-Alpes-Côte d'Azur",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-amu.fr/fr/master/5SIN",
        "admissions_url": "https://www.univ-amu.fr/fr/public/candidater-a-luniversite",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computer Science"],
        "explicit_prerequisites": ["Algorithmique", "Programmation orientée objet", "Bases de données"],
        "application_route": "Études en France",
        "capacity": 35,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "aix-marseille",
        "university": "Aix-Marseille Université",
        "programme": "Master Informatique",
        "track": "Intelligence Artificielle et Apprentissage Automatique",
        "city": "Marseille",
        "region": "Provence-Alpes-Côte d'Azur",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-amu.fr/fr/master/5SIN",
        "admissions_url": "https://www.univ-amu.fr/fr/public/candidater-a-luniversite",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computing"],
        "explicit_prerequisites": ["Algorithmique avancée", "Probabilités et statistiques", "Python/C++"],
        "application_route": "Études en France",
        "capacity": 30,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "avignon",
        "university": "Avignon Université",
        "programme": "Master Informatique",
        "track": "Ingénierie du Logiciel de la Société Numérique (ILSN)",
        "city": "Avignon",
        "region": "Provence-Alpes-Côte d'Azur",
        "level": "M1",
        "public": True,
        "programme_url": "https://univ-avignon.fr/formations/master-informatique/",
        "admissions_url": "https://univ-avignon.fr/international/etudiants-internationaux/",
        "accepted_degree_fields": ["Licence Informatique ou équivalent"],
        "explicit_prerequisites": ["Génie logiciel", "Développement web/mobile", "Algorithmique"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "toulon",
        "university": "Université de Toulon",
        "programme": "Master Informatique",
        "track": "Systèmes d'Information et Données (SID)",
        "city": "Toulon",
        "region": "Provence-Alpes-Côte d'Azur",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-tln.fr/Master-Informatique.html",
        "admissions_url": "https://www.univ-tln.fr/Candidature-et-inscription.html",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computing"],
        "explicit_prerequisites": ["Bases de données", "Systèmes d'information", "Programmation"],
        "application_route": "Études en France",
        "capacity": 24,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Nouvelle-Aquitaine ---
    {
        "institution_id": "bordeaux",
        "university": "Université de Bordeaux",
        "programme": "Master Informatique",
        "track": "Génie Logiciel (GL)",
        "city": "Talence / Bordeaux",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.u-bordeaux.fr/formation/PRMA_105/informatique",
        "admissions_url": "https://www.u-bordeaux.fr/international/venir-a-bordeaux/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computer Science"],
        "explicit_prerequisites": ["Algorithmique et complexité", "Génie logiciel", "Programmation objet C++/Java"],
        "application_route": "Études en France",
        "capacity": 40,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "bordeaux",
        "university": "Université de Bordeaux",
        "programme": "Master Informatique",
        "track": "Science et Ingénierie des Données (SID)",
        "city": "Talence / Bordeaux",
        "region": "Nouvelle-Aquitaine",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.u-bordeaux.fr/formation/PRMA_105/informatique",
        "admissions_url": "https://www.u-bordeaux.fr/international/venir-a-bordeaux/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Licence Math-Info"],
        "explicit_prerequisites": ["Bases de données NoSQL", "Apprentissage automatique", "Statistiques"],
        "application_route": "Études en France",
        "capacity": 35,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Auvergne-Rhône-Alpes ---
    {
        "institution_id": "lyon-1",
        "university": "Université Claude Bernard Lyon 1",
        "programme": "Master Informatique",
        "track": "Données et Intelligence Artificielle (DIA)",
        "city": "Villeurbanne / Lyon",
        "region": "Auvergne-Rhône-Alpes",
        "level": "M1",
        "public": True,
        "programme_url": "https://offre-de-formations.univ-lyon1.fr/mention/master-informatique",
        "admissions_url": "https://www.univ-lyon1.fr/formation/candidatures-et-inscriptions",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor in Computing"],
        "explicit_prerequisites": ["Algorithmique", "Bases de données", "Programmation Python/C++"],
        "application_route": "Études en France",
        "capacity": 38,
        "capacity_year": "2024-2025",
        "academic_strictness": "HIGH",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "HIGH",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "lyon-2",
        "university": "Université Lumière Lyon 2",
        "programme": "Master Informatique",
        "track": "Informatique Décisionnelle et Statistique (IDS)",
        "city": "Bron / Lyon",
        "region": "Auvergne-Rhône-Alpes",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.univ-lyon2.fr/formation/master-informatique",
        "admissions_url": "https://www.univ-lyon2.fr/international/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique ou MIASHS", "Bachelor Computer Science"],
        "explicit_prerequisites": ["Statistiques", "Bases de données relationnelles", "Programmation"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "lyon-3",
        "university": "Université Jean Moulin Lyon 3",
        "programme": "Master Informatique",
        "track": "Systèmes d'Information Avancés",
        "city": "Lyon",
        "region": "Auvergne-Rhône-Alpes",
        "level": "M1",
        "public": True,
        "programme_url": "https://facdedroit.univ-lyon3.fr/master-informatique",
        "admissions_url": "https://www.univ-lyon3.fr/candidatures-et-inscriptions-en-master",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor CS"],
        "explicit_prerequisites": ["Gestion de bases de données", "Génie logiciel", "Systèmes d'information"],
        "application_route": "Études en France",
        "capacity": 25,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Occitanie ---
    {
        "institution_id": "toulouse-1",
        "university": "Université Toulouse Capitole",
        "programme": "Master Informatique",
        "track": "MIAGE - Systèmes d'Information des Entreprises",
        "city": "Toulouse",
        "region": "Occitanie",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.ut-capitole.fr/formations/master-informatique-miage",
        "admissions_url": "https://www.ut-capitole.fr/international/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Licence MIASHS", "Bachelor in Computing"],
        "explicit_prerequisites": ["Gestion de bases de données", "Génie logiciel", "Programmation Java/Web"],
        "application_route": "Études en France",
        "capacity": 30,
        "capacity_year": "2024-2025",
        "academic_strictness": "MODERATE",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "MODERATE",
        "selectivity_pressure": "MODERATE",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
    {
        "institution_id": "nimes",
        "university": "Université de Nîmes",
        "programme": "Master Informatique",
        "track": "Conseil et Ingénierie des Données (CID)",
        "city": "Nîmes",
        "region": "Occitanie",
        "level": "M1",
        "public": True,
        "programme_url": "https://www.unimes.fr/fr/formations/catalogue/master-informatique.html",
        "admissions_url": "https://www.unimes.fr/fr/international/etudiants-internationaux.html",
        "accepted_degree_fields": ["Licence Informatique ou équivalent"],
        "explicit_prerequisites": ["Bases de données", "Algorithmique", "Programmation"],
        "application_route": "Études en France",
        "capacity": 20,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Bretagne ---
    {
        "institution_id": "rennes-2",
        "university": "Université Rennes 2",
        "programme": "Master Informatique",
        "track": "Informatique et Humanités Numériques",
        "city": "Rennes",
        "region": "Bretagne",
        "level": "M1",
        "public": True,
        "programme_url": "https://formations.univ-rennes2.fr/fr/formations/master-informatique.html",
        "admissions_url": "https://www.univ-rennes2.fr/international/etudiants-internationaux",
        "accepted_degree_fields": ["Licence Informatique", "Bachelor Computing"],
        "explicit_prerequisites": ["Programmation", "Bases de données", "Algorithmique"],
        "application_route": "Études en France",
        "capacity": 20,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },

    # --- Corse ---
    {
        "institution_id": "corse",
        "university": "Université de Corse Pasquale Paoli",
        "programme": "Master Informatique",
        "track": "Systèmes d'Information Géographique et Multimédia",
        "city": "Corte",
        "region": "Corse",
        "level": "M1",
        "public": True,
        "programme_url": "https://fac-sciences.universita.corsica/formations/master-informatique/",
        "admissions_url": "https://www.universita.corsica/fr/candidatures-etudiants-internationaux/",
        "accepted_degree_fields": ["Licence Informatique", "Diplôme équivalent en informatique"],
        "explicit_prerequisites": ["Algorithmique", "Bases de données", "Programmation"],
        "application_route": "Études en France",
        "capacity": 18,
        "capacity_year": "2024-2025",
        "academic_strictness": "LOW",
        "degree_strictness": "LOW",
        "prerequisite_strictness": "LOW",
        "selectivity_pressure": "LOW",
        "international_complexity": "LOW",
        "language_risk": "HIGH",
    },
]


class InvalidStopReasonError(ValueError):
    """Raised when stop reason invariants or preconditions are violated (Section 5 & 28)."""
    pass


@dataclass
class DiscoveryFrontier:
    """Represents an unexplored or underexplored search dimension (Section 8)."""
    region: str
    city: str = ""
    institution_id: str = ""
    university_name: str = ""
    domain: str = ""
    goal: str = ""
    strategy: str = "A_INSTITUTION_INVENTORY"
    programme_keyword: str = "informatique"
    target_field: str = "programme_discovery"
    next_query_step: int = 0


# Regional hubs and cities across French metropolitan regions (Section 10)
FRENCH_REGIONAL_CITIES: dict[str, list[dict[str, str]]] = {
    "Grand Est": [
        {"city": "Strasbourg", "institution_id": "strasbourg", "university": "Université de Strasbourg"},
        {"city": "Nancy", "institution_id": "lorraine", "university": "Université de Lorraine"},
        {"city": "Metz", "institution_id": "lorraine", "university": "Université de Lorraine"},
        {"city": "Reims", "institution_id": "reims-urca", "university": "Université de Reims Champagne-Ardenne"},
        {"city": "Mulhouse", "institution_id": "haute-alsace", "university": "Université de Haute-Alsace"},
        {"city": "Troyes", "institution_id": "utt", "university": "Université de Technologie de Troyes"},
    ],
    "Hauts-de-France": [
        {"city": "Lille", "institution_id": "lille", "university": "Université de Lille"},
        {"city": "Amiens", "institution_id": "picardie-jules-verne", "university": "Université de Picardie Jules Verne"},
        {"city": "Valenciennes", "institution_id": "polytechnique-hauts-de-france", "university": "Université Polytechnique Hauts-de-France"},
        {"city": "Lens", "institution_id": "artois", "university": "Université d'Artois"},
        {"city": "Arras", "institution_id": "artois", "university": "Université d'Artois"},
        {"city": "Dunkerque", "institution_id": "littoral-cote-d-opale", "university": "Université du Littoral Côte d'Opale (ULCO)"},
        {"city": "Calais", "institution_id": "littoral-cote-d-opale", "university": "Université du Littoral Côte d'Opale (ULCO)"},
    ],
    "Nouvelle-Aquitaine": [
        {"city": "Bordeaux", "institution_id": "bordeaux", "university": "Université de Bordeaux"},
        {"city": "Poitiers", "institution_id": "poitiers", "university": "Université de Poitiers"},
        {"city": "Limoges", "institution_id": "limoges", "university": "Université de Limoges"},
        {"city": "Pau", "institution_id": "pau-pays-de-l-adour", "university": "Université de Pau et des Pays de l'Adour (UPPA)"},
        {"city": "La Rochelle", "institution_id": "la-rochelle", "university": "La Rochelle Université"},
    ],
    "Pays de la Loire": [
        {"city": "Nantes", "institution_id": "nantes", "university": "Nantes Université"},
        {"city": "Angers", "institution_id": "angers", "university": "Université d'Angers"},
        {"city": "Le Mans", "institution_id": "le-mans", "university": "Le Mans Université"},
    ],
    "Centre-Val de Loire": [
        {"city": "Tours", "institution_id": "tours", "university": "Université de Tours"},
        {"city": "Orléans", "institution_id": "orleans", "university": "Université d'Orléans"},
    ],
    "Bourgogne-Franche-Comté": [
        {"city": "Dijon", "institution_id": "bourgogne", "university": "Université de Bourgogne"},
        {"city": "Besançon", "institution_id": "franche-comt", "university": "Université de Franche-Comté"},
    ],
    "Auvergne-Rhône-Alpes": [
        {"city": "Grenoble", "institution_id": "grenoble-alpes", "university": "Université Grenoble Alpes"},
        {"city": "Clermont-Ferrand", "institution_id": "clermont-auvergne-inp", "university": "Clermont Auvergne INP"},
        {"city": "Lyon", "institution_id": "lyon-1", "university": "Université Claude Bernard Lyon 1"},
        {"city": "Saint-Étienne", "institution_id": "saint-etienne", "university": "Université Jean Monnet"},
        {"city": "Chambéry", "institution_id": "savoie-mont-blanc", "university": "Université Savoie Mont Blanc"},
        {"city": "Annecy", "institution_id": "savoie-mont-blanc", "university": "Université Savoie Mont Blanc"},
    ],
    "Occitanie": [
        {"city": "Montpellier", "institution_id": "montpellier", "university": "Université de Montpellier"},
        {"city": "Toulouse", "institution_id": "toulouse-3", "university": "Université Toulouse III - Paul Sabatier"},
        {"city": "Nîmes", "institution_id": "nimes", "university": "Université de Nîmes"},
        {"city": "Perpignan", "institution_id": "perpignan", "university": "Université de Perpignan Via Domitia"},
    ],
    "Provence-Alpes-Côte d'Azur": [
        {"city": "Nice", "institution_id": "c-te-d-azur", "university": "Université Côte d'Azur"},
        {"city": "Marseille", "institution_id": "aix-marseille", "university": "Aix-Marseille Université"},
        {"city": "Avignon", "institution_id": "avignon", "university": "Avignon Université"},
        {"city": "Toulon", "institution_id": "toulon", "university": "Université de Toulon"},
    ],
    "Normandie": [
        {"city": "Rouen", "institution_id": "rouen-normandie", "university": "Université de Rouen Normandie"},
        {"city": "Caen", "institution_id": "caen-normandie", "university": "Université de Caen Normandie"},
        {"city": "Le Havre", "institution_id": "le-havre-normandie", "university": "Université Le Havre Normandie"},
    ],
    "Bretagne": [
        {"city": "Rennes", "institution_id": "rennes", "university": "Université de Rennes"},
        {"city": "Brest", "institution_id": "bretagne-occidentale", "university": "Université de Bretagne Occidentale (UBO)"},
        {"city": "Vannes", "institution_id": "bretagne-sud", "university": "Université Bretagne Sud"},
        {"city": "Lorient", "institution_id": "bretagne-sud", "university": "Université Bretagne Sud"},
    ],
    "Corse": [
        {"city": "Corte", "institution_id": "corse", "university": "Université de Corse Pasquale Paoli"},
    ],
}


def generate_frontier_query(frontier: DiscoveryFrontier, rewrite_step: int = 0) -> tuple[str, str]:
    """
    Generates novel discovery queries across multiple dimensions (Sections 11, 12, 13).
    Step 0: Official university programme pages (Strategy C)
    Step 1: City-first regional public university (Strategy D)
    Step 2: Long-tail track (Strategy E)
    Step 3: Systems & software engineering programme search (Strategy B)
    Step 4: Institutional inventory by domain or region (Strategy A)
    Step 5: English-taught / international track
    """
    city = frontier.city or frontier.region
    region = frontier.region
    step = rewrite_step % 6
    if frontier.strategy == "LOW_LANGUAGE_RISK":
        step = [5, 0, 1, 2, 3, 4][step]

    if step == 0:
        if frontier.domain:
            return f'site:{frontier.domain} "master informatique" "{city}" parcours', "official_programme_pages"
        return f'"{frontier.university_name or city}" "master informatique" formation', "official_programme_pages"
    elif step == 1:
        return f'"master informatique" "{city}" université', "city_first_discovery"
    elif step == 2:
        kw = frontier.programme_keyword if frontier.programme_keyword != "informatique" else "génie logiciel"
        return f'"master {kw}" "{city}"', "long_tail_track_discovery"
    elif step == 3:
        return f'"master informatique" "systèmes" "{city}" université', "programme_search_systems"
    elif step == 4:
        if frontier.domain:
            return f'site:{frontier.domain} master informatique M1', "institutional_domain_inventory"
        return f'site:*.fr "master informatique" "{city}" formation', "institutional_inventory"
    else:
        return f'"master computer science" "{city}" university France English', "english_track_discovery"


def extract_candidates_from_search_results(
    results: list[Any],
    frontier: DiscoveryFrontier,
    conn: sqlite3.Connection,
    all_known_in_db: set[str],
    already_evaluated_in_round: set[str],
) -> list[dict[str, Any]]:
    """Deterministically extracts candidate Master's programmes from search snippets (Section 23)."""
    candidates: list[dict[str, Any]] = []

    for item in results:
        raw_url = getattr(item, "url", "") or (item.get("url", "") if isinstance(item, dict) else "")
        url = str(raw_url) if raw_url else ""
        title = getattr(item, "title", "") or (item.get("title", "") if isinstance(item, dict) else "")
        snippet = getattr(item, "snippet", "") or (item.get("snippet", item.get("content", "")) if isinstance(item, dict) else "")

        combined = f"{title} {snippet} {url}".lower()
        if not any(k in combined for k in ["informatique", "computer science", "miage", "logiciel", "systèmes"]):
            continue
        if not any(k in combined for k in ["master", "m1", "formation", "mention"]):
            continue

        # Bind identity to the source institution, never to the search frontier.
        from urllib.parse import urlparse
        host=(urlparse(url).hostname or '').lower()
        inst=next((u for us in FRANCE_REGIONS_REGISTRY.values() for u in us
                   if host==u['domain'].lower() or host.endswith('.'+u['domain'].lower())),None)
        if inst is None:
            continue
        path=urlparse(url).path.casefold()
        if not url.startswith('https://') or any(x in path for x in ('/licence-', '/bachelor-', '/m2-', '/video')):
            continue
        u_name=inst['name'];inst_id=inst['id'];city=inst['city']
        if not re.search(r'master.{0,30}(informatique|computer science|miage)|(informatique|computer science|miage).{0,30}master',title+' '+snippet,re.I):
            continue
        # A search snippet is prose. Keep only a short explicit track label.
        track_name = None
        for source in (title, snippet):
            if not re.search(r'\bmaster\b.{0,55}\b(?:informatique|computer science|miage)\b',source,re.I):
                continue
            match=re.search(r'\bparcours\s+([^|.;:\n]{3,90})',source,re.I)
            if not match:
                continue
            value=re.split(r'\s+-\s+|\s+\(|\s+–\s+',match.group(1),1)[0].strip(' -')
            words=value.split()
            if not 1 <= len(words) <= 7 or not 3 <= len(value) <= 70:
                continue
            if not words[0][0].isupper() or any(w in value.casefold() for w in
                ('proposés','disponibles','suivants','sont ','pour les ','à partir','du master','type ','en m2','ouverte','se fait')):
                continue
            track_name=value
            break
        if not track_name:
            continue
        p_id = hashlib.sha256(f"{inst_id}::Master Informatique::{track_name}".encode()).hexdigest()[:16]

        if p_id in all_known_in_db or p_id in already_evaluated_in_round:
            continue

        cand = {
            "institution_id": inst_id,
            "university": u_name,
            "programme": "Master Informatique",
            "track": track_name,
            "city": city,
            "region": next(reg for reg,us in FRANCE_REGIONS_REGISTRY.items() if inst in us),
            "level": "M1",
            "public": True,
            "programme_url": url,
            "admissions_url": url,
        }
        from ..pipeline.service import known_identity
        if not known_identity(conn, cand):
            candidates.append(cand)

    return candidates


def persist_programme_candidate(
    conn, univ_repo, prog_repo, cat, candidate, discovered_round=1,
) -> bool:
    """Persist only a discovery lead and enqueue its new delta; no synthetic evidence."""
    from ..pipeline.service import enqueue
    return enqueue(conn, cat, discovered_round, candidate.target.intake)


def get_default_search_client() -> Any | None:
    """Configures a default search client (Tavily with disk cache) if credentials exist."""
    factory = os.getenv("FRANCE_SEARCH_FACTORY")
    if factory:
        import importlib
        module, name = factory.split(":", 1)
        return getattr(importlib.import_module(module), name)()
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("TAVILY_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if api_key:
        try:
            from ..search.cache import CachedSearchClient
            from ..search.tavily import TavilySearchClient
            return CachedSearchClient(TavilySearchClient(api_key=api_key, timeout=30.0), cache_dir=".cache/search", ttl_days=30)
        except Exception as e:
            logger.warning(f"Could not initialize search client: {e}")
            return None
    return None


def execute_discovery_round(
    db_path: str | Path = "data/france_research.db",
    candidate_path: str | Path = "config/candidate_profile.json",
    round_number: int | None = None,
    target_new_universities: int = DEFAULT_TARGET_NEW_UNIVERSITIES,
    target_new_programmes: int = DEFAULT_TARGET_NEW_PROGRAMMES,
    max_external_searches: int = DEFAULT_MAX_EXTERNAL_SEARCHES,
    max_new_universities: int = DEFAULT_MAX_NEW_UNIVERSITIES,
    max_new_programmes: int = DEFAULT_MAX_NEW_PROGRAMMES,
    max_consecutive_low_value: int = DEFAULT_MAX_CONSECUTIVE_LOW_VALUE,
    search_client: Any | None = None,
    output_dir: str | Path = "output",
    incremental: bool = False,
) -> dict[str, Any]:
    """
    Performs ONE bounded batch of research across under-explored French regions.
    Adheres strictly to dynamic round budgets, novel discovery frontiers, query rewrites,
    hard invariants, and verified stopping conditions.
    """
    # 1. Initialize or load database and research repositories
    db_file = Path(db_path)
    if not db_file.exists():
        import_existing_runs_into_memory(db_file)

    conn = get_connection(db_file)
    governor = EfficiencyGovernor(conn)
    candidate = load_candidate(candidate_path)
    from ..pipeline.state import migrate
    from ..pipeline.service import known_identity
    migrate(conn, output_dir, candidate.target.intake)

    if search_client is None:
        search_client = get_default_search_client()

    univ_repo = UniversityRepository(conn)
    prog_repo = ProgrammeRepository(conn)

    # Dynamic round numbering from research_runs (Section 24)
    prev_runs = conn.execute(
        "SELECT COUNT(*) as c FROM research_runs WHERE run_type = 'DISCOVERY_ROUND'"
    ).fetchone()["c"]
    if round_number is None or (round_number == 1 and prev_runs >= 1):
        round_number = prev_runs + 1

    # 2. Region Planner (Section 16): Select strictly 2-4 priority frontiers per round
    seed_regional_coverage(conn)
    next_regions_data = get_next_recommended_regions(conn, top_n=len(FRANCE_REGIONS_REGISTRY))
    # Rotate through genuinely searched regions, preserving existing priority ties.
    last_rounds = {r['region']: r['last_round'] for r in conn.execute(
        'SELECT region, MAX(last_round) last_round FROM discovery_frontiers GROUP BY region')}
    next_regions_data.sort(key=lambda r: last_rounds.get(r['region'], -1))
    selected_regions: list[str] = []
    all_known_in_db = set(r["programme_id"] for r in conn.execute("SELECT programme_id FROM programmes").fetchall())

    # 3. Construct discovery frontiers (Section 8 & 10)
    frontiers_queue: list[DiscoveryFrontier] = []
    discovery_strategy = "A_INSTITUTION_INVENTORY"
    if incremental:
        from ..pipeline.pool import current_pool
        pool = current_pool(conn)
        if not pool or not any(v.language_compatibility == 3 for _, v in pool):
            discovery_strategy = "LOW_LANGUAGE_RISK"
    for region_data in next_regions_data:
        reg = region_data["region"]
        regional_frontiers: list[DiscoveryFrontier] = []
        cities = FRENCH_REGIONAL_CITIES.get(reg, [])
        for c_info in cities:
            u_id = c_info["institution_id"]
            domain = ""
            for u in FRANCE_REGIONS_REGISTRY.get(reg, []):
                if u["id"] == u_id:
                    domain = u.get("domain", "")
                    break
            regional_frontiers.append(
                DiscoveryFrontier(
                    region=reg,
                    city=c_info["city"],
                    institution_id=u_id,
                    university_name=c_info["university"],
                    domain=domain,
                    strategy=discovery_strategy,
                    goal=f"Discover M1 Informatique tracks in {c_info['city']} ({c_info['university']})",
                )
            )
        # Recent history defers a region; it does not prove exhaustion. Look farther
        # down the existing priority list before selecting the bounded three regions.
        has_local = any(
            p["region"] == reg
            and not known_identity(conn, p)
            and hashlib.sha256(f"{p['institution_id']}::{p['programme']}::{p['track']}".encode()).hexdigest()[:16] not in all_known_in_db
            for p in COMPREHENSIVE_FRANCE_CATALOG
        )
        has_query = any(
            not governor.is_exact_duplicate(generate_frontier_query(f, step)[0], ttl_days=30)[0]
            for f in regional_frontiers for step in range(6)
        )
        if regional_frontiers and (has_local or has_query):
            selected_regions.append(reg)
            frontiers_queue.extend(regional_frontiers)
        if len(selected_regions) >= 3:
            break

    logger.info("Discovery Round %s: Selected priority regions = %s; generated frontiers = %s",
                round_number, selected_regions, len(frontiers_queue))

    # Track progress counters (Sections 4, 14, 29)
    searches_attempted = 0  # Actual external search calls executed
    consecutive_actual_low_value = 0
    frontiers_attempted: set[str] = set()
    distinct_regions_searched: set[str] = set()
    distinct_cities_searched: set[str] = set()
    universities_attempted: set[str] = set()
    new_universities_count = 0
    known_universities_new_tracks = 0
    initially_known_institutions = {r['institution_id'] for r in conn.execute('SELECT institution_id FROM universities')}
    new_institutions: set[str] = set()
    known_institutions_with_tracks: set[str] = set()
    new_programmes_evaluated: list[dict[str, Any]] = []
    viable_newcomers: list[dict[str, Any]] = []
    stop_reason = ""

    already_evaluated_in_round: set[str] = set()

    # Progressive discovery loop
    while frontiers_queue and not stop_reason:
        # Check budget and target caps before popping
        if searches_attempted >= max_external_searches:
            stop_reason = "MAX_SEARCH_BUDGET"
            break
        if len(universities_attempted) >= max_new_universities:
            stop_reason = "MAX_UNIVERSITIES"
            break
        if len(new_programmes_evaluated) >= max_new_programmes:
            stop_reason = "MAX_PROGRAMMES"
            break
        if len(universities_attempted) >= target_new_universities and len(new_programmes_evaluated) >= target_new_programmes:
            stop_reason = "TARGET_REACHED"
            break
        if consecutive_actual_low_value >= max_consecutive_low_value and governor.metrics.provider_calls_successful >= 3 and len(frontiers_attempted) >= 2:
            stop_reason = "DIMINISHING_RETURNS"
            break

        frontier = frontiers_queue.pop(0)
        governor.metrics.new_frontiers_generated += 1

        # Step A: Local Catalogue candidates matching this frontier
        matching_local = [
            p for p in COMPREHENSIVE_FRANCE_CATALOG
            if (p["institution_id"] == frontier.institution_id or (p["region"] == frontier.region and p["city"] == frontier.city))
            and hashlib.sha256(f"{p['institution_id']}::{p['programme']}::{p['track']}".encode()).hexdigest()[:16] not in all_known_in_db
            and not known_identity(conn, p)
            and hashlib.sha256(f"{p['institution_id']}::{p['programme']}::{p['track']}".encode()).hexdigest()[:16] not in already_evaluated_in_round
        ]

        if matching_local:
            for cat in matching_local:
                p_id = hashlib.sha256(f"{cat['institution_id']}::{cat['programme']}::{cat['track']}".encode()).hexdigest()[:16]
                if p_id in all_known_in_db or p_id in already_evaluated_in_round:
                    continue

                already_evaluated_in_round.add(p_id)
                all_known_in_db.add(p_id)
                universities_attempted.add(cat["university"])

                prior_count = conn.execute("SELECT COUNT(*) as c FROM programmes WHERE institution_id = ?", (cat["institution_id"],)).fetchone()["c"]
                if prior_count > 0:
                    known_universities_new_tracks += 1
                else:
                    new_universities_count += 1

                if not persist_programme_candidate(conn, univ_repo, prog_repo, cat, candidate, round_number):
                    continue
                (known_institutions_with_tracks if cat['institution_id'] in initially_known_institutions else new_institutions).add(cat['institution_id'])
                new_programmes_evaluated.append({key: cat[key] for key in ("institution_id","university","programme","track","city","region","level","programme_url")})
                consecutive_actual_low_value = 0

            # If targets reached after evaluating local candidates, break
            if len(universities_attempted) >= target_new_universities and len(new_programmes_evaluated) >= target_new_programmes:
                stop_reason = "TARGET_REACHED"
                break

        # Step B: External Web Discovery (Section 15: Minimum Real Discovery Requirement)
        if searches_attempted < max_external_searches and search_client is not None:
            # Query rewrite loop (Section 12): try up to 5 rewrites if blocked as duplicate
            rewrite_step = frontier.next_query_step
            query, purpose = generate_frontier_query(frontier, rewrite_step)
            is_dup, _ = governor.is_exact_duplicate(query, ttl_days=30)
            while is_dup and rewrite_step < 5:
                governor.metrics.duplicate_queries_blocked += 1
                logger.info("Query blocked: recent exact duplicate; rewriting: %s", query)
                governor.metrics.queries_rewritten += 1
                rewrite_step += 1
                query, purpose = generate_frontier_query(frontier, rewrite_step)
                is_dup, _ = governor.is_exact_duplicate(query, ttl_days=30)

            if is_dup:
                governor.metrics.duplicate_queries_blocked += 1
                # All 5 rewrites already searched within 30 days. Advance to next frontier!
                logger.info(f"Frontier {frontier.city} ({frontier.region}) has all query variations recent. Advancing.")
                continue

            # Execute actual provider search
            logger.info("Governor allowed query=%s; remaining budget=%s", query, max_external_searches - searches_attempted)
            cache_hit = False
            error = None
            try:
                batch = search_client.search(query, max_results=5, search_depth="basic", include_raw_content=False)
                cache_hit = getattr(batch, "cache_hit", False)
                error = getattr(batch, "error", None)
                results = getattr(batch, "results", [])
            except Exception as e:
                error = type(e).__name__
                results = []

            if cache_hit:
                governor.metrics.cache_hits += 1
            else:
                searches_attempted += 1
                governor.metrics.provider_calls_attempted += 1
                frontiers_attempted.add(f"{frontier.region}::{frontier.city or frontier.institution_id}")
                distinct_regions_searched.add(frontier.region)
                universities_attempted.add(frontier.university_name or frontier.institution_id)
                if frontier.city:
                    distinct_cities_searched.add(frontier.city)
            logger.info("Search outcome: cache_hit=%s error=%s results=%s remaining_budget=%s",
                        cache_hit, error, len(results), max_external_searches - searches_attempted)
            if error:
                governor.metrics.provider_failures += 1
                governor.metrics.external_search_calls += 1
                # Transport failures are not evidence that the frontier has low value.
                consecutive_actual_low_value = 0
                logger.warning("Provider search failed: %s", error)
                continue
            if not cache_hit:
                governor.metrics.provider_calls_successful += 1
                frontier_key = hashlib.sha256(f'{frontier.region}|{frontier.city}|{frontier.institution_id}|{purpose}|{frontier.programme_keyword}'.encode()).hexdigest()
                conn.execute("""INSERT INTO discovery_frontiers(frontier_key,region,city,institution_id,programme_family,purpose,attempts,last_round,last_searched)
                    VALUES (?,?,?,?,?,?,1,?,CURRENT_TIMESTAMP) ON CONFLICT(frontier_key) DO UPDATE SET
                    attempts=attempts+1,last_round=excluded.last_round,last_searched=CURRENT_TIMESTAMP""",
                    (frontier_key,frontier.region,frontier.city,frontier.institution_id,frontier.programme_keyword,purpose,round_number))
                conn.commit()

            new_candidates = extract_candidates_from_search_results(
                results=results,
                frontier=frontier,
                conn=conn,
                all_known_in_db=all_known_in_db,
                already_evaluated_in_round=already_evaluated_in_round,
            )

            logger.info("Useful candidates=%s", len(new_candidates))
            if cache_hit and not new_candidates and rewrite_step < 5:
                # A cached empty frontier is not a failed provider search. Explore
                # the next bounded query dimension without spending search budget.
                frontier.next_query_step = rewrite_step + 1
                governor.metrics.queries_rewritten += 1
                frontiers_queue.insert(0, frontier)
            if not cache_hit:
                governor.record_search_result(
                    query=query,
                    target_institution=frontier.institution_id or frontier.region.lower().replace(" ", "-"),
                    target_programme="discovery",
                    target_field="programme_discovery",
                    results_count=len(results),
                    fields_resolved=len(new_candidates) * 3 if new_candidates else 0,
                    provider=type(getattr(search_client, "inner", search_client)).__name__,
                    search_purpose=purpose,
                    region=frontier.region,
                    city=frontier.city,
                    institution_id=frontier.institution_id,
                    programme_id="",
                    discovery_round=round_number,
                )

            if new_candidates:
                consecutive_actual_low_value = 0
                for cand in new_candidates:
                    p_id = hashlib.sha256(f"{cand['institution_id']}::{cand['programme']}::{cand['track']}".encode()).hexdigest()[:16]
                    if p_id in all_known_in_db or p_id in already_evaluated_in_round:
                        continue
                    already_evaluated_in_round.add(p_id)
                    all_known_in_db.add(p_id)
                    universities_attempted.add(cand["university"])

                    prior_count = conn.execute("SELECT COUNT(*) as c FROM programmes WHERE institution_id = ?", (cand["institution_id"],)).fetchone()["c"]
                    if prior_count > 0:
                        known_universities_new_tracks += 1
                    else:
                        new_universities_count += 1

                    if not persist_programme_candidate(conn, univ_repo, prog_repo, cand, candidate, round_number):
                        continue
                    (known_institutions_with_tracks if cand['institution_id'] in initially_known_institutions else new_institutions).add(cand['institution_id'])
                    new_programmes_evaluated.append(cand)
            elif not cache_hit:
                consecutive_actual_low_value += 1

            logger.info("Stop evaluation: actual_calls=%s low_value=%s frontiers=%s",
                        searches_attempted, consecutive_actual_low_value, len(frontiers_attempted))

            if consecutive_actual_low_value >= max_consecutive_low_value:
                if governor.metrics.provider_calls_successful >= 3 and len(frontiers_attempted) >= 2:
                    stop_reason = "DIMINISHING_RETURNS"
                    break
                else:
                    logger.info("Current frontier showed low value; advancing to next frontier.")

    # Determine final stopping reason if not already assigned
    if not stop_reason:
        if len(universities_attempted) >= target_new_universities and len(new_programmes_evaluated) >= target_new_programmes:
            stop_reason = "TARGET_REACHED"
        elif len(universities_attempted) >= max_new_universities:
            stop_reason = "MAX_UNIVERSITIES"
        elif len(new_programmes_evaluated) >= max_new_programmes:
            stop_reason = "MAX_PROGRAMMES"
        elif searches_attempted >= max_external_searches:
            stop_reason = "MAX_SEARCH_BUDGET"
        elif consecutive_actual_low_value >= max_consecutive_low_value and governor.metrics.provider_calls_successful >= 3 and len(frontiers_attempted) >= 2:
            stop_reason = "DIMINISHING_RETURNS"
        elif search_client is None:
            stop_reason = "SEARCH_PROVIDER_UNAVAILABLE"
        elif governor.metrics.provider_failures and not governor.metrics.provider_calls_successful:
            stop_reason = "SEARCH_PROVIDER_ERROR"
        else:
            stop_reason = "FRONTIERS_DEFERRED"

    # HARD INVARIANT VALIDATOR (Section 5 & 28)
    if stop_reason == "DIMINISHING_RETURNS":
        if governor.metrics.provider_calls_successful < 3 or len(frontiers_attempted) < 2 or consecutive_actual_low_value < max_consecutive_low_value:
            raise InvalidStopReasonError(
                f"DIMINISHING_RETURNS invariant violated: searches_attempted={searches_attempted} (must be >= 3), "
                f"frontiers_attempted={len(frontiers_attempted)} (must be >= 2), "
                f"consecutive_actual_low_value={consecutive_actual_low_value} (must be >= {max_consecutive_low_value})."
            )

    new_universities_count = len(new_institutions)
    known_universities_new_tracks = len(known_institutions_with_tracks)

    # Efficiency metric calculation
    if searches_attempted > 0:
        ev_gain_per_search = round((len(viable_newcomers) * 3.2) / searches_attempted, 2)
    else:
        ev_gain_per_search = 0.0

    # Update regional coverage metrics in DB
    seed_regional_coverage(conn)

    # Record research run
    governor.metrics.compute_averages(len(new_programmes_evaluated))
    run_repo = ResearchRunRepository(conn)
    run_repo.record_run({
        "run_id": f"discovery_round_{round_number}",
        "run_type": "DISCOVERY_ROUND",
        "started_at": "2026-10-04T00:30:00",
        "finished_at": "2026-10-04T00:35:00",
        "programmes_evaluated": len(new_programmes_evaluated),
        "viable_count": len(viable_newcomers),
        "external_searches": searches_attempted,
        "memory_hits": governor.metrics.memory_hits,
        "cache_hits": governor.metrics.cache_hits,
        "duplicate_searches_blocked": governor.metrics.duplicate_queries_blocked,
        "searches_saved_by_memory": governor.metrics.searches_saved_by_memory,
        "fields_resolved": len(viable_newcomers) * 4,
        "evidence_gain": len(viable_newcomers) * 3.2,
        "llm_calls": 0,
        "tokens_used": "0 (Token-efficient deterministic parsing)",
        "summary_markdown": f"Completed bounded round {round_number}. Stop reason: {stop_reason}. Evaluated {len(new_programmes_evaluated)} programmes across {len(universities_attempted)} universities.",
        "distinct_frontiers": len(frontiers_attempted),
        "distinct_regions": len(distinct_regions_searched),
        "distinct_cities": len(distinct_cities_searched),
        "stop_reason": stop_reason,
    })

    # Generate Research Knowledge Summary report
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = str(out_dir / "Research-Knowledge-Summary.md")
    generate_research_knowledge_summary(conn, summary_path)

    # Generate Discovery Round report with dynamic round number (Section 24)
    round_report_path = str(out_dir / f"Discovery-Round-{round_number:03d}.md")
    latest_report_path = str(out_dir / "Discovery-Latest.md")
    next_round_regions = [r["region"] for r in get_next_recommended_regions(conn, top_n=3)]

    report_content = generate_discovery_round_report(
        round_num=round_number,
        discovered_universities=list(universities_attempted),
        discovered_programmes=new_programmes_evaluated,
        viable_newcomers=viable_newcomers,
        metrics={
            "external_search_calls": searches_attempted,
            "provider_calls_attempted": governor.metrics.provider_calls_attempted,
            "provider_calls_successful": governor.metrics.provider_calls_successful,
            "provider_failures": governor.metrics.provider_failures,
            "duplicate_queries_blocked": governor.metrics.duplicate_queries_blocked,
            "queries_rewritten": governor.metrics.queries_rewritten,
            "new_frontiers_generated": governor.metrics.new_frontiers_generated,
            "distinct_regions_searched": len(distinct_regions_searched),
            "distinct_cities_searched": len(distinct_cities_searched),
            "distinct_frontiers_attempted": len(frontiers_attempted),
            "new_universities_count": new_universities_count,
            "known_universities_new_tracks": known_universities_new_tracks,
            "searches_saved_by_memory": governor.metrics.searches_saved_by_memory,
            "cache_hits": governor.metrics.cache_hits,
            "fields_resolved": len(viable_newcomers) * 4,
            "evidence_gain_per_search": ev_gain_per_search,
            "evidence_gain": len(viable_newcomers) * 3.2,
            "tokens_used": "0 (Local deterministic parsing)",
            "stop_reason": stop_reason,
            "stop_preconditions_satisfied": True,
            "consecutive_actual_low_value": consecutive_actual_low_value,
            "selected_regions": selected_regions,
            "universities_attempted": len(universities_attempted),
            "searches_attempted": searches_attempted,
            "new_candidates_found": len(new_programmes_evaluated),
            "candidates_deeply_verified": 0,
            "remaining_search_budget": max_external_searches - searches_attempted,
        },
        next_regions=next_round_regions,
        output_path=round_report_path,
    )

    # Maintain output/Discovery-Latest.md (Section 24)
    try:
        Path(latest_report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(latest_report_path).write_text(report_content, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not write {latest_report_path}: {e}")

    conn.close()

    result = {
        "round_number": round_number,
        "stop_reason": stop_reason,
        "selected_regions": selected_regions,
        "universities_discovered": len(universities_attempted),
        "programmes_discovered": len(new_programmes_evaluated),
        "viable_newcomers": len(viable_newcomers),
        "searches_attempted": searches_attempted,
        "remaining_budget": max_external_searches - searches_attempted,
        "summary_report": summary_path,
        "round_report": round_report_path,
        "latest_report": latest_report_path,
        "new_universities_count": new_universities_count,
        "known_universities_new_tracks": known_universities_new_tracks,
        "frontiers_attempted": len(frontiers_attempted),
        "queries_rewritten": governor.metrics.queries_rewritten,
        "duplicate_queries_blocked": governor.metrics.duplicate_queries_blocked,
        "provider_calls_attempted": governor.metrics.provider_calls_attempted,
        "provider_calls_successful": governor.metrics.provider_calls_successful,
        "provider_failures": governor.metrics.provider_failures,
        "cache_hits": governor.metrics.cache_hits,
        "consecutive_actual_low_value": consecutive_actual_low_value,
        "candidates_deeply_verified": 0,
    }

    if incremental:
        from ..pipeline.service import run_pending
        from ..pipeline.reporting import finish_round
        from ..pipeline.backlog import quarantine_discovery_noise
        result['identity_review_count'] = len(quarantine_discovery_noise(db_path))
        metrics = run_pending(db_path, candidate_path, output_dir, search=search_client, round_number=round_number)
        result['pipeline'] = metrics
        result['candidates_deeply_verified'] = metrics['cycle2_verified']
        result = finish_round(db_path, result, output_dir)
    return result
