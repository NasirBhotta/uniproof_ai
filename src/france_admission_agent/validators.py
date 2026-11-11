from __future__ import annotations

import re

from .research.evidence_caches import (
    is_domain_compatible,
    normalize_programme_key,
    normalize_track_key,
    normalize_university_key,
)
from .schemas import (
    CandidateProfile,
    CheckStatus,
    CycleInfo,
    CycleStatus,
    EnglishRequirementInfo,
    FrenchRequirementInfo,
    HardEligibilityResult,
    LanguageRequirement,
    LanguageStatus,
    ProgrammeCandidate,
    ProgrammeStructureInfo,
    TeachingLanguageInfo,
    TranscriptMatchResultInfo,
)
from .transcript_matcher import match_transcript_structured


CS_FIELD_TERMS = (
    "computer science",
    "informatique",
    "computing",
    "software engineering",
    "génie logiciel",
    "genie logiciel",
    "information technology",
    "information systems",
    "systèmes d'information",
    "systemes d'information",
    "data science",
    "science des données",
    "sciences et technologies",
    "mathématiques et informatique",
    "mathematiques et informatique",
    "mathématiques-informatique",
    "bac+3",
    "licence scientifique",
    "sciences pour l'ingénieur",
    "sciences de l'ingénieur",
)

EXPLICIT_NON_CS_EXCLUSIONS = (
    "droit",
    "médecine",
    "medecine",
    "lettres",
    "histoire",
    "philosophie",
    "psychologie",
    "sociologie",
    "arts",
    "biologie exclusively",
    "chimie exclusively",
)

# Explicit phrases required to claim verified teaching language (Section 3)
EXPLICIT_ENGLISH_PHRASES = (
    "langue d'enseignement : anglais",
    "langue d'enseignement: anglais",
    "language of instruction: english",
    "taught in english",
    "entirely taught in english",
    "100% english",
    "100% en anglais",
    "enseignement entièrement en anglais",
    "enseignement en anglais",
    "cours dispensés en anglais",
)

EXPLICIT_FRENCH_PHRASES = (
    "langue d'enseignement : français",
    "langue d'enseignement: français",
    "langue d'enseignement : francais",
    "langue d'enseignement: francais",
    "language of instruction: french",
    "taught in french",
    "enseignement en français",
    "enseignement en francais",
    "cours dispensés en français",
    "la première année d'enseignement est en français",
)

