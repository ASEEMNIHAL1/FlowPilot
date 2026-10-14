from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=False,
        env_prefix="FLOWPILOT_",
    )

    app_name: str = "FlowPilot"
    timezone: str = "Asia/Kolkata"
    database_url: str = "sqlite:///./flowpilot.db"

    llm_provider: str = "dev"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    max_tool_calls: int = 24
    max_retries: int = 2
    max_repair_attempts: int = 1
    run_timeout_seconds: int = 90
    max_goal_length: int = 4000
    max_invalid_tool_calls: int = 3

    work_start: str = "09:00"
    work_end: str = "19:00"
    lunch_start: str = "12:00"
    lunch_end: str = "13:00"
    default_meeting_minutes: int = 60
    default_lunch_minutes: int = 60

    inject_create_failures: int = 0


class OpenAIEnvSettings(BaseSettings):
    """Reads unprefixed OpenAI variables so keys stay in standard locations."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    openai_env = OpenAIEnvSettings()
    if openai_env.openai_api_key:
        settings.openai_api_key = openai_env.openai_api_key
    if openai_env.openai_model:
        settings.openai_model = openai_env.openai_model
    if openai_env.openai_base_url:
        settings.openai_base_url = openai_env.openai_base_url
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
