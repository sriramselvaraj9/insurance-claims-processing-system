"""Pydantic schemas for Customer entity."""

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class CustomerResponse(BaseModel):
    id: str = Field(..., description="Unique customer ID (e.g. CUST-2026-000001)")
    first_name: str
    last_name: str
    email: str
    phone: str
    date_of_birth: date
    kyc_status: str
    risk_profile: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
