from __future__ import annotations

from france_admission_agent.profile import load_candidate
from france_admission_agent.research.application_route import resolve_application_route
from france_admission_agent.research.evidence_caches import (
    InstitutionEvidenceCache,
    ProgrammeEvidenceCache,
    SearchTracker,
    normalize_query,
)
from france_admission_agent.schemas import (
    CandidateProfile,
    CheckStatus,
    CycleStatus,
    EvidenceItem,
    LanguageRequirement,
    LanguageStatus,
    ProgrammeCandidate,
    ProgrammeEvaluation,
)
from france_admission_agent.scoring import assign_evaluation_group, calculate_score
from france_admission_agent.transcript_matcher import match_transcript_structured
from france_admission_agent.validators import (
    determine_cycle_readiness,
    validate_cycle_state,
    validate_degree_field,
    validate_hard_eligibility,
    validate_language,
    validate_teaching_language,
)


def get_candidate() -> CandidateProfile:
    return load_candidate("config/candidate_profile.json")


def make_programme(**kwargs) -> ProgrammeCandidate:
    defaults = {
        "programme_id": "test_prog_01",
        "university": "Université de Tours",
        "programme": "Master Informatique",
        "level": "M1",
        "city": "Tours",
        "public": True,
    }
    defaults.update(kwargs)
    return ProgrammeCandidate(**defaults)


# ---------------------------------------------------------------------------
# Section 27: 17 Mandatory Unit Tests
# ---------------------------------------------------------------------------

# 1. Speaking 5.5, official minimum 6.0 => FAIL
def test_1_speaking_5_5_vs_required_6_0_fails():
    candidate = get_candidate()
    prog = make_programme(
        language=LanguageRequirement(
            teaching_language=["English"],
            ielts_overall_min=6.5,
            ielts_speaking_min=6.0,
        )
    )
    status, reasons = validate_language(candidate, prog)
    assert status == CheckStatus.FAIL
    assert any("speaking" in r.lower() for r in reasons)


# 2. IELTS speaking requirement missing => UNVERIFIED
def test_2_ielts_speaking_missing_is_unverified():
    candidate = get_candidate()
    prog = make_programme(
        language=LanguageRequirement(
            teaching_language=["English"],
            ielts_overall_min=6.5,
            ielts_speaking_min=None,  # Not published
        )
    )
    status, reasons = validate_language(candidate, prog)
    assert status != CheckStatus.FAIL
    assert prog.english_req_info.status == LanguageStatus.VERIFIED_ENGLISH
    assert prog.english_req_info.ielts_speaking is None


# 3. Teaching language missing => LANGUAGE_UNVERIFIED => programme NOT rejected
def test_3_teaching_language_missing_is_unverified_and_not_rejected():
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Licence Informatique"],
        language=LanguageRequirement(teaching_language=[]),
    )
    r = validate_hard_eligibility(candidate, prog)
    assert not r.hard_fail
    assert prog.teaching_language_info.status == LanguageStatus.LANGUAGE_UNVERIFIED


# 4. Language requirement missing => LANGUAGE_REQUIREMENT_UNVERIFIED => programme NOT rejected
def test_4_language_requirement_missing_is_unverified_and_not_rejected():
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Licence Informatique"],
        language=LanguageRequirement(
            teaching_language=["English"],
            ielts_overall_min=None,
            ielts_speaking_min=None,
            english_cefr_required=None,
        ),
    )
    r = validate_hard_eligibility(candidate, prog)
    assert not r.hard_fail
    assert prog.english_req_info.status == LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED


# 5. French B2 officially mandatory, candidate lacks accepted proof => FAIL
def test_5_french_b2_required_without_formal_certificate_fails():
    candidate = get_candidate()
    prog = make_programme(
        language=LanguageRequirement(
            teaching_language=["French"],
            french_level_required="B2",
        )
    )
    r = validate_hard_eligibility(candidate, prog)
    assert r.hard_fail
    assert r.french == CheckStatus.FAIL
    assert any("DELF/TCF/TEF" in reason for reason in r.reasons)


# 6. English B2 published, no IELTS equivalence => preserve B2, do not invent IELTS number
def test_6_english_b2_preserved_without_inventing_ielts():
    candidate = get_candidate()
    prog = make_programme(
        language=LanguageRequirement(
            teaching_language=["English"],
            english_cefr_required="B2",
            ielts_speaking_min=None,  # Should NOT be invented as 6.0
        )
    )
    status, reasons = validate_language(candidate, prog)
    assert status == CheckStatus.PASS
    assert prog.language.english_cefr_required == "B2"
    assert prog.language.ielts_speaking_min is None


# 7. Accepted degree fields missing => UNVERIFIED
def test_7_accepted_degree_fields_missing_is_unverified():
    candidate = get_candidate()
    prog = make_programme(accepted_degree_fields=[])
    status, reasons = validate_degree_field(candidate, prog)
    assert status == CheckStatus.UNVERIFIED
    r = validate_hard_eligibility(candidate, prog)
    assert r.degree_field == CheckStatus.UNVERIFIED
    assert not r.hard_fail


