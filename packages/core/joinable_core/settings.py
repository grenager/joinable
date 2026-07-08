from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is four levels up: packages/core/joinable_core/settings.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/joinable",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    admin_emails: str = Field(default="", alias="ADMIN_EMAILS")
    api_cors_origins: str = Field(
        default="http://localhost:5173",
        alias="API_CORS_ORIGINS",
    )
    rate_limit_anonymous: str = Field(default="60/minute", alias="RATE_LIMIT_ANONYMOUS")
    rate_limit_authenticated: str = Field(
        default="300/minute",
        alias="RATE_LIMIT_AUTHENTICATED",
    )
    geocoder_user_agent: str = Field(
        default="Joinable/0.1 (events@joinable.dev)",
        alias="GEOCODER_USER_AGENT",
    )
    google_maps_api_key: str = Field(default="", alias="GOOGLE_MAPS_API_KEY")

    @property
    def admin_email_list(self) -> list[str]:
        return [email.strip().lower() for email in self.admin_emails.split(",") if email.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def sync_database_url(self) -> str:
        """Alembic and Celery use sync psycopg2 driver."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
