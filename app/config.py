from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Klingo
    klingo_base_url: str = "https://api-externa.klingo.app/api"
    klingo_app_token: str
    klingo_register_token: str | None = None

    # Asaas
    asaas_base_url: str = "https://www.asaas.com/api/v3"
    asaas_api_key: str | None = None

    # Infra
    database_url: str = "postgresql+asyncpg://otinho:otinho@localhost:5432/otinho"
    redis_url: str | None = None
    request_timeout_seconds: int = 20
    env: str = "dev"

    class Config:
        env_file = ".env"

settings = Settings()  # type: ignore
