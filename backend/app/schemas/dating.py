from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


_INTENTS = {
    "open",
    "learn_preferences",
    "share_interest",
    "clarify",
    "address_friction",
    "close",
    "evaluate",
}


def _unit_interval(value: Any) -> float:
    """Coerce a model-provided score onto 0-1 (models sometimes answer 0-100)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if number > 1:
        number /= 100
    return max(0.0, min(1.0, number))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(i).strip() for i in items if str(i).strip()][:12]


class AgentMessageSchema(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    question: str = Field(default="", max_length=1000)
    referenced_interests: list[str] = []
    intent: Literal[
        "open",
        "learn_preferences",
        "share_interest",
        "clarify",
        "address_friction",
        "close",
        "evaluate",
    ] = "learn_preferences"
    confidence: float = Field(ge=0, le=1, default=0.5)

    @field_validator("question", mode="before")
    @classmethod
    def _question(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("intent", mode="before")
    @classmethod
    def _intent(cls, v: Any) -> str:
        text = str(v or "").strip().lower()
        return text if text in _INTENTS else "learn_preferences"

    @field_validator("referenced_interests", mode="before")
    @classmethod
    def _interests(cls, v: Any) -> list[str]:
        return _string_list(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> float:
        return _unit_interval(v)


class AgentEvaluationSchema(BaseModel):
    """One agent's private verdict on how well the other person fits its own person."""

    verdict: str = ""
    overall_impression: str = ""
    shared_interests: list[str] = []
    needs_met: list[str] = []
    needs_unmet: list[str] = []
    potential_friction: list[str] = []
    unanswered_questions: list[str] = []
    compatibility_estimate: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1, default=0.5)
    reasoning: str = ""

    @field_validator(
        "shared_interests",
        "needs_met",
        "needs_unmet",
        "potential_friction",
        "unanswered_questions",
        mode="before",
    )
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        return _string_list(v)

    @field_validator("verdict", "overall_impression", "reasoning", mode="before")
    @classmethod
    def _text(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("compatibility_estimate", mode="before")
    @classmethod
    def _estimate(cls, v: Any) -> float:
        try:
            number = float(v)
        except (TypeError, ValueError):
            return 50.0
        if 0 < number <= 1:  # answered as a fraction
            number *= 100
        return max(0.0, min(100.0, number))

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> float:
        return _unit_interval(v)


class RunCreate(BaseModel):
    name: str = Field(default="Dating Run", max_length=200)
    mode: Literal["demo", "live"] = "live"
    participant_ids: list[int] | None = None
    max_turns: int = Field(default=6, ge=2, le=12)
    session_budget: int | None = Field(default=None, ge=1, le=300)


class RunOut(BaseModel):
    id: int
    name: str
    mode: str
    status: str
    participant_count: int
    session_count: int
    completed_sessions: int
    progress: float
    error_summary: str
    max_turns: int
    config: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DateMessageOut(BaseModel):
    id: int
    speaker_participant_id: int
    turn_index: int
    message: str
    question: str
    referenced_interests: list[Any]
    intent: str
    confidence: float
    is_live_llm: bool
    model_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DateSessionOut(BaseModel):
    id: int
    participant_a_id: int
    participant_b_id: int
    run_id: int
    status: str
    current_turn: int
    max_turns: int
    date_summary: str
    shared_interests: list[Any]
    potential_friction: list[Any]
    unanswered_questions: list[Any]
    agent_a_feedback: dict[str, Any]
    agent_b_feedback: dict[str, Any]
    compatibility_score: float | None
    confidence: float | None
    score_breakdown: dict[str, Any]
    is_demo_replay: bool
    error_message: str
    created_at: datetime
    completed_at: datetime | None
    participant_a_name: str | None = None
    participant_b_name: str | None = None

    model_config = {"from_attributes": True}


class DateTranscriptOut(BaseModel):
    session: DateSessionOut
    messages: list[DateMessageOut]


class DateSessionCreate(BaseModel):
    participant_a_id: int
    participant_b_id: int
    max_turns: int = Field(default=6, ge=2, le=12)
