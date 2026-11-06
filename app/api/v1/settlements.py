"""Settlement recommendation inquiry, supervisor approval, and disbursement endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep, get_settlement_service
from app.repositories.settlement_repository import SettlementRepository
from app.schemas.settlement_schemas import (
    SettlementApproveRequest,
    SettlementDisburseRequest,
    SettlementPaymentResponse,
    SettlementResponse,
)
from app.services.exceptions import DuplicatePaymentError
from app.services.settlement_service import SettlementService

router = APIRouter(tags=["Settlements"])


@router.get(
    "/claims/{claim_id}/settlements",
    response_model=list[SettlementResponse],
    summary="Retrieve all settlement recommendations for a claim",
)
def get_claim_settlements(
    claim_id: str,
    db: SessionDep,
) -> list[SettlementResponse]:
    """Retrieve settlement recommendations and history for a claim."""
    repo = SettlementRepository(db)
    settlements = repo.get_by_claim_id(claim_id)
    return [SettlementResponse.model_validate(s) for s in settlements]


@router.post(
    "/settlements/{settlement_id}/approve",
    response_model=SettlementResponse,
    summary="Supervisor approval of a proposed settlement recommendation",
)
def approve_settlement(
    settlement_id: str,
    payload: SettlementApproveRequest,
    service: Annotated[SettlementService, Depends(get_settlement_service)],
) -> SettlementResponse:
    """Approve a proposed settlement."""
    try:
        settlement = service.approve_settlement(settlement_id, approved_by=payload.approved_by)
        return SettlementResponse.model_validate(settlement)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/settlements/{settlement_id}/disburse",
    response_model=SettlementPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Disburse payment for an approved settlement with duplicate payment protection",
)
def disburse_payment(
    settlement_id: str,
    payload: SettlementDisburseRequest,
    service: Annotated[SettlementService, Depends(get_settlement_service)],
) -> SettlementPaymentResponse:
    """Disburse payment, strictly blocking duplicate payment execution (Scenario 6 control)."""
    try:
        payment = service.disburse_payment(settlement_id, payment_method=payload.payment_method)
        return SettlementPaymentResponse.model_validate(payment)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicatePaymentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
