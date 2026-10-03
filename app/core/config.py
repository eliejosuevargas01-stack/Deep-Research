from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/deep_research_db"
    ADMIN_PASSWORD: str = Field(min_length=12)
    SESSION_SECRET: str = Field(min_length=32)
    APP_ENCRYPTION_KEY: str = Field(min_length=32)
    API_AUTH_SECRET: Optional[str] = None
    SESSION_TTL_HOURS: int = 24
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    SEARCH_TIMEOUT_SECONDS: int = 30
    MAX_AUDIT_ATTEMPTS: int = 4
    MAX_WORKER_QUERIES: int = 3

    @field_validator("MAX_WORKER_QUERIES")
    @classmethod
    def validate_worker_queries_cap(cls, v: int) -> int:
        if v > 3:
            raise ValueError("MAX_WORKER_QUERIES cannot exceed absolute maximum of 3")
        return v
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LITELLM_API_KEY: Optional[str] = None
    LITELLM_API_BASE: Optional[str] = None
    JINA_API_KEY: Optional[str] = None
    SERPAPI_API_KEY: Optional[str] = None
    APIFY_API_TOKEN: Optional[str] = None
    SCOUT_MODEL: Optional[str] = None
    HISTORIAN_MODEL: Optional[str] = None
    SKEPTIC_MODEL: Optional[str] = None
    PRAGMATIST_MODEL: Optional[str] = None
    FUTURIST_MODEL: Optional[str] = None
    AUDITOR_MODEL: Optional[str] = None
    WRITER_MODEL: Optional[str] = None

    @property
    def production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def origins(self) -> list[str]:
        return [v.strip() for v in self.ALLOWED_ORIGINS.split(",") if v.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
