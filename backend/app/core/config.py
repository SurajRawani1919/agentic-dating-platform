from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/pairwise.db"
    llm_provider: Literal["openai", "none"] = "none"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: int = 60
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_concurrent_dates: int = 3
    default_max_turns: int = 6
    max_profile_text_chars: int = 20000
    rate_limit_analyze: str = "10/minute"
    rate_limit_runs: str = "5/minute"
    analysis_prompt_version: str = "v1"
    dating_prompt_version: str = "v1"
    ranking_prompt_version: str = "v1"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip()) and self.llm_provider != "none"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
