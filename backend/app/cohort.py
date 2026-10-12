"""Build, run and ship the real-people example from the command line.

  python -m app.cohort ingest people.csv   # read + analyze everyone in the file
  python -m app.cohort date                # every agent dates every other agent, then rank
  python -m app.cohort export              # save the finished example to demo_snapshot.json
  python -m app.cohort import              # load demo_snapshot.json into an empty database

people.csv holds one person per line: ``linkedin_url,instagram_url[,display name]``.
Lines starting with # are ignored.

The snapshot is how a finished run reaches a deployed site: profiles are read
from a home connection (datacenter IPs are often blocked by both platforms) and
the result is restored on startup wherever the API runs.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.db import session as db_session
from app.db.migrate import ensure_schema
from app.models import (
    DateMessage,
    DateSession,
    DemoRun,
    Participant,
    ProfileAnalysis,
    Ranking,
    SourceRecord,
)
from app.schemas.participant import ParticipantCreate
from app.services import analysis as analysis_service
from app.services import participants as participant_service
from app.services.dating import execute_run, ordered_ids, unique_pairs

logger = logging.getLogger("pairwise.cohort")

SNAPSHOT_VERSION = 1
_FINISHED = ("completed", "completed_with_errors")
# Columns that must not be copied between databases.
_SKIP = {"id", "created_at", "updated_at"}
_DATETIME_COLUMNS = {"fetched_at", "completed_at"}


def snapshot_path() -> Path:
    path = Path(get_settings().demo_snapshot_path)
    return path if path.is_absolute() else BACKEND_DIR / path


# ---------------------------------------------------------------- ingest


def read_people(path: Path) -> list[tuple[str, str, str]]:
    people: list[tuple[str, str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            cells = [c.strip() for c in row if c.strip()]
            if not cells or cells[0].startswith("#"):
                continue
            if cells[0].lower().startswith("linkedin") and "://" not in cells[0]:
                continue  # header row
            if len(cells) < 2:
                raise ValueError(f"Expected 'linkedin_url,instagram_url' but got: {row}")
            people.append((cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return people


def ingest(path: Path, *, pause: float = 2.0) -> int:
    """Read and analyze every person in the file. Returns how many succeeded."""
    people = read_people(path)
    print(f"Reading {len(people)} people from {path} …")
    ok = 0
    for index, (linkedin, instagram, name) in enumerate(people, start=1):
        db = db_session.SessionLocal()
        try:
            payload = ParticipantCreate(
                display_name=name,
                linkedin_url=linkedin,
                instagram_url=instagram,
                adult_eligibility_confirmed=True,
                consent_to_agent_dating=True,
            )
            person = participant_service.create_participant(db, payload)
            analysis = asyncio.run(analysis_service.analyze_participant(db, person.id))
            statuses = ", ".join(
                f"{s.source_type}={s.acquisition_status}" for s in person.sources
            )
            print(
                f"  [{index}/{len(people)}] OK   {person.display_name} "
                f"({statuses}; {len(analysis.needs or [])} needs, "
                f"{len(analysis.hobbies or [])} hobbies, {len(analysis.interests or [])} interests; "
                f"{analysis.model_name})"
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 — keep going, report at the end
            print(f"  [{index}/{len(people)}] FAIL {linkedin} — {exc}")
        finally:
            db.close()
        if index < len(people):
            time.sleep(pause)  # stay polite to both platforms
    print(f"Done: {ok}/{len(people)} people read and analyzed.")
    return ok


# ---------------------------------------------------------------- date


def date_everyone(name: str, max_turns: int) -> int:
    """Create a run over every real, analyzed person and execute it to completion."""
    settings = get_settings()
    db = db_session.SessionLocal()
    try:
        people = (
            db.query(Participant)
            .filter(Participant.is_synthetic.is_(False))
            .order_by(Participant.id)
            .all()
        )
        ready = [p for p in people if analysis_service.latest_analysis(db, p.id)]
        if len(ready) < 2:
            raise SystemExit("Need at least 2 analyzed people. Run `ingest` first.")
        ids = [p.id for p in ready]
        pairs = unique_pairs(ids)
        engine = f"llm:{settings.llm_model}" if settings.llm_configured else "rule-based"
        run = DemoRun(
            name=name,
            mode="live",
            status="pending",
            participant_count=len(ids),
            session_count=len(pairs),
            max_turns=max_turns,
            config={"participant_ids": ids, "engine": engine},
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
                    max_turns=max_turns,
                )
            )
        db.commit()
        run_id = run.id
    finally:
        db.close()

    print(f"Run #{run_id}: {len(ids)} people, {len(pairs)} dates, engine={engine} …")
    started = time.time()
    asyncio.run(
        execute_run(
            db_session.SessionLocal,
            run_id,
            force_deterministic=not settings.llm_configured,
        )
    )
    db = db_session.SessionLocal()
    try:
        run = db.get(DemoRun, run_id)
        rankings = db.query(Ranking).filter(Ranking.run_id == run_id).count()
        print(
            f"Run #{run_id} {run.status}: {run.completed_sessions}/{run.session_count} dates, "
            f"{rankings} ranking rows in {time.time() - started:.0f}s."
        )
        if run.error_summary:
            print(f"  errors: {run.error_summary}")
    finally:
        db.close()
    return run_id


# ---------------------------------------------------------------- snapshot


def _row(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column in obj.__table__.columns:
        if column.name in _SKIP:
            continue
        value = getattr(obj, column.name)
        out[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return out


def _restore(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for key in _DATETIME_COLUMNS & out.keys():
        if isinstance(out[key], str):
            out[key] = datetime.fromisoformat(out[key])
    return out


def export_snapshot(path: Path, run_id: int | None = None) -> Path:
    """Write the finished example (people, analyses, dates, rankings) to JSON."""
    db = db_session.SessionLocal()
    try:
        query = db.query(DemoRun).filter(DemoRun.mode == "live", DemoRun.status.in_(_FINISHED))
        run = (
            query.filter(DemoRun.id == run_id).first()
            if run_id
            else query.order_by(DemoRun.participant_count.desc(), DemoRun.id.desc()).first()
        )
        if not run:
            raise SystemExit("No finished run over real people to export. Run `date` first.")

        sessions = db.query(DateSession).filter(DateSession.run_id == run.id).all()
        ids = sorted(
            {s.participant_a_id for s in sessions} | {s.participant_b_id for s in sessions}
        )
        people = []
        for pid in ids:
            person = db.get(Participant, pid)
            analysis = analysis_service.latest_analysis(db, pid)
            people.append(
                {
                    "ref": pid,
                    **_row(person),
                    "sources": [_row(s) for s in person.sources],
                    "analysis": _row(analysis) if analysis else None,
                }
            )
        payload = {
            "version": SNAPSHOT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "run": _row(run),
            "participants": people,
            "sessions": [
                {"ref": s.id, **_row(s), "messages": [_row(m) for m in s.messages]}
                for s in sessions
            ],
            "rankings": [
                _row(r) for r in db.query(Ranking).filter(Ranking.run_id == run.id).all()
            ],
        }
    finally:
        db.close()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"Exported run #{run.id}: {len(people)} people, {len(payload['sessions'])} dates, "
        f"{len(payload['rankings'])} ranking rows → {path}"
    )
    return path


def import_snapshot(path: Path, db: Session | None = None) -> int:
    """Load a snapshot, remapping ids. Returns the new run id."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    own_session = db is None
    db = db or db_session.SessionLocal()
    try:
        person_ids: dict[int, int] = {}
        for item in payload["participants"]:
            data = {k: v for k, v in item.items() if k not in {"ref", "sources", "analysis"}}
            person = Participant(**data)
            db.add(person)
            db.flush()
            person_ids[item["ref"]] = person.id
            for source in item["sources"]:
                db.add(SourceRecord(**{**_restore(source), "participant_id": person.id}))
            if item["analysis"]:
                db.add(ProfileAnalysis(**{**item["analysis"], "participant_id": person.id}))

        run_data = _restore(payload["run"])
        run_data["config"] = {
            **(run_data.get("config") or {}),
            "participant_ids": list(person_ids.values()),
            "restored_from_snapshot": payload.get("exported_at"),
        }
        run = DemoRun(**run_data)
        db.add(run)
        db.flush()

        session_ids: dict[int, int] = {}
        for item in payload["sessions"]:
            data = _restore({k: v for k, v in item.items() if k not in {"ref", "messages"}})
            data.update(
                run_id=run.id,
                participant_a_id=person_ids[data["participant_a_id"]],
                participant_b_id=person_ids[data["participant_b_id"]],
            )
            session = DateSession(**data)
            db.add(session)
            db.flush()
            session_ids[item["ref"]] = session.id
            for message in item["messages"]:
                db.add(
                    DateMessage(
                        **{
                            **message,
                            "session_id": session.id,
                            "speaker_participant_id": person_ids[message["speaker_participant_id"]],
                        }
                    )
                )
        for item in payload["rankings"]:
            db.add(
                Ranking(
                    **{
                        **item,
                        "run_id": run.id,
                        "participant_id": person_ids[item["participant_id"]],
                        "candidate_id": person_ids[item["candidate_id"]],
                        "date_session_id": session_ids.get(item.get("date_session_id")),
                    }
                )
            )
        db.commit()
        return run.id
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def restore_snapshot_if_empty() -> None:
    """On startup, load the saved example when the database has no real people yet."""
    path = snapshot_path()
    if not path.exists():
        return
    db = db_session.SessionLocal()
    try:
        if db.query(Participant).filter(Participant.is_synthetic.is_(False)).count():
            return
        run_id = import_snapshot(path, db)
        logger.info("Restored saved example from %s as run #%s", path.name, run_id)
    except Exception:  # noqa: BLE001 — a bad snapshot must not stop the API from booting
        logger.exception("Could not restore snapshot %s", path)
    finally:
        db.close()


# ---------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cohort", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="read + analyze everyone in a CSV of links")
    p_ingest.add_argument("file", type=Path)
    p_ingest.add_argument("--pause", type=float, default=2.0, help="seconds between people")

    p_date = sub.add_parser("date", help="run every pairwise date, then rank")
    p_date.add_argument("--name", default="Real cohort — every agent dates every agent")
    p_date.add_argument("--max-turns", type=int, default=get_settings().default_max_turns)

    p_export = sub.add_parser("export", help="save the finished example to a snapshot file")
    p_export.add_argument("file", type=Path, nargs="?", default=snapshot_path())
    p_export.add_argument("--run-id", type=int, default=None)

    p_import = sub.add_parser("import", help="load a snapshot file into this database")
    p_import.add_argument("file", type=Path, nargs="?", default=snapshot_path())

    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ensure_schema(db_session.engine)

    if args.command == "ingest":
        ingest(args.file, pause=args.pause)
    elif args.command == "date":
        date_everyone(args.name, args.max_turns)
    elif args.command == "export":
        export_snapshot(args.file, args.run_id)
    elif args.command == "import":
        print(f"Imported snapshot as run #{import_snapshot(args.file)}")


if __name__ == "__main__":
    main()
