"""Common and reusable Pydantic schemas for pagination, health, and error responses."""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination wrapper metadata and item payload."""

    total: int = Field(..., ge=0, description="Total number of matching records in database")
    page: int = Field(..., ge=1, description="Current page number (1-based index)")
    page_size: int = Field(..., ge=1, le=1000, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    items: list[T] = Field(..., description="Array of records for the requested page")

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        if page < 1:
            raise ValueError("Page must be greater than or equal to 1")
        if page_size < 1:
            raise ValueError("Page size must be greater than or equal to 1")
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class ErrorResponse(BaseModel):
    """Consistent error payload structure."""

    error_code: str = Field(..., description="Machine-readable error identifier")
    error_message: str = Field(..., description="Human-readable error explanation")
    resource_id: str | None = Field(default=None, description="Identifier of the affected resource")
    details: dict[str, Any] | list[Any] | None = Field(default=None, description="Detailed validation or execution context")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Occurrence timestamp in UTC")


class HealthResponse(BaseModel):
    """System health and database readiness probe response."""

    service: str = Field(..., description="Service application name")
    version: str = Field(..., description="Application semantic version")
    status: str = Field(..., description="Overall health status ('healthy' or 'unhealthy')")
    database: str = Field(..., description="Database connectivity status ('connected' or 'disconnected')")
    redis: str | None = Field(default=None, description="Redis cache connectivity status ('connected', 'disconnected', or 'disabled')")
    environment: str = Field(..., description="Operational environment")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Server timestamp in UTC")
