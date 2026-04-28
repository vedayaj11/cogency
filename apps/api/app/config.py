from functools import lru_cache
from uuid import UUID

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

    # LLM (OpenAI is the active provider for MVP)
    openai_api_key: str = ""
    openai_default_model: str = "gpt-4o"
    openai_triage_model: str = "gpt-4o-mini"
    openai_judge_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-large"

    # Anthropic kept for cross-family judge / future routing
    anthropic_api_key: str = ""

    # Salesforce
    sf_login_url: str = "https://login.salesforce.com"
    sf_token_url: str = "https://login.salesforce.com/services/oauth2/token"
    sf_api_version: str = "62.0"
    sf_client_id: str = ""
    sf_client_secret: str = ""
    sf_username: str = ""
    sf_jwt_private_key_path: str = "./secrets/sf_jwt.pem"
    sf_pubsub_endpoint: str = "api.pubsub.salesforce.com:7443"

    cogency_dev_tenant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")

    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
