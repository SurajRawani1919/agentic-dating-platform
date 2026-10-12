from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import __version__
from app.api import dates, demo, health, participants, rankings, runs, settings as settings_api
from app.core.config import get_settings
from app.cohort import restore_snapshot_if_empty
from app.db.migrate import ensure_schema
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("pairwise")

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.is_sqlite:
        Path("data").mkdir(parents=True, exist_ok=True)
    ensure_schema(engine)
    restore_snapshot_if_empty()
    logger.info("PAIRWISE API starting (env=%s, llm=%s)", settings.app_env, settings.llm_configured)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PAIRWISE API",
        description="Agentic Dating Platform — AI agents, real compatibility.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.frontend_origin.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # noqa: ARG001
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router)
    app.include_router(participants.router)
    app.include_router(runs.router)
    app.include_router(dates.router)
    app.include_router(rankings.router)
    app.include_router(demo.router)
    app.include_router(settings_api.router)

    # Rate-limit expensive endpoints via dependency decoration wrappers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    return app


app = create_app()
