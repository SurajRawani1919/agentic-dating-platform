from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.source_providers.url_validation import normalize_instagram_url, normalize_linkedin_url


class SourceContentInput(BaseModel):
    linkedin_text: str = Field(default="", max_length=20000)
    instagram_text: str = Field(default="", max_length=20000)


class ParticipantCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    linkedin_url: str = Field(min_length=8, max_length=500)
    instagram_url: str = Field(min_length=8, max_length=500)
    adult_eligibility_confirmed: bool
    consent_to_agent_dating: bool
    linkedin_text: str = Field(default="", max_length=20000)
    instagram_text: str = Field(default="", max_length=20000)

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("display_name is required")
        return name

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin(cls, v: str) -> str:
        return normalize_linkedin_url(v)

    @field_validator("instagram_url")
    @classmethod
    def validate_instagram(cls, v: str) -> str:
        return normalize_instagram_url(v)

    @model_validator(mode="after")
    def require_consent(self) -> "ParticipantCreate":
        if not self.adult_eligibility_confirmed:
            raise ValueError("Adult eligibility confirmation is required")
        if not self.consent_to_agent_dating:
            raise ValueError("Explicit consent for agent dating is required")
        return self


class SourceRecordOut(BaseModel):
    id: int
    source_type: Literal["linkedin", "instagram"]
    submitted_url: str
    acquisition_method: str
    acquisition_status: str
    verification_notes: str
    permitted_content_preview: str
    fetched_at: datetime | None

    model_config = {"from_attributes": True}


class ParticipantOut(BaseModel):
    id: int
    display_name: str
    linkedin_url: str
    instagram_url: str
    source_verification_status: str
    consent_status: str
    adult_eligibility_confirmed: bool
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime
    sources: list[SourceRecordOut] = []
    has_analysis: bool = False

    model_config = {"from_attributes": True}


class EvidenceItem(BaseModel):
    value: str
    evidence: str
    source_type: Literal["linkedin", "instagram", "conversation"]
    confidence: float = Field(ge=0, le=1)


class AnalysisOut(BaseModel):
    id: int
    participant_id: int
    summary: str
    interests: list[Any]
    hobbies: list[Any]
    explicitly_stated_preferences: list[Any]
    communication_clues: list[Any]
    lifestyle_clues: list[Any]
    relationship_preferences: list[Any]
    evidence_items: list[Any]
    uncertainty_notes: list[Any]
    confidence_by_attribute: dict[str, Any]
    source_coverage: dict[str, Any]
    contradictions: list[Any]
    missing_information: list[Any]
    model_name: str
    prompt_version: str
    status: str
    is_demo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisResultSchema(BaseModel):
    """Structured LLM / deterministic analysis output."""

    summary: str
    interests: list[EvidenceItem] = []
    hobbies: list[EvidenceItem] = []
    explicit_preferences: list[EvidenceItem] = []
    communication_clues: list[EvidenceItem] = []
    lifestyle_clues: list[EvidenceItem] = []
    relationship_preferences: list[EvidenceItem] = []
    contradictions: list[str] = []
    uncertainties: list[str] = []
    missing_information: list[str] = []
    confidence_by_attribute: dict[str, float] = {}
    source_coverage: dict[str, Any] = {}
