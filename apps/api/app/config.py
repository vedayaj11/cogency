from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    database_url: str = Field(
        default="postgresql+asyncpg://cogency:cogency_dev@localhost:5432/cogency"
    )

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "cogency-default"

    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-sonnet-4-5"
    anthropic_triage_model: str = "claude-haiku-4-5"
    anthropic_judge_model: str = "claude-opus-4-5"

    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