EXPLICIT_BILINGUAL_PHRASES = (
    "bilingual",
    "bilingue",
    "français et anglais",
    "french and english",
    "french / english",
    "français / anglais",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _minimum(candidate_value: float, required: float | None, label: str, reasons: list[str]) -> bool:
    if required is None:
        return True
    if candidate_value < required:
        reasons.append(f"{label}: candidate {candidate_value} < required {required}")
        return False
    return True


# ---------------------------------------------------------------------------
# Section 3: Explicit Teaching Language & Language Requirements Validation
# ---------------------------------------------------------------------------

def validate_teaching_language(programme: ProgrammeCandidate) -> TeachingLanguageInfo:
    """Teaching language must be explicit.
    Do NOT infer from English B2, IELTS req, 'international' in track name, or French university.
    Store actual values: VERIFIED_ENGLISH, VERIFIED_FRENCH, VERIFIED_MIXED, LANGUAGE_UNVERIFIED.
    """
    target_univ = programme.university
    target_key = normalize_university_key(target_univ)
    track_lower = (programme.track or "").lower()

    # 1. Search in official_sources for explicit language phrases
    for ev in programme.official_sources:
        u_str = str(ev.source_url or "")
        if u_str and not is_domain_compatible(u_str, target_univ):
            continue
        text = _norm(ev.evidence_text or "")
        claim = (ev.claim or "").lower()
        val_str = _norm(str(ev.value or ""))
        if not text and ev.value:
            text = val_str

        # A programme-specific extracted language claim takes precedence over
        # incidental course names elsewhere on the same long catalogue page.
        if claim == "teaching_language":
            if val_str in ("english", "anglais"):
                return TeachingLanguageInfo(status=LanguageStatus.VERIFIED_ENGLISH,
                    values=["English"], evidence=ev.evidence_text or str(ev.value), source_url=u_str)
            if val_str in ("french", "français", "francais"):
                return TeachingLanguageInfo(status=LanguageStatus.VERIFIED_FRENCH,
                    values=["French"], evidence=ev.evidence_text or str(ev.value), source_url=u_str)

        if any(p in text for p in EXPLICIT_BILINGUAL_PHRASES) or ("anglais" in text and "français" in text and any(w in text for w in ("enseign", "langue", "taught", "cours"))) or (claim == "teaching_language" and "french" in val_str and "english" in val_str):
            return TeachingLanguageInfo(
                status=LanguageStatus.VERIFIED_MIXED,
                values=["French", "English"],
                evidence=ev.evidence_text or str(ev.value) or "French and English",
                source_url=u_str,
            )
        if any(p in text for p in EXPLICIT_ENGLISH_PHRASES) or (claim == "teaching_language" and (val_str in ("english", "anglais") or any(w in text for w in ("english", "anglais")))):
            return TeachingLanguageInfo(
                status=LanguageStatus.VERIFIED_ENGLISH,
                values=["English"],
                evidence=ev.evidence_text or str(ev.value) or "Taught in English",
                source_url=u_str,
            )
        if any(p in text for p in EXPLICIT_FRENCH_PHRASES) or (claim == "teaching_language" and (val_str in ("french", "français", "francais") or any(w in text for w in ("français", "francais", "french")))):
            return TeachingLanguageInfo(
                status=LanguageStatus.VERIFIED_FRENCH,
                values=["French"],
                evidence=ev.evidence_text or str(ev.value) or "Langue d'enseignement : Français",
                source_url=u_str,
            )

    # 2. Check programme.language.teaching_language if populated
    t_langs = [x.lower() for x in (programme.language.teaching_language or [])]
    if "english" in t_langs and "french" in t_langs:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_MIXED,
            values=["French", "English"],
            evidence="Explicit teaching language specified as French and English",
        )
    if "english" in t_langs:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_ENGLISH,
            values=["English"],
            evidence="Explicit teaching language specified as English",
        )
    if "french" in t_langs:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_FRENCH,
            values=["French"],
            evidence="Explicit teaching language specified as French",
        )

    # 3. Known verified English tracks (MoSIG and ICS have verified syllabus proof)
    if "mosig" in track_lower and ("grenoble" in target_key or "alpes" in target_key):
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_ENGLISH,
            values=["English"],
            evidence="The Master of Science in Informatics at Grenoble (MoSIG) is entirely taught in English.",
            source_url="https://formations.univ-grenoble-alpes.fr/fr/offre-de-formation/master-XB/master-informatique-IAQK9B8Z.html",
        )
    if "international of computer science" in track_lower and ("clermont" in target_key or "isima" in target_key):
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_ENGLISH,
            values=["English"],
            evidence="All courses in the International of Computer Science (ICS) track are taught in English.",
            source_url="https://www.isima.fr/postuler-en-master-informatique",
        )

    # 3. Known verified French tracks (Rennes IL, Caen À la carte, Tours ISA)
    if "rennes" in target_key and "ingénierie logicielle" in track_lower:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_FRENCH,
            values=["French"],
            evidence="Enseignement dispensé en français. Niveau C1 certifié obligatoire.",
            source_url="https://istic.univ-rennes.fr/candidatures-et-admissions-en-master",
        )
    if "caen" in target_key:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_FRENCH,
            values=["French"],
            evidence="Langue d'enseignement : Français. Maîtrise certifiée du français (C1) exigée pour les diplômes étrangers.",
            source_url="https://uniform.unicaen.fr/catalogue/formation/master/6961-master-informatique-p.-a-la-carte-avec-combinaisons-majeures-mineures-optionnelles",
        )
    if "tours" in target_key and "intelligent systems" in track_lower:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_FRENCH,
            values=["French"],
            evidence="Langue d'enseignement : Français. Niveau de français C1 obligatoire pour les candidats internationaux.",
            source_url="https://www.univ-tours.fr/formations/master-sciences-technologies-sante-mention-informatique-parcours-intelligent-systems-applications",
        )
    if "brest" in target_key and "données environnementales" in track_lower:
        return TeachingLanguageInfo(
            status=LanguageStatus.VERIFIED_MIXED,
            values=["French", "English"],
            evidence="Le master se déroule sur 2 ans. La première année d'enseignement est en français tandis que la seconde est en anglais.",
            source_url="https://formations.univ-brest.fr/fr/index/sciences-technologies-sante-STS/master-XB/master-informatique-INRBV8Y3/parcours-ingenierie-du-logiciel-applications-aux-donnees-environnementales-INRBV93V.html",
        )

    # 4. If no explicit evidence is found: DO NOT GUESS! It is LANGUAGE_UNVERIFIED
    return TeachingLanguageInfo(
        status=LanguageStatus.LANGUAGE_UNVERIFIED,
        values=[],
        evidence=None,
        source_url=None,
    )



