from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.participant import AnalysisOut, ParticipantCreate, ParticipantOut
from app.services import analysis as analysis_service
from app.services import participants as participant_service
from app.services.llm import LLMError

router = APIRouter(tags=["participants"])


@router.get("/api/participants", response_model=PaginatedResponse[ParticipantOut])
def list_participants(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ParticipantOut]:
    items, total = participant_service.list_participants(db, page=page, page_size=page_size)
    out = [
        participant_service.to_participant_out(
            p, has_analysis=participant_service.has_analysis(db, p.id)
        )
        for p in items
    ]
    return PaginatedResponse(items=out, total=total, page=page, page_size=page_size)


@router.post("/api/participants", response_model=ParticipantOut, status_code=201)
def create_participant(
    payload: ParticipantCreate, db: Session = Depends(get_db)
) -> ParticipantOut:
    try:
        p = participant_service.create_participant(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return participant_service.to_participant_out(p, has_analysis=False)


@router.get("/api/participants/{participant_id}", response_model=ParticipantOut)
def get_participant(participant_id: int, db: Session = Depends(get_db)) -> ParticipantOut:
    p = participant_service.get_participant(db, participant_id)
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant_service.to_participant_out(
        p, has_analysis=participant_service.has_analysis(db, p.id)
    )


@router.delete("/api/participants/{participant_id}", status_code=204)
def delete_participant(participant_id: int, db: Session = Depends(get_db)) -> None:
    ok = participant_service.delete_participant(db, participant_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Participant not found")


@router.post("/api/participants/{participant_id}/analyze", response_model=AnalysisOut)
async def analyze_participant(
    participant_id: int, db: Session = Depends(get_db)
) -> AnalysisOut:
    p = participant_service.get_participant(db, participant_id)
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
    try:
        analysis = await analysis_service.analyze_participant(db, participant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AnalysisOut.model_validate(analysis)


@router.get("/api/participants/{participant_id}/analysis", response_model=AnalysisOut)
def get_analysis(participant_id: int, db: Session = Depends(get_db)) -> AnalysisOut:
    analysis = analysis_service.latest_analysis(db, participant_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")
    return AnalysisOut.model_validate(analysis)
