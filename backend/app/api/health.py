from fastapi import APIRouter

from app import __version__
from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        llm_configured=settings.llm_configured,
        database="sqlite" if settings.is_sqlite else "postgres",
    )
