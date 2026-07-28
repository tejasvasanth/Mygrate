"""Application settings loaded from environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # Gemini (AI brain)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Credential encryption fallback
    credential_encryption_key: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # App
    environment: str = "development"
    frontend_url: str = "http://localhost:5173"
    # Base URL used to build shareable report links and README badges.
    public_base_url: str = "http://localhost:5173"

    # SMTP for drift alerts and health digests (optional — unset means
    # notifications are logged instead of sent).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "migrate@localhost"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
