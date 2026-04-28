from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "cogency-default"

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()
