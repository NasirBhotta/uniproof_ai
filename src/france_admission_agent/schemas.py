from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNVERIFIED = "UNVERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

    @classmethod
    def _missing_(cls, value: object) -> CheckStatus | None:
        if isinstance(value, str):
            v = value.upper()
            if v in ("UNCERTAIN", "UNKNOWN", "PENDING"):
                return cls.UNVERIFIED
            if v in ("REVIEW", "CONTRADICTION", "CONTAMINATED"):
                return cls.REVIEW_REQUIRED
        return None


class LanguageStatus(str, Enum):
    VERIFIED_ENGLISH = "VERIFIED_ENGLISH"
    VERIFIED_FRENCH = "VERIFIED_FRENCH"
    VERIFIED_MIXED = "VERIFIED_MIXED"
    LANGUAGE_UNVERIFIED = "LANGUAGE_UNVERIFIED"
    LANGUAGE_REQUIREMENT_UNVERIFIED = "LANGUAGE_REQUIREMENT_UNVERIFIED"
    LANGUAGE_INCOMPATIBLE = "LANGUAGE_INCOMPATIBLE"


class CycleStatus(str, Enum):
    OPEN = "OPEN"
    PENDING_PUBLICATION = "PENDING_PUBLICATION"
    VERIFIED_NOT_OPEN = "VERIFIED_NOT_OPEN"
    CLOSED = "CLOSED"
    UNVERIFIED = "UNVERIFIED"


class ScoreStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"


class IELTSProfile(BaseModel):
    overall: float
    listening: float
    reading: float
    writing: float
    speaking: float
    official_trf_verified: bool = False


class DegreeProfile(BaseModel):
    title: str
    institution: str
    campus: str | None = None
    duration_years: int
    credits: int | None = None
    cgpa: float
    scale: float
    completed: str
    medium_of_instruction: str | None = None


class TargetPreferences(BaseModel):
    public_university: bool = True
    outside_paris_strongly_preferred: bool = True
    smaller_or_medium_city_preferred: bool = True
    lower_international_visibility_preferred: bool = True
    english_taught_strongly_preferred: bool = True


class TargetProfile(BaseModel):
    country: str
    level: Literal["M1", "M2"]
    intake: str
    preferred_fields: list[str] = Field(default_factory=list)
    preferences: TargetPreferences


class CandidateProfile(BaseModel):
    candidate_id: str
    nationality: str
    target: TargetProfile
    degree: DegreeProfile
    ielts: IELTSProfile
    french: dict
    coursework: list[str] = Field(default_factory=list)
    experience: dict = Field(default_factory=dict)
    projects: list[str] = Field(default_factory=list)
    rules: dict = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    claim: str
    value: str | int | float | bool | None = None
    source_url: HttpUrl | str | None = None
    source_type: Literal[
        "official_university",
        "official_government",
        "campus_france",
        "official_pdf",
        "third_party",
    ]
    retrieved_at: str | None = None
    evidence_text: str | None = None
    university: str | None = None
    programme: str | None = None
    track: str | None = None


class CycleInfo(BaseModel):
    """Canonical single-source-of-truth object for cycle readiness."""
    target_intake: str = "2027"
    status: CycleStatus = CycleStatus.UNVERIFIED
    opening_date: str | None = None
    deadline: str | None = None
    source: str | None = None
    last_verified: str | None = None


class TeachingLanguageInfo(BaseModel):
    status: LanguageStatus = LanguageStatus.LANGUAGE_UNVERIFIED
    values: list[str] = Field(default_factory=list)
    evidence: str | None = None
    source_url: str | None = None


class EnglishRequirementInfo(BaseModel):
    status: LanguageStatus = LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED
    cefr: str | None = None
    ielts_overall: float | None = None
    ielts_speaking: float | None = None
    ielts_listening: float | None = None
    ielts_reading: float | None = None
    ielts_writing: float | None = None
    evidence: str | None = None
    source_url: str | None = None