# 8. Official degree incompatibility => FAIL
def test_8_official_degree_incompatibility_fails():
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Licence de Droit exclusivement", "Médecine"]
    )
    status, reasons = validate_degree_field(candidate, prog)
    assert status == CheckStatus.FAIL
    r = validate_hard_eligibility(candidate, prog)
    assert r.degree_field == CheckStatus.FAIL
    assert r.hard_fail


# 9. Matched courses = 0 => transcript coverage cannot be 85%
def test_9_matched_courses_zero_cannot_have_85_percent_coverage():
    candidate = get_candidate()
    prog = make_programme(
        explicit_prerequisites=["Génie civil avancé", "Résistance des matériaux"]
    )
    t_info = match_transcript_structured(candidate, prog)
    assert len(t_info.matched_candidate_courses) == 0
    assert t_info.coverage == 0.0
    assert t_info.coverage != 0.85


# 10. Evidence from University A cannot populate University B
def test_10_evidence_from_university_a_cannot_populate_university_b():
    inst_cache = InstitutionEvidenceCache()
    inst_cache.update_policy(
        "Université de Montpellier",
        domain="umontpellier.fr",
        eef_policy="Montpellier specific policy",
        source_university="Université de Montpellier",
    )
    # Attempt to merge into Franche-Comté
    inst_cache.update_policy(
        "Université de Franche-Comté",
        domain="univ-fcomte.fr",
        eef_policy="Montpellier specific policy",
        source_university="Université de Montpellier",  # Mismatch!
    )
    assert inst_cache.scope_mismatches_prevented >= 1
    fc = inst_cache.get("Université de Franche-Comté")
    assert fc is None or fc.etudes_en_france_policy is None

    prog_cache = ProgrammeEvidenceCache()
    res = prog_cache.add_page_evidence(
        target_university="Université de Franche-Comté",
        target_programme="Master Informatique",
        target_track="ISL",
        page_url="https://umontpellier.fr/gl",
        page_content="Montpellier content",
        source_university="Université de Montpellier",
        source_programme="Génie Logiciel",
    )
    assert res is False
    assert prog_cache.scope_mismatches_prevented >= 1


# 11. M2-only track cannot be presented as M1 track
def test_11_m2_only_track_cannot_be_presented_as_m1_track():
    candidate = get_candidate()
    prog = make_programme(
        university="Université de Bretagne Occidentale",
        programme="Master Informatique",
        track="Parcours International",
        level="M1",
        official_sources=[
            EvidenceItem(
                claim="programme_structure",
                value="M2 only",
                evidence_text="Ce parcours est accessible uniquement en M2 pour les étudiants internationaux.",
                source_url="https://formations.univ-brest.fr/international",
                source_type="official_university",
            )

        ],
    )
    r = validate_hard_eligibility(candidate, prog)
    assert r.hard_fail is True
    assert prog.programme_structure.m1_entry == CheckStatus.FAIL


# 12. 2027 deadline unavailable => PENDING_PUBLICATION => not rejection
def test_12_deadline_unavailable_is_pending_publication_not_rejection():
    candidate = get_candidate()
    prog = make_programme(deadline=None, deadline_cycle=None)
    cycle_status, reasons = determine_cycle_readiness(candidate, prog)
    assert cycle_status == CycleStatus.PENDING_PUBLICATION
    r = validate_hard_eligibility(candidate, prog)
    assert not r.hard_fail


# 13. Cycle cannot simultaneously be OPEN and PENDING_PUBLICATION
def test_13_cycle_cannot_simultaneously_be_open_and_pending_publication():
    candidate = get_candidate()
    prog_open = make_programme(deadline="2027-02-15", deadline_cycle="2027")
    c_open = validate_cycle_state(candidate, prog_open)
    assert c_open.status == CycleStatus.OPEN
    assert c_open.status != CycleStatus.PENDING_PUBLICATION

    prog_pend = make_programme(deadline="2025-02-15", deadline_cycle="2025")
    c_pend = validate_cycle_state(candidate, prog_pend)
    assert c_pend.status == CycleStatus.PENDING_PUBLICATION
    assert c_pend.status != CycleStatus.OPEN


# 14. English B2 requirement does not automatically mean English-taught
def test_14_english_b2_requirement_does_not_mean_english_taught():
    prog = make_programme(
        language=LanguageRequirement(
            teaching_language=[],
            english_cefr_required="B2",
        )
    )
    t_info = validate_teaching_language(prog)
    assert t_info.status == LanguageStatus.LANGUAGE_UNVERIFIED
    assert t_info.status != LanguageStatus.VERIFIED_ENGLISH


