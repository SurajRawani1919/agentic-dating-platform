from __future__ import annotations

import asyncio
from typing import Any

from app.db.session import SessionLocal
from app.services.dating import execute_run

_tasks: dict[int, asyncio.Task] = {}
_cancel_events: dict[int, asyncio.Event] = {}


def start_run_background(run_id: int, *, force_deterministic: bool = False) -> None:
    if run_id in _tasks and not _tasks[run_id].done():
        return
    cancel_event = asyncio.Event()
    _cancel_events[run_id] = cancel_event

    async def _runner() -> None:
        await execute_run(
            SessionLocal,
            run_id,
            cancel_event=cancel_event,
            force_deterministic=force_deterministic,
        )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    task = loop.create_task(_runner())
    _tasks[run_id] = task


def cancel_run(run_id: int) -> bool:
    ev = _cancel_events.get(run_id)
    if not ev:
        return False
    ev.set()
    return True


def run_status(run_id: int) -> dict[str, Any]:
    task = _tasks.get(run_id)
    return {
        "running": bool(task and not task.done()),
        "done": bool(task and task.done()),
    }