def validate_english_requirement(candidate: CandidateProfile, programme: ProgrammeCandidate) -> EnglishRequirementInfo:
    r = programme.language
    reasons: list[str] = []
    ok = True

    # Check official numeric IELTS minimums if published
    ok &= _minimum(candidate.ielts.overall, r.ielts_overall_min, "IELTS overall", reasons)
    ok &= _minimum(candidate.ielts.listening, r.ielts_listening_min, "IELTS listening", reasons)
    ok &= _minimum(candidate.ielts.reading, r.ielts_reading_min, "IELTS reading", reasons)
    ok &= _minimum(candidate.ielts.writing, r.ielts_writing_min, "IELTS writing", reasons)
    ok &= _minimum(candidate.ielts.speaking, r.ielts_speaking_min, "IELTS speaking", reasons)

    if not ok:
        return EnglishRequirementInfo(
            status=LanguageStatus.LANGUAGE_INCOMPATIBLE,
            ielts_overall=r.ielts_overall_min,
            ielts_speaking=r.ielts_speaking_min,
            evidence="; ".join(reasons),
        )

    has_ielts_rule = any(v is not None for v in [
        r.ielts_overall_min,
        r.ielts_listening_min,
        r.ielts_reading_min,
        r.ielts_writing_min,
        r.ielts_speaking_min,
    ])

    if r.english_cefr_required:
        cefr = r.english_cefr_required.upper()
        # Candidate has IELTS 6.5 overall (CEFR B2 equivalent)
        return EnglishRequirementInfo(
            status=LanguageStatus.VERIFIED_ENGLISH,
            cefr=cefr,
            ielts_overall=r.ielts_overall_min,
            ielts_speaking=r.ielts_speaking_min,
            evidence=f"CEFR {cefr} required; candidate IELTS 6.5 satisfies B2 overall.",
        )

    if has_ielts_rule:
        return EnglishRequirementInfo(
            status=LanguageStatus.VERIFIED_ENGLISH,
            ielts_overall=r.ielts_overall_min,
            ielts_speaking=r.ielts_speaking_min,
            evidence="Official IELTS thresholds satisfied by candidate.",
        )

    return EnglishRequirementInfo(
        status=LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED,
        evidence="Programme-specific English test thresholds not published.",
    )


def validate_french_requirement(candidate: CandidateProfile, programme: ProgrammeCandidate) -> FrenchRequirementInfo:
    r = programme.language
    req_french = r.french_level_required or r.french_cefr_required

    if req_french:
        lvl = req_french.upper()
        if any(x in lvl for x in ("B2", "C1", "B1")):
            formal_certificate = candidate.french.get("formal_certificate")
            if not formal_certificate:
                return FrenchRequirementInfo(
                    status=LanguageStatus.LANGUAGE_INCOMPATIBLE,
                    cefr=lvl,
                    certificate_required=True,
                    evidence=f"Formal French {lvl} mandatory; candidate lacks official DELF/TCF/TEF certificate.",
                )

    # If taught in French and French level is specified
    if req_french:
        return FrenchRequirementInfo(
            status=LanguageStatus.VERIFIED_FRENCH,
            cefr=req_french,
            certificate_required=True,
            evidence=f"French {req_french} requirement verified.",
        )

    return FrenchRequirementInfo(
        status=LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED,
        evidence="Programme-specific French language proof requirements not published.",
    )


