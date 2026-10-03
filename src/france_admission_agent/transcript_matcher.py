from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .schemas import (
    CandidateProfile,
    CheckStatus,
    ProgrammeCandidate,
    TranscriptMatchResultInfo,
)


ADMINISTRATIVE_TOKENS = (
    "cv",
    "curriculum vitae",
    "lettre de motivation",
    "lettres de motivation",
    "motivation letter",
    "relevé de notes",
    "releve de notes",
    "relevés de notes",
    "releves de notes",
    "transcripts",
    "transcript",
    "passeport",
    "passport",
    "lettre de recommandation",
    "lettres de recommandation",
    "recommendation letter",
    "recommendation letters",
    "certificat de langue",
    "certificat de langue anglaise",
    "english certificate",
    "french certificate",
    "pièce d'identité",
    "piece d'identite",
    "photo",
    "attestation",
    "diplôme du baccalauréat",
    "diplome du baccalaureat",
    "baccalauréat",
    "baccalaureat",
    "dossier de candidature",
    "projet professionnel",
    "avis de poursuite d'études",
)

DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "programming": ("programming", "programmation", "coding", "development", "développement", "java", "c++", "python"),
    "object_oriented": ("object oriented", "object-oriented", "oop", "objet", "poo"),
    "algorithms": ("algorithm", "algorithme", "algorithmique", "complexité", "complexity"),
    "data_structures": ("data structure", "structures de données", "structures de donnees"),
    "databases": ("database", "bases de données", "bases de donnees", "sql", "data management", "bd"),
    "operating_systems": ("operating system", "système d'exploitation", "systemes d'exploitation", "systèmes", "unix", "linux"),
    "networks": ("network", "réseau", "reseau", "réseaux", "reseaux", "telecom"),
    "software_engineering": ("software engineering", "génie logiciel", "genie logiciel", "conception logicielle", "uml"),
    "web": ("web", "internet technologies", "client-serveur", "technologies web"),
    "distributed": ("distributed", "distribué", "distribue", "parallel", "parallèle", "systèmes distribués", "cloud"),
    "security": ("security", "sécurité", "securite", "cyber", "cryptographie"),
    "ai": ("artificial intelligence", "intelligence artificielle", " ia ", "agents intelligents"),
    "machine_learning": ("machine learning", "apprentissage automatique", "fouille de données", "data mining"),
    "linear_algebra": ("linear algebra", "algèbre linéaire", "algebre lineaire", "matrices", "espaces vectoriels"),
    "probability_statistics": ("probability", "probabilités", "probabilites", "statistics", "statistique"),
    "calculus": ("calculus", "analyse mathématique", "analysis", "differential", "équations différentielles"),
    "discrete_math": ("discrete", "mathématiques discrètes", "mathematiques discretes", "graph theory", "théorie des graphes", "logique"),
    "automata_theory": ("automata", "automate", "formal language", "langages formels", "compilation", "calculabilité"),
    "computer_architecture": ("computer organization", "computer architecture", "architecture des ordinateurs", "assembly", "microprocesseurs"),
}

COURSE_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "Programming Fundamentals": ("programming",),
    "Object-Oriented Programming": ("programming", "object_oriented"),
    "Data Structures and Algorithms": ("algorithms", "data_structures"),
    "Design and Analysis of Algorithms": ("algorithms",),
    "Discrete Structures": ("discrete_math",),
    "Database Systems": ("databases",),
    "Operating Systems": ("operating_systems",),
    "Computer Networks": ("networks",),
    "Computer Organization and Assembly Language": ("computer_architecture",),
    "Theory of Automata": ("automata_theory",),
    "Graph Theory": ("discrete_math",),
    "Software Engineering": ("software_engineering",),
    "Web Technologies": ("web",),
    "Advanced Web Technologies": ("web",),
    "Mobile Application Development": ("programming", "software_engineering"),
    "Parallel and Distributed Computing": ("distributed",),
    "Compiler Construction": ("automata_theory", "programming"),
    "Information Security": ("security",),
    "Artificial Intelligence": ("ai",),
    "Machine Learning": ("machine_learning", "ai"),
    "Calculus and Analytical Geometry": ("calculus",),
    "Linear Algebra": ("linear_algebra",),
    "Differential Equations": ("calculus",),
    "Statistics and Probability Theory": ("probability_statistics",),
    "Numerical Computations": ("calculus",),
}


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("c++", "cpp")
    text = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_administrative_requirement(text: str) -> bool:
    """Checks whether a requirement string is an administrative/application document
    rather than an academic/coursework prerequisite.
    """
    n = _norm(text)
    if not n:
        return True
    return any(token in n for token in ADMINISTRATIVE_TOKENS)


def _matches_alias(alias: str, text: str) -> bool:
    clean_alias = _norm(alias)
    if not clean_alias or len(clean_alias) < 2:
        return False
    # Use whole word boundary to prevent short abbreviations from matching substrings of words
    pattern = r'\b' + re.escape(clean_alias) + r'\b'
    return bool(re.search(pattern, text))


