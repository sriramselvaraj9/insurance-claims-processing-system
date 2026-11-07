"""Pydantic schemas for Adjuster and AdjusterAssignment entities."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AdjusterAssignmentResponse(BaseModel):
    id: str = Field(..., description="Unique assignment audit record ID")
    claim_id: str
    adjuster_id: str
    assigned_at: datetime
    unassigned_at: datetime | None = None
    is_active: bool
    assignment_reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdjusterResponse(BaseModel):
    id: str = Field(..., description="Unique adjuster profile ID (e.g. ADJ-2026-000001)")
    employee_id: str
    name: str
    email: str
    phone: str
    specialization: str
    status: str
    active_claims_count: int
    max_capacity: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