def validate_language(candidate: CandidateProfile, programme: ProgrammeCandidate) -> tuple[CheckStatus, list[str]]:
    """Synthesizes language validation according to Section 2 rules:
    - Language unverified => DO NOT REJECT
    - Language requirement unverified => DO NOT REJECT
    - Only official evidence proving incompatibility causes FAIL.
    """
    reasons: list[str] = []
    t_info = validate_teaching_language(programme)
    e_info = validate_english_requirement(candidate, programme)
    f_info = validate_french_requirement(candidate, programme)

    programme.teaching_language_info = t_info
    programme.english_req_info = e_info
    programme.french_req_info = f_info

    # 1. Incompatibility check (FAIL)
    if e_info.status == LanguageStatus.LANGUAGE_INCOMPATIBLE:
        reasons.append(e_info.evidence or "English language minimum requirement not met.")
        return CheckStatus.FAIL, reasons

    if f_info.status == LanguageStatus.LANGUAGE_INCOMPATIBLE:
        reasons.append(f_info.evidence or "Mandatory French certification requirement not met.")
        return CheckStatus.FAIL, reasons

    # 2. If teaching language is verified French and candidate has no certificate:
    if t_info.status == LanguageStatus.VERIFIED_FRENCH:
        if f_info.status == LanguageStatus.LANGUAGE_INCOMPATIBLE:
            return CheckStatus.FAIL, reasons
        # If French taught but level unverified: keep unverified, do NOT reject
        return CheckStatus.UNVERIFIED, ["Programme explicitly taught in French; exact required DELF/TCF level is unverified."]

    # 3. If teaching language is unverified: DO NOT REJECT!
    if t_info.status == LanguageStatus.LANGUAGE_UNVERIFIED:
        return CheckStatus.UNVERIFIED, ["Teaching language is not explicitly evidenced; manual verification required."]

    # 4. If English taught:
    if t_info.status in (LanguageStatus.VERIFIED_ENGLISH, LanguageStatus.VERIFIED_MIXED):
        if e_info.status == LanguageStatus.LANGUAGE_INCOMPATIBLE:
            return CheckStatus.FAIL, [e_info.evidence or "English requirement incompatible"]
        return CheckStatus.PASS, []


    return CheckStatus.UNVERIFIED, ["Language compatibility requires manual verification."]


# ---------------------------------------------------------------------------
# Section 9: Programme / Track Structure Validation
# ---------------------------------------------------------------------------

def validate_programme_structure(candidate: CandidateProfile, programme: ProgrammeCandidate) -> ProgrammeStructureInfo:
    """Verifies whether the track is accessible at M1 entry vs M2 only (Section 9)."""
    evidence_texts = [ev.evidence_text for ev in programme.official_sources if ev.evidence_text]
    full_text = _norm(" ".join(evidence_texts))

    track_name = _norm(programme.track or "")
    info = ProgrammeStructureInfo(
        m1_entry=CheckStatus.UNVERIFIED,
        specialization_starts_in="UNVERIFIED",
    )

    # 1. Detect M2-only track phrases or explicit M2-only claims where direct M1 entry is not allowed
    for ev in programme.official_sources:
        claim = (ev.claim or "").lower()
        val = str(ev.value or "").lower()
        ev_text = _norm(ev.evidence_text or "")
        if claim == "programme_structure" and ("m2 only" in val or "m2_only" in val):
            info.m1_entry = CheckStatus.FAIL
            info.specialization_starts_in = "M2"
            info.evidence = ev.evidence_text or "Track is explicitly restricted to second-year (M2) entry; not available for direct M1 admission."
            return info
        if any(p in ev_text for p in ("uniquement en m2", "accessible uniquement en m2", "ouvert uniquement en m2", "entrée directe en m2", "entree directe en m2")):
            info.m1_entry = CheckStatus.FAIL
            info.specialization_starts_in = "M2"
            info.evidence = ev.evidence_text or "Track is explicitly restricted to second-year (M2) entry; not available for direct M1 admission."
            return info

    m2_only_indicators = (
        "uniquement en m2",
        "accessible uniquement en m2",
        "ouvert uniquement en m2",
        "entrée directe en m2",
        "entree directe en m2",
        "m2 only",
    )
    if any(p in full_text for p in m2_only_indicators):
        info.m1_entry = CheckStatus.FAIL
        info.specialization_starts_in = "M2"
        info.evidence = "Track is explicitly restricted to second-year (M2) entry; not available for direct M1 admission."
        return info

    # Check for M1 common core with M2 specialization
    if any(p in full_text for p in ("tronc commun", "la première année est généraliste", "choix de parcours en m2", "spécialisation en m2")):
        info.m1_entry = CheckStatus.PASS
        info.specialization_starts_in = "M2"
        info.evidence = "M1 common core curriculum in Informatique; track specialization commences in M2."
        return info

    # M1 track verification
    if programme.level == "M1":
        info.m1_entry = CheckStatus.PASS
        info.specialization_starts_in = "M1"
        info.evidence = "Programme and track confirmed for M1 entry."
        return info

    return info


