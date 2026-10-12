from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import DateSession, DemoRun, Participant, Ranking
from app.schemas.dating import RunOut
from app.seed_demo import DEMO_RUN_NAME, seed_demo

router = APIRouter(tags=["demo"])

_FINISHED = ("completed", "completed_with_errors")


def showcase_run(db: Session) -> DemoRun | None:
    """The finished example to show: the largest completed run over real people."""
    return (
        db.query(DemoRun)
        .filter(DemoRun.mode == "live", DemoRun.status.in_(_FINISHED))
        .order_by(DemoRun.participant_count.desc(), DemoRun.id.desc())
        .first()
    )


@router.get("/api/demo")
def get_demo(db: Session = Depends(get_db)) -> dict:
    """The saved, already-run example.

    A finished run over real people always wins. The labeled synthetic sample
    is only a stand-in until such a run exists.
    """
    run = showcase_run(db)
    is_real = run is not None
    if run is None:
        run = (
            db.query(DemoRun)
            .filter(DemoRun.mode == "demo", DemoRun.name == DEMO_RUN_NAME)
            .order_by(DemoRun.id.desc())
            .first()
        )
        if not run:
            run_id = seed_demo(reset=True)
            db.expire_all()
            run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=500, detail="Demo seed failed")

    sessions = (
        db.query(DateSession)
        .filter(DateSession.run_id == run.id, DateSession.status == "completed")
        .all()
    )
    participant_ids = sorted(
        {s.participant_a_id for s in sessions} | {s.participant_b_id for s in sessions}
    )
    # Best conversations first: full-length dates with the highest mutual score.
    showcase = sorted(
        sessions,
        key=lambda s: (-(s.current_turn or 0), -(s.compatibility_score or 0), s.id),
    )[:6]

    top_matches = (
        db.query(Ranking)
        .filter(Ranking.run_id == run.id, Ranking.rank == 1)
        .order_by(Ranking.participant_id)
        .all()
    )
    names = {
        p.id: p.display_name
        for p in db.query(Participant).filter(Participant.id.in_(participant_ids or [0]))
    }

    if is_real:
        engine = (run.config or {}).get("engine", "rule-based")
        label = "Finished run — real people, read from their public LinkedIn + Instagram"
        notes = [
            "Every person here was added by pasting two public links: their LinkedIn and their Instagram.",
            "Each agent read only those two profiles, then dated every other agent one-to-one.",
            f"Dating engine for this run: {engine}.",
            "Rankings are personal: each person's list leans on the verdict of their own agent.",
        ]
    else:
        label = "SYNTHETIC SAMPLE — no real run has been saved yet"
        notes = [
            "These 25 people are invented placeholders, not real profiles.",
            "Their links are fake and their conversations are templated replays.",
            "Paste real LinkedIn + Instagram links in the workspace and run dating to replace this.",
        ]

    return {
        "label": label,
        "is_real": is_real,
        "run": RunOut.model_validate(run).model_dump(),
        "participant_count": len(participant_ids) or run.participant_count,
        "participant_ids": participant_ids,
        "session_count": run.session_count,
        "ranking_count": db.query(Ranking).filter(Ranking.run_id == run.id).count(),
        "showcase_date_ids": [s.id for s in showcase],
        "first_participant_id": participant_ids[0] if participant_ids else 0,
        "video_url": get_settings().demo_video_url,
        "notes": notes,
        "top_matches": [
            {
                "participant_id": r.participant_id,
                "participant_name": names.get(r.participant_id, ""),
                "candidate_id": r.candidate_id,
                "candidate_name": names.get(r.candidate_id, ""),
                "score": r.compatibility_score,
                "date_session_id": r.date_session_id,
            }
            for r in top_matches
        ],
    }


@router.get("/api/demo/{run_id}", response_model=RunOut)
def get_demo_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Demo run not found")
    return RunOut.model_validate(run)


@router.post("/api/demo/seed", response_model=RunOut)
def reseed_demo(db: Session = Depends(get_db)) -> RunOut:
    """Rebuild the synthetic sample. Real people and their runs are untouched."""
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