def _domains_for_requirement(requirement: str) -> set[str]:
    req_norm = _norm(requirement)
    found: set[str] = set()
    for domain, aliases in DOMAIN_ALIASES.items():
        for alias in aliases:
            if _matches_alias(alias, req_norm):
                found.add(domain)
                break
    return found


def _course_domains(course: str) -> set[str]:
    if course in COURSE_DOMAIN_HINTS:
        return set(COURSE_DOMAIN_HINTS[course])
    return _domains_for_requirement(course)


@dataclass
class RequirementMatch:
    requirement: str
    matched_courses: list[str] = field(default_factory=list)
    matched_domains: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class TranscriptMatchResult:
    coverage: float
    matches: list[RequirementMatch]
    unmatched_requirements: list[str]


def match_transcript(candidate: CandidateProfile, programme: ProgrammeCandidate) -> TranscriptMatchResult:
    # 1. Filter out administrative documents (CV, motivation letter, passport, etc.)
    raw_reqs = [r.strip() for r in programme.explicit_prerequisites if r and r.strip()]
    reqs = [r for r in raw_reqs if not is_administrative_requirement(r)]

    # Rule: If official prerequisites are not published, DO NOT assign an arbitrary default!
    if not reqs:
        return TranscriptMatchResult(coverage=0.0, matches=[], unmatched_requirements=[])

    course_domains = {c: _course_domains(c) for c in candidate.coursework}
    matches: list[RequirementMatch] = []
    unmatched: list[str] = []

    for req in reqs:
        req_domains = _domains_for_requirement(req)
        scored: list[tuple[float, str, set[str]]] = []
        req_norm = _norm(req)

        for course in candidate.coursework:
            domains = req_domains & course_domains[course]
            course_norm = _norm(course)
            lexical = SequenceMatcher(None, req_norm, course_norm).ratio()
            # If domain match exists: strong domain score (0.85).
            # If domain match does not exist: only match if direct lexical match is high (>= 0.75)
            if domains:
                score = max(0.85, lexical)
            elif lexical >= 0.75:
                score = lexical
            else:
                score = 0.0

            if score >= 0.58:
                scored.append((score, course, domains))


        scored.sort(reverse=True)
        top = scored[:3]
        if not top:
            unmatched.append(req)
            matches.append(RequirementMatch(requirement=req, score=0.0))
            continue

        best = top[0][0]
        matches.append(RequirementMatch(
            requirement=req,
            matched_courses=[x[1] for x in top],
            matched_domains=sorted(set().union(*(x[2] for x in top))),
            score=round(best, 3),
        ))

    matched_count = sum(1 for m in matches if m.score >= 0.58)
    coverage = matched_count / len(reqs) if reqs else 0.0

    # Critical invariant: If matched candidate courses = 0, coverage cannot be > 0.0
    all_matched = [c for m in matches for c in m.matched_courses]
    if not all_matched:
        coverage = 0.0

    return TranscriptMatchResult(
        coverage=round(coverage, 4),
        matches=matches,
        unmatched_requirements=unmatched,
    )


def match_transcript_structured(candidate: CandidateProfile, programme: ProgrammeCandidate) -> TranscriptMatchResultInfo:
    """Returns canonical TranscriptMatchResultInfo conforming to Section 7 & 8."""
    raw_reqs = [r.strip() for r in programme.explicit_prerequisites if r and r.strip()]
    academic_reqs = [r for r in raw_reqs if not is_administrative_requirement(r)]

    if not academic_reqs:
        return TranscriptMatchResultInfo(
            status=CheckStatus.UNVERIFIED,
            required_topics=[],
            matched_topics=[],
            unmatched_topics=[],
            matched_candidate_courses=[],
            coverage=0.0,
        )

    res = match_transcript(candidate, programme)
    matched_topics: list[str] = []
    unmatched_topics: list[str] = []
    matched_courses: list[str] = []

    for m in res.matches:
        if m.score >= 0.58 and m.matched_courses:
            matched_topics.append(m.requirement)
            matched_courses.extend(m.matched_courses)
        else:
            unmatched_topics.append(m.requirement)

    unique_courses = list(dict.fromkeys(matched_courses))
    coverage = len(matched_topics) / len(academic_reqs) if academic_reqs else 0.0
    if not unique_courses:
        coverage = 0.0

    status = CheckStatus.PASS if coverage >= 0.6 else (CheckStatus.UNVERIFIED if coverage > 0 else CheckStatus.FAIL)

    return TranscriptMatchResultInfo(
        status=status,
        required_topics=academic_reqs,
        matched_topics=matched_topics,
        unmatched_topics=unmatched_topics,
        matched_candidate_courses=unique_courses,
        coverage=round(coverage, 2),
    )
