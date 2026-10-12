from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import DateSession, DemoRun, Participant
from app.schemas.dating import DateSessionOut, RunCreate, RunOut
from app.services.analysis import latest_analysis
from app.services.dating import ordered_ids, unique_pairs
from app.workers.run_manager import cancel_run, start_run_background

router = APIRouter(tags=["runs"])


def _session_out(s: DateSession, names: dict[int, str]) -> DateSessionOut:
    data = DateSessionOut.model_validate(s)
    data.participant_a_name = names.get(s.participant_a_id)
    data.participant_b_name = names.get(s.participant_b_id)
    return data


def _engine_label() -> str:
    settings = get_settings()
    return f"llm:{settings.llm_model}" if settings.llm_configured else "rule-based"


@router.get("/api/runs", response_model=list[RunOut])
def list_runs(
    limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[RunOut]:
    runs = db.query(DemoRun).order_by(DemoRun.id.desc()).limit(limit).all()
    return [RunOut.model_validate(r) for r in runs]


@router.post("/api/runs", response_model=RunOut, status_code=201)
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> RunOut:
    q = db.query(Participant)
    if payload.participant_ids:
        participants = q.filter(Participant.id.in_(payload.participant_ids)).all()
        if len(participants) != len(set(payload.participant_ids)):
            raise HTTPException(status_code=400, detail="One or more participant_ids invalid")
    else:
        # A live run is for the real people that were pasted in, never the synthetic sample.
        if payload.mode == "live":
            q = q.filter(Participant.is_synthetic.is_(False))
        participants = q.order_by(Participant.id).all()

    # An agent can only date once it has read its person.
    ready = [p for p in participants if latest_analysis(db, p.id) is not None]
    skipped = [p.display_name for p in participants if p not in ready]
    if len(ready) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 analyzed people are required — paste in LinkedIn + Instagram links first.",
        )

    ids = [p.id for p in ready]
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
            "engine": _engine_label(),
            "skipped_without_analysis": skipped,
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


def _launch(run: DemoRun, db: Session) -> RunOut:
    """Start (or resume) a run in the background.

    Agents use the LLM when one is configured; otherwise the built-in rule-based
    agents date instead, and every message is labeled accordingly.
    """
    force_det = run.mode == "demo" or not get_settings().llm_configured
    run.status = "queued"
    run.error_summary = ""
    run.config = {**(run.config or {}), "engine": "rule-based" if force_det else _engine_label()}
    db.commit()
    db.refresh(run)
    out = RunOut.model_validate(run)
    start_run_background(run.id, force_deterministic=force_det)
    return out


@router.post("/api/runs/{run_id}/start", response_model=RunOut)
def start_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in {"running", "queued"}:
        return RunOut.model_validate(run)
    return _launch(run, db)


@router.post("/api/runs/{run_id}/resume", response_model=RunOut)
def resume_run(run_id: int, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(DemoRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _launch(run, db)


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
