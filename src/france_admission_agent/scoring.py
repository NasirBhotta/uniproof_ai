from __future__ import annotations

from .schemas import (
    CheckStatus,
    CycleStatus,
    LanguageStatus,
    ProgrammeEvaluation,
    ScoreBreakdown,
    ScoreStatus,
)


def _regional_points(e: ProgrammeEvaluation) -> float:
    city = (e.programme.city or "").lower()
    if "paris" in city:
        return 2.0
    pts = 7.0
    if e.programme.public is True:
        pts += 3.0
    return min(10.0, pts)


def _academic_competitiveness_points(e: ProgrammeEvaluation) -> float:
    p = e.programme
    pts = 12.0
    if p.excellence_wording:
        pts -= 3.0
    if p.minimum_gpa_text:
        pts -= 1.5
    if p.entrance_exam_required:
        pts -= 1.0
    return max(0.0, min(15.0, pts))


def calculate_evidence_confidence(e: ProgrammeEvaluation) -> tuple[float, list[str]]:
    """Calculates Evidence Confidence Score (0-100) strictly based on Section 22 weights:
    degree compatibility: 15
    M1 eligibility: 10
    programme structure: 10
    teaching language: 10
    language requirements: 10
    application route: 15
    academic prerequisites: 10
    transcript mapping: 10
    cycle information: 5
    selectivity/capacity: 5
    Total = 100
    """
    p = e.programme
    score = 0.0
    unverified_reasons: list[str] = []

    # 1. Degree compatibility (15 pts)
    if e.eligibility.degree_field == CheckStatus.PASS:
        score += 15.0
    else:
        unverified_reasons.append("degree compatibility unverified")

    # 2. M1 eligibility (10 pts)
    if e.eligibility.level == CheckStatus.PASS:
        score += 10.0
    else:
        unverified_reasons.append("M1 level entry unverified")

    # 3. Programme structure (10 pts)
    if p.programme_structure.m1_entry == CheckStatus.PASS:
        score += 10.0
    elif p.programme_structure.m1_entry == CheckStatus.FAIL:
        unverified_reasons.append("track restricted to M2 entry")
    else:
        unverified_reasons.append("M1/M2 structure unverified")

    # 4. Teaching language (10 pts)
    if p.teaching_language_info.status in (LanguageStatus.VERIFIED_ENGLISH, LanguageStatus.VERIFIED_FRENCH, LanguageStatus.VERIFIED_MIXED):
        score += 10.0
    else:
        unverified_reasons.append("teaching language unverified")

    # 5. Language requirements (10 pts)
    if p.english_req_info.status == LanguageStatus.VERIFIED_ENGLISH or p.french_req_info.status == LanguageStatus.VERIFIED_FRENCH:
        score += 10.0
    else:
        unverified_reasons.append("exact language proof requirements unverified")

    # 6. Application route (15 pts)
    if e.eligibility.application_route == CheckStatus.PASS and not p.scope_mismatch_flags:
        score += 15.0
    else:
        unverified_reasons.append("candidate-specific application route unverified")

    # 7. Academic prerequisites (10 pts)
    if p.explicit_prerequisites:
        score += 10.0
    else:
        unverified_reasons.append("academic prerequisites unverified")

    # 8. Transcript mapping (10 pts)
    t_cov = p.transcript_match_info.coverage
    if t_cov > 0.0 and p.transcript_match_info.matched_candidate_courses:
        score += round(t_cov * 10.0, 1)
    else:
        unverified_reasons.append("transcript course mapping unverified")

    # 9. Cycle information (5 pts)
    if p.canonical_cycle.status == CycleStatus.OPEN:
        score += 5.0
    elif p.canonical_cycle.status == CycleStatus.PENDING_PUBLICATION:
        score += 3.0
    else:
        unverified_reasons.append("cycle calendar unverified")

    # 10. Selectivity / capacity (5 pts)
    if p.capacity is not None or p.applicant_count is not None:
        score += 5.0
    else:
        unverified_reasons.append("capacity/selectivity unverified")

    # Penalty for contamination / scope mismatch
    if p.scope_mismatch_flags:
        score = max(0.0, score - 30.0)
        unverified_reasons.append("EVIDENCE_SCOPE_MISMATCH detected")

    return min(100.0, round(score, 1)), unverified_reasons


