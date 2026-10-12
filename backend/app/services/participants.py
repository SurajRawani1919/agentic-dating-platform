from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Participant, ProfileAnalysis, SourceRecord
from app.schemas.participant import ParticipantCreate, ParticipantOut, SourceRecordOut
from app.source_providers.instagram import InstagramSourceProvider
from app.source_providers.linkedin import LinkedInSourceProvider


def _preview(text: str, n: int = 240) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def to_participant_out(p: Participant, has_analysis: bool = False) -> ParticipantOut:
    sources = []
    for s in p.sources or []:
        sources.append(
            SourceRecordOut(
                id=s.id,
                source_type=s.source_type,  # type: ignore[arg-type]
                submitted_url=s.submitted_url,
                acquisition_method=s.acquisition_method,
                acquisition_status=s.acquisition_status,
                verification_notes=s.verification_notes,
                permitted_content_preview=_preview(s.permitted_content),
                fetched_at=s.fetched_at,
            )
        )
    return ParticipantOut(
        id=p.id,
        display_name=p.display_name,
        linkedin_url=p.linkedin_url,
        instagram_url=p.instagram_url,
        source_verification_status=p.source_verification_status,
        consent_status=p.consent_status,
        adult_eligibility_confirmed=p.adult_eligibility_confirmed,
        is_synthetic=p.is_synthetic,
        created_at=p.created_at,
        updated_at=p.updated_at,
        sources=sources,
        has_analysis=has_analysis,
    )


def create_participant(db: Session, payload: ParticipantCreate) -> Participant:
    li = LinkedInSourceProvider()
    ig = InstagramSourceProvider()
    li_result = li.acquire_permitted_content(payload.linkedin_url, payload.linkedin_text)
    ig_result = ig.acquire_permitted_content(payload.instagram_url, payload.instagram_text)

    # Identity verification: only when both sources have content and share name tokens
    verification = "unverified"
    notes = []
    if (
        li_result.acquisition_status in {"participant_provided", "acquired"}
        and ig_result.acquisition_status in {"participant_provided", "acquired"}
        and li_result.permitted_content
        and ig_result.permitted_content
    ):
        name_tokens = {t.lower() for t in payload.display_name.split() if len(t) > 2}
        li_l = li_result.permitted_content.lower()
        ig_l = ig_result.permitted_content.lower()
        hits = sum(1 for t in name_tokens if t in li_l and t in ig_l)
        if name_tokens and hits == len(name_tokens):
            verification = "plausibly_matched"
            notes.append(
                "Display name tokens appear in both permitted sources; "
                "not cryptographic identity proof."
            )
        else:
            verification = "unverified"
            notes.append(
                "Insufficient evidence to confirm both URLs belong to the same person."
            )
    else:
        notes.append(
            "Verification deferred until permitted content exists for both sources."
        )

    participant = Participant(
        display_name=payload.display_name,
        linkedin_url=li_result.submitted_url,
        instagram_url=ig_result.submitted_url,
        source_verification_status=verification,
        consent_status="granted",
        adult_eligibility_confirmed=True,
        is_synthetic=False,
    )
    db.add(participant)
    db.flush()

    now = datetime.now(timezone.utc)
    for result in (li_result, ig_result):
        db.add(
            SourceRecord(
                participant_id=participant.id,
                source_type=result.source_type,
                submitted_url=result.submitted_url,
                acquisition_method=result.acquisition_method,
                permitted_content=result.permitted_content,
                acquisition_status=result.acquisition_status,
                fetched_at=result.fetched_at or now,
                verification_notes=result.verification_notes
                + (" " + " ".join(notes) if notes else ""),
            )
        )
    db.commit()
    db.refresh(participant)
    participant = (
        db.query(Participant)
        .options(joinedload(Participant.sources))
        .filter(Participant.id == participant.id)
        .one()
    )
    return participant


def delete_participant(db: Session, participant_id: int) -> bool:
    p = db.get(Participant, participant_id)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def list_participants(db: Session, *, page: int = 1, page_size: int = 50) -> tuple[list[Participant], int]:
    q = db.query(Participant).order_by(Participant.id)
    total = q.count()
    items = (
        q.options(joinedload(Participant.sources))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_participant(db: Session, participant_id: int) -> Participant | None:
    return (
        db.query(Participant)
        .options(joinedload(Participant.sources))
        .filter(Participant.id == participant_id)
        .one_or_none()
    )


def has_analysis(db: Session, participant_id: int) -> bool:
    return (
        db.query(ProfileAnalysis)
        .filter(ProfileAnalysis.participant_id == participant_id)
        .count()
        > 0
    )