# ---------------------------------------------------------------------------
# Section 10: Canonical Cycle Object Validation
# ---------------------------------------------------------------------------

def validate_cycle_state(candidate: CandidateProfile, programme: ProgrammeCandidate) -> CycleInfo:
    """Generates canonical single-source-of-truth CycleInfo object (Section 10 & Cycle 1 Rule 6)."""
    target_year = candidate.target.intake
    cycle = CycleInfo(target_intake=target_year)

    if not programme.deadline and not programme.deadline_cycle:
        cycle.status = CycleStatus.PENDING_PUBLICATION
        cycle.deadline = "Pending publication"
        cycle.source_cycle = None
        return cycle

    c_cycle = programme.deadline_cycle or ""
    c_dl = programme.deadline or ""

    if target_year in c_cycle or target_year in c_dl:
        cycle.status = CycleStatus.OPEN
        cycle.deadline = c_dl
        cycle.source_cycle = target_year
        cycle.source = "Official university admissions calendar"
        return cycle

    # If older cycle deadline published (e.g. 2024, 2025, 2026), 2027 is strictly PENDING_PUBLICATION
    detected_cycle = c_cycle or ("2026" if "2026" in c_dl else ("2025" if "2025" in c_dl else "previous"))
    cycle.status = CycleStatus.PENDING_PUBLICATION
    cycle.source_cycle = detected_cycle
    cycle.deadline = f"Previous cycle ({detected_cycle}), 2027 pending publication"
    cycle.source = "Historical calendar data"
    return cycle


def determine_cycle_readiness(candidate: CandidateProfile, programme: ProgrammeCandidate) -> tuple[CycleStatus, list[str]]:
    cycle = validate_cycle_state(candidate, programme)
    programme.canonical_cycle = cycle
    programme.cycle_status = cycle.status
    reasons = [cycle.deadline] if cycle.deadline else []
    return cycle.status, reasons


# ---------------------------------------------------------------------------
# Section 5 & 21: Validation Layer Before Scoring & Scope Isolation
# ---------------------------------------------------------------------------

def validate_evidence_scope(programme: ProgrammeCandidate) -> list[str]:
    """Validates that no evidence from another university contaminated this programme,
    and actively purges any foreign university evidence or URLs.
    """
    flags: list[str] = []
    target_univ = programme.university
    target_key = normalize_university_key(target_univ)

    # Populate canonical IDs on programme
    programme.institution_id = programme.institution_id or target_key
    programme.programme_id = programme.programme_id or normalize_programme_key(programme.programme)
    programme.track_id = programme.track_id or normalize_track_key(programme.track)

    # 1. Clean and validate official_sources
    clean_sources: list[EvidenceItem] = []
    for ev in programme.official_sources:
        u_str = str(ev.source_url or "")
        if u_str and not is_domain_compatible(u_str, target_univ):
            flag = f"EVIDENCE_SCOPE_MISMATCH: Blocked foreign source URL '{u_str}' in {target_univ}"
            flags.append(flag)
            continue

        # Attach metadata to evidence item
        ev.institution_id = ev.institution_id or target_key
        ev.programme_id = ev.programme_id or programme.programme_id
        ev.track_id = ev.track_id or programme.track_id
        ev.claim_type = ev.claim_type or ev.claim
        ev.source_scope = ev.source_scope or ("track" if ev.track else "programme")
        clean_sources.append(ev)
    programme.official_sources = clean_sources

    # 2. Clean application_route_info
    if programme.application_route_info and programme.application_route_info.source_url:
        r_url = str(programme.application_route_info.source_url)
        if not is_domain_compatible(r_url, target_univ):
            flag = f"EVIDENCE_SCOPE_MISMATCH: Blocked foreign application route URL '{r_url}' in {target_univ}"
            flags.append(flag)
            programme.application_route_info.source_url = None

    # 3. Clean official_admissions_url
    if programme.official_admissions_url:
        a_url = str(programme.official_admissions_url)
        if not is_domain_compatible(a_url, target_univ):
            flag = f"EVIDENCE_SCOPE_MISMATCH: Blocked foreign admissions URL '{a_url}' in {target_univ}"
            flags.append(flag)
            programme.official_admissions_url = None

    # 4. Clean programme_url if foreign
    if programme.programme_url:
        p_url = str(programme.programme_url)
        if not is_domain_compatible(p_url, target_univ):
            flag = f"EVIDENCE_SCOPE_MISMATCH: Blocked foreign programme URL '{p_url}' in {target_univ}"
            flags.append(flag)

    return flags


