from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.participant_agent import ParticipantAgent
from app.core.config import get_settings
from app.models import DateMessage, DateSession, DemoRun, Participant
from app.ranking.engine import compute_session_scores
from app.services.analysis import latest_analysis, public_analysis_view


def ordered_ids(a: int, b: int) -> tuple[int, int]:
    if a == b:
        raise ValueError("Self-dates are not allowed")
    return (a, b) if a < b else (b, a)


def unique_pairs(participant_ids: list[int]) -> list[tuple[int, int]]:
    ids = sorted(set(participant_ids))
    pairs: list[tuple[int, int]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            pairs.append((a, b))
    return pairs


async def run_date(
    db: Session,
    session: DateSession,
    *,
    cancel_event: threading.Event | None = None,
    force_deterministic: bool = False,
) -> DateSession:
    settings = get_settings()
    a = db.get(Participant, session.participant_a_id)
    b = db.get(Participant, session.participant_b_id)
    if not a or not b:
        session.status = "failed"
        session.error_message = "Participant missing"
        db.commit()
        return session

    analysis_a = latest_analysis(db, a.id)
    analysis_b = latest_analysis(db, b.id)
    if not analysis_a or not analysis_b:
        session.status = "failed"
        session.error_message = "Both participants require profile analysis before dating"
        db.commit()
        return session

    agent_a = ParticipantAgent(a.id, a.display_name, public_analysis_view(analysis_a))
    agent_b = ParticipantAgent(b.id, b.display_name, public_analysis_view(analysis_b))

    session.status = "in_progress"
    session.error_message = ""
    db.commit()

    # Load existing messages for resume
    existing = (
        db.query(DateMessage)
        .filter(DateMessage.session_id == session.id)
        .order_by(DateMessage.turn_index)
        .all()
    )
    transcript: list[dict[str, Any]] = [
        {
            "speaker_participant_id": m.speaker_participant_id,
            "message": m.message,
            "question": m.question,
            "intent": m.intent,
            "referenced_interests": list(m.referenced_interests or []),
        }
        for m in existing
    ]
    start_turn = len(existing)
    max_turns = session.max_turns or settings.default_max_turns
    speakers = [agent_a, agent_b]

    for turn in range(start_turn, max_turns):
        if cancel_event and cancel_event.is_set():
            session.status = "cancelled"
            db.commit()
            return session

        speaker = speakers[turn % 2]
        peer = speakers[(turn + 1) % 2]
        try:
            msg, is_live, model = await speaker.generate_turn(
                turn_index=turn,
                max_turns=max_turns,
                peer_name=peer.display_name,
                transcript=transcript,
                force_deterministic=force_deterministic,
            )
        except Exception as exc:  # noqa: BLE001
            session.status = "failed"
            session.error_message = f"Turn {turn} failed: {exc}"
            db.commit()
            return session

        row = DateMessage(
            session_id=session.id,
            speaker_participant_id=speaker.participant_id,
            turn_index=turn,
            message=msg.message,
            question=msg.question or "",
            referenced_interests=msg.referenced_interests,
            intent=msg.intent,
            confidence=msg.confidence,
            is_live_llm=is_live,
            model_name=model,
        )
        db.add(row)
        session.current_turn = turn + 1
        db.commit()

        transcript.append(
            {
                "speaker_participant_id": speaker.participant_id,
                "message": msg.message,
                "question": msg.question,
                "intent": msg.intent,
                "referenced_interests": list(msg.referenced_interests),
            }
        )

    # Independent verdicts — each agent judges from its own profile + the transcript only
    (eval_a, _, _), (eval_b, _, _) = await asyncio.gather(
        agent_a.evaluate(transcript, b.display_name, force_deterministic=force_deterministic),
        agent_b.evaluate(transcript, a.display_name, force_deterministic=force_deterministic),
    )

    breakdown = compute_session_scores(
        analysis_a=public_analysis_view(analysis_a),
        analysis_b=public_analysis_view(analysis_b),
        eval_a=eval_a.model_dump(),
        eval_b=eval_b.model_dump(),
        transcript=transcript,
    )

    session.agent_a_feedback = eval_a.model_dump()
    session.agent_b_feedback = eval_b.model_dump()
    session.shared_interests = breakdown["shared_interests"]
    session.potential_friction = breakdown["potential_friction"]
    session.unanswered_questions = breakdown["unanswered_questions"]
    session.compatibility_score = breakdown["compatibility_score"]
    session.confidence = breakdown["confidence"]
    session.score_breakdown = breakdown["score_breakdown"]
    verdicts = " ".join(
        f"{agent.first_name}'s agent: {verdict}"
        for agent, verdict in ((agent_a, eval_a.verdict), (agent_b, eval_b.verdict))
        if verdict
    )
    session.date_summary = f"{breakdown['date_summary']} {verdicts}".strip()
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    # Only the seeded synthetic sample is a replay; this conversation just happened.
    session.is_demo_replay = False
    db.commit()
    db.refresh(session)
    return session


async def execute_run(
    db_factory,
    run_id: int,
    *,
    cancel_event: threading.Event | None = None,
    force_deterministic: bool = False,
) -> None:
    settings = get_settings()
    db: Session = db_factory()
    try:
        run = db.get(DemoRun, run_id)
        if not run:
            return
        run.status = "running"
        db.commit()

        sessions = (
            db.query(DateSession)
            .filter(
                DateSession.run_id == run_id,
                DateSession.status.in_(["pending", "failed", "cancelled", "in_progress"]),
            )
            .all()
        )
        # Resume: skip fully completed
        pending = [s for s in sessions if s.status != "completed"]
        sem = asyncio.Semaphore(settings.max_concurrent_dates)
        errors: list[str] = []

        async def _one(session_id: int) -> None:
            async with sem:
                if cancel_event and cancel_event.is_set():
                    return
                local = db_factory()
                try:
                    sess = local.get(DateSession, session_id)
                    if not sess or sess.status == "completed":
                        return
                    await run_date(
                        local,
                        sess,
                        cancel_event=cancel_event,
                        force_deterministic=force_deterministic or run.mode == "demo",
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"session {session_id}: {exc}")
                finally:
                    # refresh run progress
                    try:
                        r = local.get(DemoRun, run_id)
                        if r:
                            total = r.session_count or 1
                            done = (
                                local.query(DateSession)
                                .filter(
                                    DateSession.run_id == run_id,
                                    DateSession.status == "completed",
                                )
                                .count()
                            )
                            r.completed_sessions = done
                            r.progress = round(100.0 * done / total, 2)
                            local.commit()
                    finally:
                        local.close()

        await asyncio.gather(*[_one(s.id) for s in pending])

        run = db.get(DemoRun, run_id)
        if not run:
            return
        if cancel_event and cancel_event.is_set():
            run.status = "cancelled"
        else:
            failed = (
                db.query(DateSession)
                .filter(DateSession.run_id == run_id, DateSession.status == "failed")
                .count()
            )
            done = (
                db.query(DateSession)
                .filter(DateSession.run_id == run_id, DateSession.status == "completed")
                .count()
            )
            run.completed_sessions = done
            run.progress = round(100.0 * done / max(run.session_count, 1), 2)
            failures = [
                f"date {s.id}: {s.error_message}"
                for s in db.query(DateSession)
                .filter(DateSession.run_id == run_id, DateSession.status == "failed")
                .limit(10)
            ]
            run.error_summary = "; ".join((errors + failures)[:10])
            if failed and done == 0:
                run.status = "failed"
            else:
                run.status = "completed_with_errors" if failed else "completed"
                run.completed_at = datetime.now(timezone.utc)
                # Rank from every date that did finish, even if a few failed.
                from app.ranking.engine import aggregate_rankings

                db.commit()
                aggregate_rankings(db, run_id)
        db.commit()
    finally:
        db.close()
