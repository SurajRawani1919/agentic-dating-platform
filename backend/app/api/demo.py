from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DateSession, DemoRun, Participant, Ranking
from app.schemas.dating import RunOut
from app.seed_demo import DEMO_RUN_NAME, seed_demo

router = APIRouter(tags=["demo"])


@router.get("/api/demo")
def get_demo(db: Session = Depends(get_db)) -> dict:
    run = (
        db.query(DemoRun)
        .filter(DemoRun.mode == "demo", DemoRun.name == DEMO_RUN_NAME)
        .order_by(DemoRun.id.desc())
        .first()
    )
    if not run:
        # Auto-seed for convenience in local/demo environments
        run_id = seed_demo(reset=True)
        db.expire_all()
        run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=500, detail="Demo seed failed")

    synth_count = db.query(Participant).filter(Participant.is_synthetic.is_(True)).count()
    first_synth = (
        db.query(Participant)
        .filter(Participant.is_synthetic.is_(True))
        .order_by(Participant.id)
        .first()
    )
    showcase = (
        db.query(DateSession)
        .filter(DateSession.run_id == run.id, DateSession.is_demo_replay.is_(True))
        .order_by(DateSession.id)
        .limit(8)
        .all()
    )
    # Prefer sessions with more messages — pick known richer ones by higher turn
    showcase_ids = [s.id for s in showcase if s.current_turn >= 6][:5] or [s.id for s in showcase[:5]]

    ranking_sample = (
        db.query(Ranking)
        .filter(Ranking.run_id == run.id)
        .order_by(Ranking.participant_id, Ranking.rank)
        .limit(24)
        .all()
    )

    return {
        "label": "SYNTHETIC DEMO — not verified real participants",
        "run": RunOut.model_validate(run).model_dump(),
        "synthetic_participant_count": synth_count,
        "session_count": run.session_count,
        "ranking_count": db.query(Ranking).filter(Ranking.run_id == run.id).count(),
        "showcase_date_ids": showcase_ids,
        "first_participant_id": first_synth.id if first_synth else 0,
        "notes": [
            "All demo participants are synthetic.",
            "Source links are placeholders and are not verified real profiles.",
            "Transcripts are labeled demo replays, not live LLM calls.",
            "Use live mode with consented real profile text and LLM_API_KEY for real AI dating.",
        ],
        "sample_top_ranks": [
            {
                "participant_id": r.participant_id,
                "candidate_id": r.candidate_id,
                "rank": r.rank,
                "score": r.compatibility_score,
            }
            for r in ranking_sample
        ],
    }


@router.get("/api/demo/{run_id}", response_model=RunOut)
def get_demo_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run or run.mode != "demo":
        raise HTTPException(status_code=404, detail="Demo run not found")
    return RunOut.model_validate(run)


@router.post("/api/demo/seed", response_model=RunOut)
def reseed_demo(db: Session = Depends(get_db)) -> RunOut:
    run_id = seed_demo(reset=True)
    # Need new session after seed closed its own
    from app.db.session import SessionLocal

    fresh = SessionLocal()
    try:
        run = fresh.get(DemoRun, run_id)
        if not run:
            raise HTTPException(status_code=500, detail="Seed failed")
        return RunOut.model_validate(run)
    finally:
        fresh.close()