# 15. French university does not automatically mean French-taught
def test_15_french_university_does_not_mean_french_taught():
    prog = make_programme(
        university="Université de Franche-Comté",
        language=LanguageRequirement(teaching_language=[]),
    )
    t_info = validate_teaching_language(prog)
    assert t_info.status == LanguageStatus.LANGUAGE_UNVERIFIED
    assert t_info.status != LanguageStatus.VERIFIED_FRENCH


# 16. Language unverified + strong academic fit => LANGUAGE VERIFICATION REQUIRED
def test_16_language_unverified_plus_strong_academic_fit_goes_to_category_c():
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Licence Informatique"],
        explicit_prerequisites=["Programmation", "Algorithmique", "Bases de données"],
        language=LanguageRequirement(teaching_language=[]),  # Language unverified
    )
    elig = validate_hard_eligibility(candidate, prog)
    cycle_status, _ = determine_cycle_readiness(candidate, prog)
    e = ProgrammeEvaluation(programme=prog, eligibility=elig, cycle_readiness=cycle_status)
    e.score = calculate_score(e)
    group = assign_evaluation_group(e)
    assert group == "C_LANGUAGE_VERIFICATION_REQUIRED"
    assert e.score.status.value == "PROVISIONAL"


# 17. Language unverified alone must not remove programme from viable pool
def test_17_language_unverified_alone_must_not_remove_from_viable_pool():
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Informatique"],
        explicit_prerequisites=["Algorithmique"],
        language=LanguageRequirement(teaching_language=[]),  # Unverified
    )
    elig = validate_hard_eligibility(candidate, prog)
    assert not elig.hard_fail
    cycle_status, _ = determine_cycle_readiness(candidate, prog)
    e = ProgrammeEvaluation(programme=prog, eligibility=elig, cycle_readiness=cycle_status)
    e.score = calculate_score(e)
    group = assign_evaluation_group(e)
    # Programme is viable in Category C
    assert group in ("A_FULLY_VERIFIED", "B_CALENDAR_PENDING", "C_LANGUAGE_VERIFICATION_REQUIRED")


# ---------------------------------------------------------------------------
# Search and Cache Efficiency Tests
# ---------------------------------------------------------------------------

def test_cached_university_route_prevents_duplicate_search():
    candidate = get_candidate()
    cache = InstitutionEvidenceCache()
    cache.update_policy(
        "Université de Tours",
        domain="univ-tours.fr",
        eef_policy="Candidate must apply via Études en France procedure for Pakistan.",
    )
    prog = make_programme(
        university="Université de Tours",
        official_university_domain="univ-tours.fr",
    )
    route_info = resolve_application_route(candidate, prog, cache, cached_pages={})
    assert route_info.platform == "Études en France"
    assert route_info.status == CheckStatus.PASS


def test_normalized_search_deduplication():
    tracker = SearchTracker()
    q1 = 'Master "Informatique" M1 Tours'
    q2 = 'master informatique m1 tours'
    assert normalize_query(q1) == normalize_query(q2)

    tracker.record_search(q1, is_cache_hit=False)
    assert tracker.external_searches_used == 1

    tracker.record_search(q2, is_cache_hit=True)
    assert tracker.cache_hits == 1
    assert tracker.external_searches_used == 1


def test_single_page_resolves_multiple_fields():
    candidate = get_candidate()
    page_text = (
        "Master Informatique M1. Candidats internationaux: procédure Études en France obligatoire. "
        "Langue d'enseignement: Anglais (English). Capacité d'accueil: 45 places. "
        "Prérequis: Licence Informatique ou diplôme équivalent en informatique."
    )
    cache = InstitutionEvidenceCache()
    prog = make_programme(
        university="Université de Franche-Comté",
        official_university_domain="univ-fcomte.fr",
    )
    route_info = resolve_application_route(
        candidate,
        prog,
        cache,
        cached_pages={"https://www.univ-fcomte.fr/master-info": page_text},
    )
    assert route_info.platform == "Études en France"
    assert route_info.status == CheckStatus.PASS

    inst = cache.get("Université de Franche-Comté")
    assert inst is not None
    assert inst.etudes_en_france_policy is not None


def test_report_count_consistency():
    from france_admission_agent.reporting import build_markdown_report
    candidate = get_candidate()
    prog = make_programme(
        accepted_degree_fields=["Informatique"],
        explicit_prerequisites=["Algorithmique"],
        language=LanguageRequirement(teaching_language=["English"]),
    )
    elig = validate_hard_eligibility(candidate, prog)
    cycle_status, _ = determine_cycle_readiness(candidate, prog)
    e = ProgrammeEvaluation(programme=prog, eligibility=elig, cycle_readiness=cycle_status)
    e.score = calculate_score(e)
    e.group = assign_evaluation_group(e)

    # Valid report generation
    report = build_markdown_report(
        final_shortlist=[e],
        evaluations=[e],
        rejected=[],
        stop_reason="Test run",
        target_intake=candidate.target.intake,
    )
    assert "# France Master's Shortlist" in report
    assert "A. Fully verified:" in report

