from functools import lru_cache
from typing import Literal
from pydantic import model_validator
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

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "claims_db"
    DATABASE_URL: str | None = None

    # Test Database
    TEST_DATABASE_URL: str = "sqlite:///./test_claims.db"

    # Business Rules Parameters
    TIMELY_FILING_DAYS_LIMIT: int = 30
    AUTO_APPROVAL_THRESHOLD: float = 2500.00
    HIGH_VALUE_CLAIM_THRESHOLD: float = 50000.00
    DEFAULT_EXPENSE_RATIO: float = 0.12

    # Synthetic Dataset & Evaluation
    SYNTHETIC_DATA_RANDOM_SEED: int = 42
    DEFAULT_SYNTHETIC_CLAIM_COUNT: int = 500

    @model_validator(mode="after")
    def set_default_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
