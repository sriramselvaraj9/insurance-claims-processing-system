"""Application configuration and environment settings."""

from functools import lru_cache
from typing import Any, Literal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application settings
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Insurance Claims Processing System"
    API_V1_STR: str = "/api/v1"

    # Server Bindings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "claims_db"
    DATABASE_URL: str | None = None

    # Test Database
    TEST_DATABASE_URL: str = "sqlite:///./test_claims.db"

    # Redis Cache & Ephemeral Storage
    REDIS_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    REDIS_URL: str | None = None
    REDIS_CACHE_TTL_SECONDS: int = 300

    # Business Rules Parameters
    TIMELY_FILING_DAYS_LIMIT: int = 30
    AUTO_APPROVAL_THRESHOLD: float = 2500.00
    HIGH_VALUE_CLAIM_THRESHOLD: float = 50000.00
    DEFAULT_EXPENSE_RATIO: float = 0.12

    # Synthetic Dataset & Evaluation
    SYNTHETIC_DATA_RANDOM_SEED: int = 42
    DEFAULT_SYNTHETIC_CLAIM_COUNT: int = 500

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_and_finalize_settings(self) -> "Settings":
        # Finalize Database URL if not explicitly supplied
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # Finalize Redis URL if enabled and not explicitly supplied
        if not self.REDIS_URL and self.REDIS_ENABLED:
            auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        # Production security hardening
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG mode must be disabled in production environment.")
            if self.POSTGRES_PASSWORD in ("postgres", "password", "admin", "123456", ""):
                raise ValueError(
                    "Insecure default or empty POSTGRES_PASSWORD is not permitted in production environment."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
