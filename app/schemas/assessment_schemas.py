"""Pydantic schemas for eligibility assessment history."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AssessmentResponse(BaseModel):
    id: str
    claim_id: str
    is_eligible: bool
    policy_active_check: bool
    incident_covered_check: bool
    timely_filing_check: bool
    exclusions_check: bool
    documentation_complete_check: bool
    fraud_check_passed: bool
    decision_reasons: list[str]
    rejection_code: str | None
    assessed_at: datetime
    assessed_by: str

    model_config = ConfigDict(from_attributes=True)
