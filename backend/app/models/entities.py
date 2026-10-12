from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    linkedin_url: Mapped[str] = mapped_column(String(500), nullable=False)
    instagram_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_verification_status: Mapped[str] = mapped_column(
        String(50), default="unverified", nullable=False
    )
    consent_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    adult_eligibility_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sources: Mapped[list[SourceRecord]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    analyses: Mapped[list[ProfileAnalysis]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # linkedin | instagram
    submitted_url: Mapped[str] = mapped_column(String(500), nullable=False)
    acquisition_method: Mapped[str] = mapped_column(String(50), nullable=False)
    permitted_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    acquisition_status: Mapped[str] = mapped_column(String(50), nullable=False)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="sources")

    __table_args__ = (
        CheckConstraint("source_type IN ('linkedin', 'instagram')", name="ck_source_type"),
        UniqueConstraint("participant_id", "source_type", name="uq_participant_source_type"),
    )


class ProfileAnalysis(Base):
    __tablename__ = "profile_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    headline: Mapped[Optional[str]] = mapped_column(String(400), default="", nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    needs: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    interests: Mapped[Any] = mapped_column(JSON, default=list)
    hobbies: Mapped[Any] = mapped_column(JSON, default=list)
    core_values: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    personality_traits: Mapped[Any] = mapped_column(JSON, default=list, nullable=True)
    ideal_date: Mapped[Optional[str]] = mapped_column(Text, default="", nullable=True)
    explicitly_stated_preferences: Mapped[Any] = mapped_column(JSON, default=list)
    communication_clues: Mapped[Any] = mapped_column(JSON, default=list)
    lifestyle_clues: Mapped[Any] = mapped_column(JSON, default=list)
    relationship_preferences: Mapped[Any] = mapped_column(JSON, default=list)
    evidence_items: Mapped[Any] = mapped_column(JSON, default=list)
    uncertainty_notes: Mapped[Any] = mapped_column(JSON, default=list)
    confidence_by_attribute: Mapped[Any] = mapped_column(JSON, default=dict)
    source_coverage: Mapped[Any] = mapped_column(JSON, default=dict)
    contradictions: Mapped[Any] = mapped_column(JSON, default=list)
    missing_information: Mapped[Any] = mapped_column(JSON, default=list)
    model_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participant: Mapped[Participant] = relationship(back_populates="analyses")


class DemoRun(Base):
    __tablename__ = "demo_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # demo | live
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_sessions: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    max_turns: Mapped[int] = mapped_column(Integer, default=6)
    config: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[DateSession]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    rankings: Mapped[list[Ranking]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("mode IN ('demo', 'live')", name="ck_run_mode"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_run_progress"),
    )


class DateSession(Base):
    __tablename__ = "date_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_a_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    participant_b_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("demo_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    current_turn: Mapped[int] = mapped_column(Integer, default=0)
    max_turns: Mapped[int] = mapped_column(Integer, default=6)
    date_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    shared_interests: Mapped[Any] = mapped_column(JSON, default=list)
    potential_friction: Mapped[Any] = mapped_column(JSON, default=list)
    unanswered_questions: Mapped[Any] = mapped_column(JSON, default=list)
    agent_a_feedback: Mapped[Any] = mapped_column(JSON, default=dict)
    agent_b_feedback: Mapped[Any] = mapped_column(JSON, default=dict)
    compatibility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[Any] = mapped_column(JSON, default=dict)
    is_demo_replay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[DemoRun] = relationship(back_populates="sessions")
    messages: Mapped[list[DateMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="DateMessage.turn_index"
    )

    __table_args__ = (
        CheckConstraint("participant_a_id < participant_b_id", name="ck_ordered_pair"),
        CheckConstraint("participant_a_id != participant_b_id", name="ck_no_self_date"),
        UniqueConstraint("run_id", "participant_a_id", "participant_b_id", name="uq_run_pair"),
        CheckConstraint(
            "compatibility_score IS NULL OR (compatibility_score >= 0 AND compatibility_score <= 100)",
            name="ck_compat_score",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_date_confidence",
        ),
    )


class DateMessage(Base):
    __tablename__ = "date_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("date_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker_participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, default="", nullable=False)
    referenced_interests: Mapped[Any] = mapped_column(JSON, default=list)
    intent: Mapped[str] = mapped_column(String(50), default="learn_preferences")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_live_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[DateSession] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_session_turn"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_msg_confidence"),
    )


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("demo_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    compatibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[Any] = mapped_column(JSON, default=dict)
    positive_evidence: Mapped[Any] = mapped_column(JSON, default=list)
    potential_mismatches: Mapped[Any] = mapped_column(JSON, default=list)
    unanswered_questions: Mapped[Any] = mapped_column(JSON, default=list)
    date_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("date_sessions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[DemoRun] = relationship(back_populates="rankings")

    __table_args__ = (
        CheckConstraint("participant_id != candidate_id", name="ck_no_self_rank"),
        UniqueConstraint("run_id", "participant_id", "candidate_id", name="uq_run_rank_pair"),
        UniqueConstraint("run_id", "participant_id", "rank", name="uq_run_participant_rank"),
        CheckConstraint(
            "compatibility_score >= 0 AND compatibility_score <= 100",
            name="ck_rank_score",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_rank_confidence"),
        CheckConstraint("rank >= 1", name="ck_rank_positive"),
    )