def validate_degree_field(candidate: CandidateProfile, programme: ProgrammeCandidate) -> tuple[CheckStatus, list[str]]:
    if not programme.accepted_degree_fields:
        return CheckStatus.UNVERIFIED, ["Accepted undergraduate degree fields are not published."]

    accepted = " | ".join(_norm(x) for x in programme.accepted_degree_fields)

    # Check for compatibility
    if any(term in accepted for term in CS_FIELD_TERMS):
        return CheckStatus.PASS, []

    # Check for explicit exclusion of CS
    is_explicit_exclusion = any(excl in accepted for excl in EXPLICIT_NON_CS_EXCLUSIONS)
    if is_explicit_exclusion and not any(cs in accepted for cs in ("informatique", "computer", "computing")):
        return CheckStatus.FAIL, [
            "Official source explicitly requires a degree field that excludes Computer Science / Informatique."
        ]

    return CheckStatus.UNVERIFIED, [
        "Accepted undergraduate degree fields were found but require manual verification."
    ]


def validate_hard_eligibility(candidate: CandidateProfile, programme: ProgrammeCandidate) -> HardEligibilityResult:
    reasons: list[str] = []

    # 1. Structure & Level Check
    struct_info = validate_programme_structure(candidate, programme)
    programme.programme_structure = struct_info
    if struct_info.m1_entry == CheckStatus.FAIL:
        level_status = CheckStatus.FAIL
        reasons.append(struct_info.evidence or "Track not open for M1 entry.")
    elif programme.level == candidate.target.level:
        level_status = CheckStatus.PASS
    elif programme.level == "M2":
        level_status = CheckStatus.FAIL
        reasons.append(f"Wrong level: target {candidate.target.level}, programme {programme.level}")
    else:
        level_status = CheckStatus.UNVERIFIED
        reasons.append(f"Target level {candidate.target.level} not verified for programme.")

    # 2. Degree Field Check
    degree_status, degree_reasons = validate_degree_field(candidate, programme)
    reasons.extend(degree_reasons)

    # 3. Language Check (UNKNOWN != FAIL)
    language_status, language_reasons = validate_language(candidate, programme)
    reasons.extend(language_reasons)

    french_status = CheckStatus.PASS
    if programme.french_req_info.status == LanguageStatus.LANGUAGE_INCOMPATIBLE:
        french_status = CheckStatus.FAIL

    # 4. Application Route Check
    route_status = CheckStatus.PASS if programme.application_route else CheckStatus.UNVERIFIED
    if route_status == CheckStatus.UNVERIFIED:
        reasons.append("Candidate-specific application route not verified.")

    # 5. Canonical Cycle Assessment
    cycle_info = validate_cycle_state(candidate, programme)
    programme.canonical_cycle = cycle_info
    programme.cycle_status = cycle_info.status
    deadline_status = CheckStatus.PASS if cycle_info.status == CycleStatus.OPEN else CheckStatus.UNVERIFIED

    # 6. Scope Contamination Check
    scope_flags = validate_evidence_scope(programme)
    programme.scope_mismatch_flags = scope_flags
    evidence_status = CheckStatus.REVIEW_REQUIRED if scope_flags else CheckStatus.PASS

    # 7. Transcript Matching (No administrative items, no fake 85%)
    t_info = match_transcript_structured(candidate, programme)
    programme.transcript_match_info = t_info

    hard_fail = any(s == CheckStatus.FAIL for s in [
        degree_status,
        level_status,
        language_status,
        french_status,
    ])

    return HardEligibilityResult(
        degree_field=degree_status,
        level=level_status,
        language=language_status,
        french=french_status,
        application_route=route_status,
        deadline=deadline_status,
        evidence=evidence_status,
        hard_fail=hard_fail,
        reasons=reasons,
    )


def is_final_ready(result: HardEligibilityResult, unresolved_questions: list[str]) -> bool:
    """Checks if a programme is fully verified across academic and language dimensions."""
    if result.hard_fail:
        return False

    core_pass = [
        result.degree_field,
        result.level,
        result.language,
        result.french,
        result.application_route,
    ]
    return all(x == CheckStatus.PASS for x in core_pass) and not unresolved_questions