class FrenchRequirementInfo(BaseModel):
    status: LanguageStatus = LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED
    cefr: str | None = None
    certificate_required: bool | None = None
    evidence: str | None = None
    source_url: str | None = None


class ProgrammeStructureInfo(BaseModel):
    m1_entry: CheckStatus = CheckStatus.UNVERIFIED
    m1_tracks: list[str] = Field(default_factory=list)
    m2_tracks: list[str] = Field(default_factory=list)
    specialization_starts_in: Literal["M1", "M2", "UNVERIFIED"] = "UNVERIFIED"
    evidence: str | None = None
    source_url: str | None = None


class TranscriptMatchResultInfo(BaseModel):
    status: CheckStatus = CheckStatus.UNVERIFIED
    required_topics: list[str] = Field(default_factory=list)
    matched_topics: list[str] = Field(default_factory=list)
    unmatched_topics: list[str] = Field(default_factory=list)
    matched_candidate_courses: list[str] = Field(default_factory=list)
    coverage: float = 0.0

    @property
    def matched_courses(self) -> list[str]:
        return self.matched_candidate_courses

    @property
    def percentage(self) -> float:
        return round(self.coverage * 100.0, 1)


TranscriptMatchItem = TranscriptMatchResultInfo



class LanguageRequirement(BaseModel):
    teaching_language: list[str] = Field(default_factory=list)
    ielts_accepted: bool | None = None
    ielts_overall_min: float | None = None
    ielts_listening_min: float | None = None
    ielts_reading_min: float | None = None
    ielts_writing_min: float | None = None
    ielts_speaking_min: float | None = None
    toefl_min: float | None = None
    english_cefr_required: str | None = None
    french_level_required: str | None = None
    french_cefr_required: str | None = None
    english_medium_waiver_possible: bool | None = None


class ApplicationRouteInfo(BaseModel):
    platform: str | None = None
    status: CheckStatus = CheckStatus.UNVERIFIED
    candidate_country_rule: str | None = None
    university_instruction: str | None = None
    target_cycle: str | None = None
    opening_date: str | None = None
    deadline: str | None = None
    evidence: str | None = None
    source_url: str | None = None
    unresolved_items: list[str] = Field(default_factory=list)


class EvidenceMatrixItem(BaseModel):
    status: CheckStatus | CycleStatus | LanguageStatus | str = CheckStatus.UNVERIFIED
    evidence: str | None = None
    source_url: str | None = None


class ProgrammeEvidenceMatrix(BaseModel):
    degree_compatibility: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CheckStatus.UNVERIFIED))
    m1_eligibility: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CheckStatus.UNVERIFIED))
    programme_structure: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CheckStatus.UNVERIFIED))
    academic_prerequisites: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CheckStatus.UNVERIFIED))
    transcript_match: TranscriptMatchResultInfo = Field(default_factory=TranscriptMatchResultInfo)
    teaching_language: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=LanguageStatus.LANGUAGE_UNVERIFIED))
    english_requirement: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED))
    french_requirement: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=LanguageStatus.LANGUAGE_REQUIREMENT_UNVERIFIED))
    application_route: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CheckStatus.UNVERIFIED))
    cycle_2027: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status=CycleStatus.UNVERIFIED))
    capacity: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status="UNVERIFIED"))
    selectivity: EvidenceMatrixItem = Field(default_factory=lambda: EvidenceMatrixItem(status="UNVERIFIED"))


