from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# The documented setup keeps .env at the repo root while the API runs from backend/.
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/pairwise.db"
    llm_provider: Literal["openai", "none"] = "none"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_concurrent_dates: int = 3
    default_max_turns: int = 6
    max_profile_text_chars: int = 20000
    rate_limit_analyze: str = "10/minute"
    rate_limit_runs: str = "5/minute"
    analysis_prompt_version: str = "v2"
    dating_prompt_version: str = "v2"
    ranking_prompt_version: str = "v2"

    # Public-profile reading (LinkedIn + Instagram)
    scraping_enabled: bool = True
    scraper_timeout_seconds: int = 25
    scraper_proxy: str = ""
    apify_token: str = ""
    apify_instagram_actor: str = "apify~instagram-profile-scraper"
    apify_linkedin_actor: str = "dev_fusion~linkedin-profile-scraper"
    apify_linkedin_input_key: str = "profileUrls"

    # Submission extras
    demo_video_url: str = ""
    demo_snapshot_path: str = "demo_snapshot.json"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip()) and self.llm_provider != "none"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
