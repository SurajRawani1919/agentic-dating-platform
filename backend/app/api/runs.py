from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.session import get_db
from app.models import DateSession, DemoRun, Participant
from app.schemas.dating import DateSessionOut, RunCreate, RunOut
from app.services.dating import ordered_ids, unique_pairs
from app.workers.run_manager import cancel_run, start_run_background

router = APIRouter(tags=["runs"])


def _session_out(s: DateSession, names: dict[int, str]) -> DateSessionOut:
    data = DateSessionOut.model_validate(s)
    data.participant_a_name = names.get(s.participant_a_id)
    data.participant_b_name = names.get(s.participant_b_id)
    return data


@router.post("/api/runs", response_model=RunOut, status_code=201)
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> RunOut:
    settings = get_settings()
    if payload.mode == "live" and not settings.llm_configured:
        # Allow creating the run, but warn via config — start will use deterministic only if forced
        pass

    q = db.query(Participant)
    if payload.participant_ids:
        participants = q.filter(Participant.id.in_(payload.participant_ids)).all()
        if len(participants) != len(set(payload.participant_ids)):
            raise HTTPException(status_code=400, detail="One or more participant_ids invalid")
    else:
        participants = q.order_by(Participant.id).all()

    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="At least 2 participants required")

    ids = [p.id for p in participants]
    pairs = unique_pairs(ids)
    if payload.session_budget is not None:
        pairs = pairs[: payload.session_budget]

    run = DemoRun(
        name=payload.name,
        mode=payload.mode,
        status="pending",
        participant_count=len(ids),
        session_count=len(pairs),
        completed_sessions=0,
        progress=0.0,
        max_turns=payload.max_turns,
        config={
            "participant_ids": ids,
            "session_budget": payload.session_budget,
            "llm_configured": settings.llm_configured,
        },
    )
    db.add(run)
    db.flush()

    for a, b in pairs:
        a_id, b_id = ordered_ids(a, b)
        db.add(
            DateSession(
                participant_a_id=a_id,
                participant_b_id=b_id,
                run_id=run.id,
                status="pending",
                max_turns=payload.max_turns,
            )
        )
    db.commit()
    db.refresh(run)
    return RunOut.model_validate(run)


@router.get("/api/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut.model_validate(run)


@router.post("/api/runs/{run_id}/start", response_model=RunOut)
def start_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in {"running"}:
        return RunOut.model_validate(run)
    force_det = run.mode == "demo" or not get_settings().llm_configured
    if run.mode == "live" and not get_settings().llm_configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "Live mode requires LLM_API_KEY. Configure settings or start a demo run."
            ),
        )
    run.status = "queued"
    db.commit()
    start_run_background(run_id, force_deterministic=force_det)
    db.refresh(run)
    return RunOut.model_validate(run)


@router.post("/api/runs/{run_id}/resume", response_model=RunOut)
def resume_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    force_det = run.mode == "demo" or not get_settings().llm_configured
    if run.mode == "live" and not get_settings().llm_configured:
        raise HTTPException(status_code=400, detail="Live mode requires LLM_API_KEY")
    start_run_background(run_id, force_deterministic=force_det)
    run.status = "queued"
    db.commit()
    db.refresh(run)
    return RunOut.model_validate(run)


@router.post("/api/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run_endpoint(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    cancel_run(run_id)
    run.status = "cancelling"
    db.commit()
    db.refresh(run)
    return RunOut.model_validate(run)


@router.get("/api/runs/{run_id}/sessions", response_model=list[DateSessionOut])
def list_sessions(run_id: int, db: Session = Depends(get_db)) -> list[DateSessionOut]:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    sessions = (
        db.query(DateSession)
        .filter(DateSession.run_id == run_id)
        .order_by(DateSession.id)
        .all()
    )
    names = {p.id: p.display_name for p in db.query(Participant).all()}
    return [_session_out(s, names) for s in sessions]