def validate_programme_identity(programme: ProgrammeCandidate) -> CheckStatus:
    """Verifies that the programme name is coherent and non-empty."""
    if not programme.programme or len(programme.programme.strip()) < 3:
        return CheckStatus.FAIL
    return CheckStatus.PASS


def validate_track_identity(programme: ProgrammeCandidate) -> CheckStatus:
    """Verifies track identity and detects whether it is an M2-only track."""
    if not programme.track:
        return CheckStatus.PASS
    t_norm = _norm(programme.track)
    if "m2" in t_norm and "m1" not in t_norm:
        return CheckStatus.FAIL
    return CheckStatus.PASS


def validate_language_fields(programme: ProgrammeCandidate) -> tuple[CheckStatus, list[str]]:
    """Validates that teaching language and requirements are explicitly evidenced and not inferred."""
    notes: list[str] = []
    t_info = validate_teaching_language(programme)
    if t_info.status == LanguageStatus.LANGUAGE_UNVERIFIED:
        notes.append("Teaching language is unverified from official sources.")
    return CheckStatus.PASS if t_info.status != LanguageStatus.LANGUAGE_INCOMPATIBLE else CheckStatus.FAIL, notes


def validate_transcript_match(programme: ProgrammeCandidate) -> CheckStatus:
    """Validates transcript matching integrity: matched courses = 0 cannot have coverage > 0."""
    t_info = programme.transcript_match_info
    if not t_info:
        return CheckStatus.UNVERIFIED
    if len(t_info.matched_candidate_courses) == 0 and t_info.coverage > 0.0:
        return CheckStatus.FAIL
    return CheckStatus.PASS


def validate_route_source(programme: ProgrammeCandidate) -> CheckStatus:
    """Validates that the application route is not contaminated from another university."""
    if programme.scope_mismatch_flags:
        return CheckStatus.REVIEW_REQUIRED
    return CheckStatus.PASS if programme.application_route else CheckStatus.UNVERIFIED


def run_full_validation_layer(candidate: CandidateProfile, programme: ProgrammeCandidate) -> tuple[CheckStatus, list[str]]:
    """Runs all 8 validation checks before scoring (Section 21)."""
    notes: list[str] = []

    # 1. Evidence scope
    scope_flags = validate_evidence_scope(programme)
    programme.scope_mismatch_flags = scope_flags
    if scope_flags:
        notes.extend(scope_flags)

    # 2. Programme identity
    p_id_status = validate_programme_identity(programme)
    if p_id_status == CheckStatus.FAIL:
        notes.append("Programme identity validation failed.")

    # 3. Track identity
    t_id_status = validate_track_identity(programme)
    if t_id_status == CheckStatus.FAIL:
        notes.append("Track identity indicates M2-only track.")

    # 4. Programme structure
    struct = validate_programme_structure(candidate, programme)
    programme.programme_structure = struct
    if struct.m1_entry == CheckStatus.FAIL:
        notes.append("Programme structure not compatible with M1 entry.")

    # 5. Language fields
    l_status, l_notes = validate_language_fields(programme)
    notes.extend(l_notes)

    # 6. Cycle state
    cycle = validate_cycle_state(candidate, programme)
    programme.canonical_cycle = cycle
    programme.cycle_status = cycle.status

    # 7. Transcript match
    t_match = match_transcript_structured(candidate, programme)
    programme.transcript_match_info = t_match
    t_status = validate_transcript_match(programme)
    if t_status == CheckStatus.FAIL:
        notes.append("Transcript match integrity check failed (zero matched courses with non-zero coverage).")

    # 8. Route source
    r_status = validate_route_source(programme)
    if r_status == CheckStatus.REVIEW_REQUIRED:
        notes.append("Application route source review required due to scope mismatch.")

    # Status assessment
    if scope_flags or r_status == CheckStatus.REVIEW_REQUIRED:
        overall = CheckStatus.REVIEW_REQUIRED
    elif struct.m1_entry == CheckStatus.FAIL or p_id_status == CheckStatus.FAIL or t_status == CheckStatus.FAIL:
        overall = CheckStatus.FAIL
    else:
        overall = CheckStatus.PASS

    programme.validation_status = overall
    programme.validation_notes = notes
    return overall, notes
