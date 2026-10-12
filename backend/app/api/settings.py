from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["settings"])


@router.get("/api/settings")
def get_public_settings() -> dict:
    """Non-secret runtime configuration for the UI."""
    s = get_settings()
    return {
        "app_env": s.app_env,
        "llm_provider": s.llm_provider if s.llm_configured else "none",
        "llm_model": s.llm_model if s.llm_configured else None,
        "llm_configured": s.llm_configured,
        "max_concurrent_dates": s.max_concurrent_dates,
        "default_max_turns": s.default_max_turns,
        "frontend_origin": s.frontend_origin,
        "analysis_prompt_version": s.analysis_prompt_version,
        "dating_prompt_version": s.dating_prompt_version,
        "notes": [
            "API keys are never returned by this endpoint.",
            "Configure LLM_API_KEY in the server environment for live mode.",
            "Demo mode works without credentials.",
        ],
    }
