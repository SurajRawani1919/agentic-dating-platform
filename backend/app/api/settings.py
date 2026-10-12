from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["settings"])


@router.get("/api/settings")
def get_public_settings() -> dict:
    """Non-secret runtime configuration for the UI."""
    s = get_settings()
    readers = ["LinkedIn public page (JSON-LD + rendered sections)", "Instagram crawler-rendered page"]
    if s.apify_token:
        readers.append("Apify actors (fallback)")
    return {
        "app_env": s.app_env,
        "llm_provider": s.llm_provider if s.llm_configured else "none",
        "llm_model": s.llm_model if s.llm_configured else None,
        "llm_configured": s.llm_configured,
        "agent_engine": f"llm:{s.llm_model}" if s.llm_configured else "rule-based",
        "scraping_enabled": s.scraping_enabled,
        "apify_configured": bool(s.apify_token),
        "profile_readers": readers if s.scraping_enabled else [],
        "demo_video_url": s.demo_video_url,
        "max_concurrent_dates": s.max_concurrent_dates,
        "default_max_turns": s.default_max_turns,
        "frontend_origin": s.frontend_origin,
        "analysis_prompt_version": s.analysis_prompt_version,
        "dating_prompt_version": s.dating_prompt_version,
        "notes": [
            "API keys are never returned by this endpoint.",
            "Profiles are read live from the two pasted links; nothing else is used.",
            "Set LLM_API_KEY on the server for LLM agents. Without it, rule-based agents "
            "analyze and date, and are labeled as such.",
        ],
    }
