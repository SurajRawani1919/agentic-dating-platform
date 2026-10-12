from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.source_providers.url_validation import normalize_instagram_url, normalize_linkedin_url


class SourceContentInput(BaseModel):
    linkedin_text: str = Field(default="", max_length=20000)
    instagram_text: str = Field(default="", max_length=20000)


class ParticipantCreate(BaseModel):
    # Optional: the name is read from the profiles when left blank.
    display_name: str = Field(default="", max_length=200)
    linkedin_url: str = Field(min_length=8, max_length=500)
    instagram_url: str = Field(min_length=8, max_length=500)
    adult_eligibility_confirmed: bool
    consent_to_agent_dating: bool
    # Fallback only, for when a platform blocks the automatic read.
    linkedin_text: str = Field(default="", max_length=20000)
    instagram_text: str = Field(default="", max_length=20000)

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

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
    # Full text the agent read; only populated on the participant detail endpoint.
    content: str = ""
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
    headline: str = ""

    model_config = {"from_attributes": True}


class EvidenceItem(BaseModel):
    value: str
    evidence: str = ""
    source_type: Literal["linkedin", "instagram", "conversation"] = "linkedin"
    confidence: float = Field(ge=0, le=1, default=0.5)
    # One line on how the evidence supports the claim (used for inferred needs).
    why: str = ""

    @field_validator("source_type", mode="before")
    @classmethod
    def coerce_source(cls, v: Any) -> str:
        text = str(v or "").lower()
        if "insta" in text:
            return "instagram"
        if "conversation" in text:
            return "conversation"
        return "linkedin"

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float:
        try:
            number = float(v)
        except (TypeError, ValueError):
            return 0.5
        if number > 1:  # models sometimes answer on a 0-100 scale
            number /= 100
        return max(0.0, min(1.0, number))

    @field_validator("value", "evidence", "why", mode="before")
    @classmethod
    def coerce_text(cls, v: Any) -> str:
        return "" if v is None else str(v)


class AnalysisOut(BaseModel):
    id: int
    participant_id: int
    headline: str = ""
    summary: str
    needs: list[Any] = []
    interests: list[Any]
    hobbies: list[Any]
    core_values: list[Any] = []
    personality_traits: list[Any] = []
    explicitly_stated_preferences: list[Any]
    communication_clues: list[Any]
    lifestyle_clues: list[Any]
    relationship_preferences: list[Any]
    ideal_date: str = ""
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

    # Rows written before these columns existed hold NULL.
    @field_validator("needs", "core_values", "personality_traits", mode="before")
    @classmethod
    def null_list(cls, v: Any) -> list[Any]:
        return v or []

    @field_validator("headline", "ideal_date", mode="before")
    @classmethod
    def null_text(cls, v: Any) -> str:
        return v or ""


class AnalysisResultSchema(BaseModel):
    """Structured LLM / rule-based analysis output."""

    headline: str = ""
    summary: str
    needs: list[EvidenceItem] = []
    interests: list[EvidenceItem] = []
    hobbies: list[EvidenceItem] = []
    values: list[EvidenceItem] = []
    personality_traits: list[EvidenceItem] = []
    explicit_preferences: list[EvidenceItem] = []
    communication_clues: list[EvidenceItem] = []
    lifestyle_clues: list[EvidenceItem] = []
    relationship_preferences: list[EvidenceItem] = []
    ideal_date: str = ""
    contradictions: list[str] = []
    uncertainties: list[str] = []
    missing_information: list[str] = []
    confidence_by_attribute: dict[str, float] = {}
    source_coverage: dict[str, Any] = {}
