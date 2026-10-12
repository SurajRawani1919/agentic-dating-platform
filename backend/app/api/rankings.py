from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DemoRun, Participant, Ranking
from app.schemas.ranking import RankingListOut, RankingOut

router = APIRouter(tags=["rankings"])


@router.get("/api/rankings/{participant_id}", response_model=RankingListOut)
def get_rankings(
    participant_id: int,
    run_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> RankingListOut:
    p = db.get(Participant, participant_id)
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")

    if run_id is None:
        # Latest finished run in which this person actually dated.
        latest = (
            db.query(Ranking.run_id)
            .join(DemoRun, DemoRun.id == Ranking.run_id)
            .filter(
                Ranking.participant_id == participant_id,
                DemoRun.status.in_(["completed", "completed_with_errors"]),
            )
            .order_by(Ranking.run_id.desc())
            .first()
        )
        if not latest:
            raise HTTPException(
                status_code=404,
                detail="No rankings yet — this person's agent has not been on any dates. "
                "Run dating from the workspace first.",
            )
        run_id = latest[0]
    elif not db.get(DemoRun, run_id):
        raise HTTPException(status_code=404, detail="Run not found")

    rows = (
        db.query(Ranking)
        .filter(Ranking.run_id == run_id, Ranking.participant_id == participant_id)
        .order_by(Ranking.rank)
        .all()
    )
    names = {x.id: x for x in db.query(Participant).all()}
    out_rows: list[RankingOut] = []
    for r in rows:
        item = RankingOut.model_validate(r)
        cand = names.get(r.candidate_id)
        item.candidate_name = cand.display_name if cand else None
        item.candidate_is_synthetic = cand.is_synthetic if cand else None
        out_rows.append(item)

    return RankingListOut(
        participant_id=participant_id,
        participant_name=p.display_name,
        run_id=run_id,
        rankings=out_rows,
    )
