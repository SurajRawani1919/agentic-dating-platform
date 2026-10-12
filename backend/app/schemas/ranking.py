from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RankingOut(BaseModel):
    id: int
    run_id: int
    participant_id: int
    candidate_id: int
    rank: int
    compatibility_score: float
    confidence: float
    score_breakdown: dict[str, Any]
    positive_evidence: list[Any]
    potential_mismatches: list[Any]
    unanswered_questions: list[Any]
    date_session_id: int | None
    created_at: datetime
    candidate_name: str | None = None
    candidate_is_synthetic: bool | None = None

    model_config = {"from_attributes": True}


class RankingListOut(BaseModel):
    participant_id: int
    participant_name: str
    run_id: int
    rankings: list[RankingOut]
