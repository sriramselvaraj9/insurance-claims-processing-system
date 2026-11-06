"""Pydantic schemas for settlement recommendations, approvals, and disbursements."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, PaymentStatus, SettlementStatus


class SettlementApproveRequest(BaseModel):
    approved_by: str = Field(..., min_length=2, max_length=100)


class SettlementDisburseRequest(BaseModel):
    payment_method: PaymentMethod = PaymentMethod.ACH


class SettlementResponse(BaseModel):
    id: str
    claim_id: str
    recommended_amount: Decimal
    approved_amount: Decimal | None
    deductible_applied: Decimal
    copay_applied: Decimal
    net_settlement_amount: Decimal
    status: SettlementStatus
    settled_at: datetime | None
    settled_by: str | None
    payment_reference: str | None

    model_config = ConfigDict(from_attributes=True)


class SettlementPaymentResponse(BaseModel):
    id: str
    settlement_id: str
    payment_amount: Decimal
    payment_method: PaymentMethod
    payment_reference: str
    payment_date: datetime
    status: PaymentStatus

    model_config = ConfigDict(from_attributes=True)
