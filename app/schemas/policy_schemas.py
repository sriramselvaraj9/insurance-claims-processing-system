"""Pydantic schemas for Policy and Coverage entities."""

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class CoverageResponse(BaseModel):
    id: str = Field(..., description="Unique coverage ID")
    policy_id: str
    coverage_type: str
    coverage_limit: Decimal
    deductible: Decimal
    copay_percentage: Decimal
    exclusions: list[str] | None = None
    effective_date: date
    expiration_date: date
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PolicyResponse(BaseModel):
    id: str = Field(..., description="Unique policy contract ID (e.g. POL-AUTO-2026-000001)")
    customer_id: str
    policy_type: str
    status: str
    effective_date: date
    expiration_date: date
    cancellation_date: date | None = None
    total_premium: Decimal
    deductible: Decimal
    created_at: datetime
    updated_at: datetime
    coverages: list[CoverageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
