from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Participant, ProfileAnalysis, SourceRecord
from app.schemas.participant import ParticipantCreate, ParticipantOut, SourceRecordOut
from app.services.analysis import latest_analysis
from app.source_providers.base import AcquisitionResult
from app.source_providers.instagram import InstagramSourceProvider
from app.source_providers.linkedin import LinkedInSourceProvider


class SourceAcquisitionError(ValueError):
    """Neither profile could be read, or a profile is not eligible (e.g. private)."""


def _preview(text: str, n: int = 240) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def to_participant_out(
    p: Participant,
    has_analysis: bool = False,
    *,
    headline: str = "",
    include_content: bool = False,
) -> ParticipantOut:
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
                content=s.permitted_content if include_content else "",
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
        headline=headline,
    )


def describe(db: Session, p: Participant, *, include_content: bool = False) -> ParticipantOut:
    """Participant plus the headline of their latest analysis."""
    analysis = latest_analysis(db, p.id)
    return to_participant_out(
        p,
        has_analysis=analysis is not None,
        headline=(analysis.headline or "") if analysis else "",
        include_content=include_content,
    )


def _name_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", (text or "").lower()) if len(t) > 2}


def _verify_same_person(
    display_name: str, li: AcquisitionResult, ig: AcquisitionResult
) -> tuple[str, str]:
    """Cross-check that the two links plausibly belong to one person."""
    if not (li.ok and ig.ok):
        return "unverified", "Verification needs readable content from both sources."

    # Best signal: the name each platform shows for the profile.
    li_name, ig_name = _name_tokens(li.display_name), _name_tokens(ig.display_name)
    ig_handle = ig.submitted_url.rstrip("/").rsplit("/", 1)[-1].lower()
    if li_name and (li_name & ig_name or any(t in ig_handle for t in li_name)):
        return (
            "plausibly_matched",
            f"LinkedIn name “{li.display_name}” matches the Instagram profile "
            f"“{ig.display_name or '@' + ig_handle}”. Not cryptographic identity proof.",
        )

    tokens = _name_tokens(display_name)
    li_text, ig_text = li.permitted_content.lower(), ig.permitted_content.lower()
    if tokens and all(t in li_text and t in ig_text for t in tokens):
        return (
            "plausibly_matched",
            "Display name tokens appear in both sources; not cryptographic identity proof.",
        )
    return (
        "unverified",
        "The names on the two profiles do not obviously match — "
        "check that both links belong to the same person.",
    )


def _read_sources(payload: ParticipantCreate) -> tuple[AcquisitionResult, AcquisitionResult]:
    li = LinkedInSourceProvider().acquire_permitted_content(
        payload.linkedin_url, payload.linkedin_text
    )
    ig = InstagramSourceProvider().acquire_permitted_content(
        payload.instagram_url, payload.instagram_text
    )
    if ig.acquisition_status == "private_profile":
        raise SourceAcquisitionError(
            "That Instagram profile is private. Only public Instagram profiles can be used."
        )
    if not li.ok and not ig.ok:
        raise SourceAcquisitionError(
            "Neither profile could be read. "
            f"LinkedIn: {li.verification_notes} Instagram: {ig.verification_notes}"
        )
    return li, ig


def _fallback_name(linkedin_url: str) -> str:
    slug = linkedin_url.rstrip("/").rsplit("/", 1)[-1]
    words = [w for w in re.split(r"[-_]+", slug) if w and not w.isdigit()]
    return " ".join(w.capitalize() for w in words) or slug


def _store_sources(
    db: Session,
    participant: Participant,
    results: tuple[AcquisitionResult, AcquisitionResult],
    note: str,
) -> None:
    now = datetime.now(timezone.utc)
    existing = {s.source_type: s for s in participant.sources or []}
    for result in results:
        record = existing.get(result.source_type)
        if record is None:
            record = SourceRecord(participant_id=participant.id, source_type=result.source_type)
            db.add(record)
        elif not result.ok and record.permitted_content:
            # A failed re-read must not wipe content from an earlier successful one.
            record.verification_notes = (
                f"Latest re-read failed; showing content from the previous read. "
                f"{result.verification_notes}"
            )
            continue
        record.submitted_url = result.submitted_url
        record.acquisition_method = result.acquisition_method
        record.permitted_content = result.permitted_content
        record.acquisition_status = result.acquisition_status
        record.fetched_at = result.fetched_at or now
        record.verification_notes = f"{result.verification_notes} {note}".strip()


def find_existing(db: Session, linkedin_url: str, instagram_url: str) -> Participant | None:
    return (
        db.query(Participant)
        .options(joinedload(Participant.sources))
        .filter(
            Participant.linkedin_url == linkedin_url,
            Participant.instagram_url == instagram_url,
            Participant.is_synthetic.is_(False),
        )
        .first()
    )


def create_participant(db: Session, payload: ParticipantCreate) -> Participant:
    """Read both public profiles and store the person.

    Submitting the same pair of links again re-reads that person instead of
    creating a duplicate.
    """
    li_result, ig_result = _read_sources(payload)
    display_name = (
        payload.display_name
        or li_result.display_name
        or ig_result.display_name
        or _fallback_name(li_result.submitted_url)
    )
    verification, note = _verify_same_person(display_name, li_result, ig_result)

    participant = find_existing(db, li_result.submitted_url, ig_result.submitted_url)
    if participant is None:
        participant = Participant(
            display_name=display_name,
            linkedin_url=li_result.submitted_url,
            instagram_url=ig_result.submitted_url,
            consent_status="granted",
            adult_eligibility_confirmed=True,
            is_synthetic=False,
        )
        db.add(participant)
        db.flush()
    else:
        participant.display_name = display_name
    participant.source_verification_status = verification

    _store_sources(db, participant, (li_result, ig_result), note)
    db.commit()
    return get_participant(db, participant.id)  # type: ignore[return-value]


def refresh_participant(db: Session, participant: Participant) -> Participant:
    """Re-read both profiles for an existing person."""
    payload = ParticipantCreate(
        display_name=participant.display_name,
        linkedin_url=participant.linkedin_url,
        instagram_url=participant.instagram_url,
        adult_eligibility_confirmed=True,
        consent_to_agent_dating=True,
    )
    li_result, ig_result = _read_sources(payload)
    verification, note = _verify_same_person(participant.display_name, li_result, ig_result)
    if li_result.ok and ig_result.ok:
        participant.source_verification_status = verification
    _store_sources(db, participant, (li_result, ig_result), note)
    db.commit()
    return get_participant(db, participant.id)  # type: ignore[return-value]


def delete_participant(db: Session, participant_id: int) -> bool:
    p = db.get(Participant, participant_id)
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def list_participants(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    synthetic: bool | None = None,
) -> tuple[list[Participant], int]:
    q = db.query(Participant)
    if synthetic is not None:
        q = q.filter(Participant.is_synthetic.is_(synthetic))
    q = q.order_by(Participant.id)
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
