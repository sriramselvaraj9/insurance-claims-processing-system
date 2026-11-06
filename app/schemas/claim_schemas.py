"""Pydantic schemas for claim intake, responses, and processing workflow outputs."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ClaimStatus, ClaimType


class ClaimItemCreate(BaseModel):
    item_description: str = Field(..., min_length=2, max_length=255)
    quantity: int = Field(default=1, ge=1)
    unit_amount: Decimal = Field(..., ge=0)
    total_amount: Decimal = Field(..., ge=0)


class ClaimIntakeRequest(BaseModel):
    customer_id: str = Field(..., min_length=3, max_length=50)
    policy_id: str = Field(..., min_length=3, max_length=60)
    incident_id: str = Field(..., min_length=3, max_length=50)
    claim_type: ClaimType
    claimed_amount: Decimal = Field(..., gt=0)
    description: str = Field(..., min_length=5)
    reported_date: datetime | None = None
    line_items: list[ClaimItemCreate] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reconcile_items(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "claim_items" in data and not data.get("line_items"):
                data["line_items"] = data["claim_items"]
        return data


class ClaimItemResponse(BaseModel):
    id: str
    claim_id: str
    coverage_id: str | None
    item_description: str
    quantity: int
    unit_amount: Decimal
    total_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: str
    customer_id: str
    policy_id: str
    incident_id: str
    claim_type: ClaimType
    status: ClaimStatus
    reported_date: datetime
    claimed_amount: Decimal
    estimated_loss: Decimal
    description: str
    assigned_adjuster_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimProcessingResultResponse(BaseModel):
    claim_id: str
    status: ClaimStatus
    outcome: str  # ELIGIBLE, INELIGIBLE, PENDING_DOCUMENTS, MANUAL_REVIEW
    assessment_id: str | None = None
    is_eligible: bool
    rejection_code: str | None = None
    decision_reasons: list[str]
    assigned_adjuster_id: str | None = None
    reserve_id: str | None = None
    total_reserve: Decimal | None = None
    settlement_id: str | None = None
    net_settlement_amount: Decimal | None = None
    missing_document_types: list[str] = Field(default_factory=list)
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    fraud_indicators: list[dict[str, Any]] = Field(default_factory=list)
