from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from app.db import session as db_session
from app.models import DemoRun
from app.services.dating import execute_run

logger = logging.getLogger("pairwise.runs")

_threads: dict[int, threading.Thread] = {}
_cancel_events: dict[int, threading.Event] = {}


def start_run_background(run_id: int, *, force_deterministic: bool = False) -> None:
    """Run a dating run on its own thread and event loop.

    Request handlers return immediately; the UI polls the run for progress.
    """
    existing = _threads.get(run_id)
    if existing and existing.is_alive():
        return
    cancel_event = threading.Event()
    _cancel_events[run_id] = cancel_event

    def _runner() -> None:
        try:
            asyncio.run(
                execute_run(
                    db_session.SessionLocal,
                    run_id,
                    cancel_event=cancel_event,
                    force_deterministic=force_deterministic,
                )
            )
        except Exception as exc:  # noqa: BLE001 — a crashed run must not stay "running"
            logger.exception("Dating run %s crashed", run_id)
            db = db_session.SessionLocal()
            try:
                run = db.get(DemoRun, run_id)
                if run:
                    run.status = "failed"
                    run.error_summary = f"Run crashed: {exc}"[:2000]
                    db.commit()
            finally:
                db.close()

    thread = threading.Thread(target=_runner, name=f"dating-run-{run_id}", daemon=True)
    _threads[run_id] = thread
    thread.start()


def wait_for_run(run_id: int, timeout: float | None = None) -> bool:
    """Block until a run's thread finishes. Returns False on timeout."""
    thread = _threads.get(run_id)
    if not thread:
        return True
    thread.join(timeout)
    return not thread.is_alive()


def cancel_run(run_id: int) -> bool:
    ev = _cancel_events.get(run_id)
    if not ev:
        return False
    ev.set()
    return True


def run_status(run_id: int) -> dict[str, Any]:
    thread = _threads.get(run_id)
    return {
        "running": bool(thread and thread.is_alive()),
        "done": bool(thread and not thread.is_alive()),
    }
