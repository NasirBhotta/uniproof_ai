from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ClaimKey = Literal[
    "university",
    "programme",
    "track",
    "level",
    "city",
    "public",
    "teaching_language",
    "ielts_accepted",
    "ielts_overall_min",
    "ielts_listening_min",
    "ielts_reading_min",
    "ielts_writing_min",
    "ielts_speaking_min",
    "toefl_min",
    "english_cefr_required",
    "french_level_required",
    "french_cefr_required",
    "english_medium_waiver_possible",
    "application_route",
    "deadline",
    "deadline_cycle",
    "explicit_prerequisites",
    "accepted_degree_fields",
    "minimum_gpa_text",
    "excellence_wording",
    "capacity",
    "applicant_count",
    "admitted_count",
    "entrance_exam_required",
    "interview_required",
    "programme_url",
    "official_university_domain",
]


class ProgrammeSeed(BaseModel):
    university: str
    programme: str
    track: str | None = None
    level: Literal["M1", "M2"] = "M1"
    city: str | None = None
    campus: str | None = None
    likely_public: bool | None = None
    source_url: str
    source_title: str | None = None


class ProgrammeSeedBatch(BaseModel):
    programmes: list[ProgrammeSeed] = Field(default_factory=list)


class ExtractedClaim(BaseModel):
    claim_key: ClaimKey
    claim_value: str | int | float | bool | None = None
    source_url: str
    excerpt: str | None = None


class ProgrammeVerification(BaseModel):
    university: str
    programme: str
    track: str | None = None
    level: Literal["M1", "M2"] = "M1"
    city: str
    campus: str | None = None
    public: bool | None = None

    teaching_languages: list[str] = Field(default_factory=list)
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

    application_route: str | None = None
    deadline: str | None = None
    deadline_cycle: str | None = None

    explicit_prerequisites: list[str] = Field(default_factory=list)
    accepted_degree_fields: list[str] = Field(default_factory=list)
    minimum_gpa_text: str | None = None
    excellence_wording: str | None = None

    capacity: int | None = None
    applicant_count: int | None = None
    admitted_count: int | None = None
    entrance_exam_required: bool | None = None
    interview_required: bool | None = None

    programme_url: str | None = None
    official_university_domain: str | None = None
    claims: list[ExtractedClaim] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