class ProgrammeCandidate(BaseModel):
    programme_id: str
    university: str
    programme: str
    track: str | None = None
    level: Literal["M1", "M2"]
    city: str
    campus: str | None = None
    public: bool | None = None
    programme_url: HttpUrl | str | None = None

    # Canonical cycle object
    canonical_cycle: CycleInfo = Field(default_factory=CycleInfo)

    # Legacy fields maintained for backward compatibility
    application_route: str | None = None
    application_route_info: ApplicationRouteInfo | None = None
    deadline: str | None = None
    deadline_cycle: str | None = None
    cycle_status: CycleStatus = CycleStatus.UNVERIFIED

    # Specific language structures
    language: LanguageRequirement = Field(default_factory=LanguageRequirement)
    teaching_language_info: TeachingLanguageInfo = Field(default_factory=TeachingLanguageInfo)
    english_req_info: EnglishRequirementInfo = Field(default_factory=EnglishRequirementInfo)
    french_req_info: FrenchRequirementInfo = Field(default_factory=FrenchRequirementInfo)

    # Structure and transcript
    programme_structure: ProgrammeStructureInfo = Field(default_factory=ProgrammeStructureInfo)
    transcript_match_info: TranscriptMatchResultInfo = Field(default_factory=TranscriptMatchResultInfo)

    explicit_prerequisites: list[str] = Field(default_factory=list)
    accepted_degree_fields: list[str] = Field(default_factory=list)
    minimum_gpa_text: str | None = None
    excellence_wording: str | None = None

    capacity: int | None = None
    applicant_count: int | None = None
    admitted_count: int | None = None
    entrance_exam_required: bool | None = None
    interview_required: bool | None = None

    official_university_domain: str | None = None
    official_sources: list[EvidenceItem] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    evidence_matrix: ProgrammeEvidenceMatrix = Field(default_factory=ProgrammeEvidenceMatrix)
    scope_mismatch_flags: list[str] = Field(default_factory=list)
    validation_status: CheckStatus = CheckStatus.PASS
    validation_notes: list[str] = Field(default_factory=list)


class HardEligibilityResult(BaseModel):
    degree_field: CheckStatus = CheckStatus.UNVERIFIED
    level: CheckStatus = CheckStatus.UNVERIFIED
    language: CheckStatus = CheckStatus.UNVERIFIED
    french: CheckStatus = CheckStatus.UNVERIFIED
    application_route: CheckStatus = CheckStatus.UNVERIFIED
    deadline: CheckStatus = CheckStatus.UNVERIFIED
    evidence: CheckStatus = CheckStatus.UNVERIFIED
    hard_fail: bool = False
    reasons: list[str] = Field(default_factory=list)


class SkepticReview(BaseModel):
    fatal_issue: bool = False
    evidence_backed_risks: list[str] = Field(default_factory=list)
    general_heuristics: list[str] = Field(default_factory=list)
    serious_risks: list[str] = Field(default_factory=list)  # Backward compat
    unresolved_questions: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    profile_fit_score: float = 0.0
    evidence_confidence_score: float = 0.0
    status: ScoreStatus = ScoreStatus.PROVISIONAL
    status_reason: str | None = None

    # Component sub-scores
    hard_eligibility: float = 0.0
    transcript_match: float = 0.0
    academic_competitiveness: float = 0.0
    language_compatibility: float = 0.0
    regional_visibility: float = 0.0
    application_route: float = 0.0
    sop_project_alignment: float = 0.0
    evidence_quality: float = 0.0
    total: float = 0.0  # Kept as alias to profile_fit_score


class ProgrammeEvaluation(BaseModel):
    programme: ProgrammeCandidate
    eligibility: HardEligibilityResult
    curriculum_coverage: float = 0.0
    skeptic: SkepticReview = Field(default_factory=SkepticReview)
    score: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    cycle_readiness: CycleStatus = CycleStatus.UNVERIFIED
    classification: str = "Unscored"
    group: Literal[
        "A_FULLY_VERIFIED",
        "B_CALENDAR_PENDING",
        "C_LANGUAGE_VERIFICATION_REQUIRED",
        "D_NEEDS_OTHER_VERIFICATION",
        "E_REJECTED",
    ] = "D_NEEDS_OTHER_VERIFICATION"
    final_ready: bool = False
    rejected: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    validation_status: CheckStatus = CheckStatus.PASS
    validation_notes: list[str] = Field(default_factory=list)