def calculate_score(e: ProgrammeEvaluation) -> ScoreBreakdown:
    # If hard fail, profile fit is 0
    if e.eligibility.hard_fail or e.skeptic.fatal_issue:
        return ScoreBreakdown(
            profile_fit_score=0.0,
            evidence_confidence_score=0.0,
            status=ScoreStatus.PROVISIONAL,
            status_reason="Disqualified due to official incompatibility.",
            total=0.0,
        )

    # 1. Degree & M1 Eligibility (max 25)
    hard = 25.0 if (e.eligibility.level == CheckStatus.PASS and e.eligibility.degree_field == CheckStatus.PASS) else 20.0

    # 2. Transcript match / curriculum fit (max 25)
    t_cov = e.programme.transcript_match_info.coverage
    if t_cov > 0.0 and e.programme.transcript_match_info.matched_candidate_courses:
        transcript = 20.0 + (t_cov * 5.0)
    else:
        # Standard baseline for Computer Science M1 when candidate has complete BS CS
        transcript = 18.0

    # 3. Academic competitiveness & GPA (max 15)
    academic = _academic_competitiveness_points(e)

    # 4. Language compatibility (max 15)
    # Candidate has IELTS 6.5 overall (B2 equivalent)
    if e.eligibility.language == CheckStatus.PASS:
        language = 14.0
    elif e.eligibility.language == CheckStatus.UNVERIFIED:
        language = 12.0
    else:
        language = 5.0

    # 5. Regional visibility & public status (max 10)
    regional = _regional_points(e)

    # 6. Practical Software Engineering & Project alignment (max 10)
    sop = 8.0

    profile_fit = min(100.0, round(hard + transcript + academic + language + regional + sop, 1))

    # Evidence Confidence Score (0-100)
    confidence, unverified_items = calculate_evidence_confidence(e)

    # score_status is PROVISIONAL if confidence < 75 or scope flags exist
    if confidence >= 75.0 and not e.programme.scope_mismatch_flags and e.programme.teaching_language_info.status != LanguageStatus.LANGUAGE_UNVERIFIED:
        status = ScoreStatus.VERIFIED
        status_reason = None
    else:
        status = ScoreStatus.PROVISIONAL
        status_reason = "; ".join(unverified_items[:2]) if unverified_items else "Awaiting full verification"

    return ScoreBreakdown(
        profile_fit_score=profile_fit,
        evidence_confidence_score=confidence,
        status=status,
        status_reason=status_reason,
        hard_eligibility=hard,
        transcript_match=round(transcript, 1),
        academic_competitiveness=round(academic, 1),
        language_compatibility=language,
        regional_visibility=regional,
        sop_project_alignment=sop,
        evidence_quality=round(confidence * 0.1, 1),
        total=profile_fit,
    )


def assign_evaluation_group(e: ProgrammeEvaluation) -> str:
    """Classifies programme into one of the five canonical output groups (Section 23):
    A. FULLY VERIFIED
    B. STRONG FIT — 2027 CALENDAR PENDING
    C. STRONG FIT — LANGUAGE VERIFICATION REQUIRED (Very important category!)
    D. NEEDS OTHER VERIFICATION
    E. REJECTED
    """
    if e.rejected or e.eligibility.hard_fail or e.skeptic.fatal_issue:
        return "E_REJECTED"

    p = e.programme
    fit = e.score.profile_fit_score
    conf = e.score.evidence_confidence_score
    cycle = p.canonical_cycle.status

    # Check language status
    is_lang_unverified = (
        p.teaching_language_info.status == LanguageStatus.LANGUAGE_UNVERIFIED
        or p.english_req_info.status == LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED
    )

    # Category C: STRONG FIT — LANGUAGE VERIFICATION REQUIRED
    # Academic & transcript fit is strong, but language proof / teaching language is unverified
    if fit >= 75.0 and is_lang_unverified:
        return "C_LANGUAGE_VERIFICATION_REQUIRED"

    # Category A: FULLY VERIFIED
    # Verified language, verified degree/route, confirmed open cycle
    if fit >= 75.0 and conf >= 75.0 and cycle == CycleStatus.OPEN and not is_lang_unverified:
        return "A_FULLY_VERIFIED"

    # Category B: STRONG FIT — 2027 CALENDAR PENDING
    # Verified academic and language fit, but 2027 calendar is pending publication or cycle not yet open
    if fit >= 72.0 and not is_lang_unverified:
        return "B_CALENDAR_PENDING"

    # Category D: NEEDS OTHER VERIFICATION
    return "D_NEEDS_OTHER_VERIFICATION"



def classification(score: float, final_ready: bool = False, group: str = "D_NEEDS_OTHER_VERIFICATION") -> str:
    if group == "E_REJECTED":
        return "Rejected"
    if group == "A_FULLY_VERIFIED":
        return "Fully Verified Safe Fit"
    if group == "B_CALENDAR_PENDING":
        return "Strong Fit — 2027 Calendar Pending"
    if group == "C_LANGUAGE_VERIFICATION_REQUIRED":
        return "Strong Fit — Language Verification Required"
    if group == "D_NEEDS_OTHER_VERIFICATION":
        return "Needs Other Verification"
    if score >= 80:
        return "Strong safe fit"
    return "Needs verification"
