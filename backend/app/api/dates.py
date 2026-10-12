from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DateMessage, DateSession, Participant
from app.ranking.engine import compute_session_scores
from app.schemas.dating import DateSessionOut, DateTranscriptOut, DateMessageOut
from app.services.analysis import latest_analysis, public_analysis_view

router = APIRouter(tags=["dates"])


def _with_names(db: Session, s: DateSession) -> DateSessionOut:
    a = db.get(Participant, s.participant_a_id)
    b = db.get(Participant, s.participant_b_id)
    out = DateSessionOut.model_validate(s)
    out.participant_a_name = a.display_name if a else None
    out.participant_b_name = b.display_name if b else None
    return out


@router.get("/api/dates/{date_id}", response_model=DateSessionOut)
def get_date(date_id: int, db: Session = Depends(get_db)) -> DateSessionOut:
    s = db.get(DateSession, date_id)
    if not s:
        raise HTTPException(status_code=404, detail="Date session not found")
    return _with_names(db, s)


@router.get("/api/dates/{date_id}/transcript", response_model=DateTranscriptOut)
def get_transcript(date_id: int, db: Session = Depends(get_db)) -> DateTranscriptOut:
    s = db.get(DateSession, date_id)
    if not s:
        raise HTTPException(status_code=404, detail="Date session not found")
    messages = (
        db.query(DateMessage)
        .filter(DateMessage.session_id == date_id)
        .order_by(DateMessage.turn_index)
        .all()
    )
    return DateTranscriptOut(
        session=_with_names(db, s),
        messages=[DateMessageOut.model_validate(m) for m in messages],
    )


@router.post("/api/dates/{date_id}/evaluate", response_model=DateSessionOut)
def evaluate_date(date_id: int, db: Session = Depends(get_db)) -> DateSessionOut:
    s = db.get(DateSession, date_id)
    if not s:
        raise HTTPException(status_code=404, detail="Date session not found")
    messages = (
        db.query(DateMessage)
        .filter(DateMessage.session_id == date_id)
        .order_by(DateMessage.turn_index)
        .all()
    )
    if not messages:
        raise HTTPException(status_code=400, detail="No transcript to evaluate")

    a = latest_analysis(db, s.participant_a_id)
    b = latest_analysis(db, s.participant_b_id)
    if not a or not b:
        raise HTTPException(status_code=400, detail="Analyses required")

    transcript = [
        {
            "speaker_participant_id": m.speaker_participant_id,
            "message": m.message,
            "question": m.question,
            "intent": m.intent,
        }
        for m in messages
    ]
    eval_a = s.agent_a_feedback or {
        "compatibility_estimate": 50,
        "confidence": 0.4,
        "potential_friction": [],
        "unanswered_questions": [],
    }
    eval_b = s.agent_b_feedback or {
        "compatibility_estimate": 50,
        "confidence": 0.4,
        "potential_friction": [],
        "unanswered_questions": [],
    }
    scored = compute_session_scores(
        analysis_a=public_analysis_view(a),
        analysis_b=public_analysis_view(b),
        eval_a=eval_a,
        eval_b=eval_b,
        transcript=transcript,
    )
    s.compatibility_score = scored["compatibility_score"]
    s.confidence = scored["confidence"]
    s.score_breakdown = scored["score_breakdown"]
    s.shared_interests = scored["shared_interests"]
    s.potential_friction = scored["potential_friction"]
    s.unanswered_questions = scored["unanswered_questions"]
    s.date_summary = scored["date_summary"]
    db.commit()
    db.refresh(s)
    return _with_names(db, s)
