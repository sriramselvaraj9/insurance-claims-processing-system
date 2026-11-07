"""Settlement recommendation inquiry, supervisor approval, and disbursement endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep, get_settlement_service
from app.repositories.claim_repository import ClaimRepository
from app.repositories.coverage_repository import CoverageRepository
from app.repositories.settlement_repository import SettlementRepository
from app.schemas.settlement_schemas import (
    SettlementApproveRequest,
    SettlementDisburseRequest,
    SettlementPaymentResponse,
    SettlementResponse,
)
from app.services.exceptions import DuplicatePaymentError, SettlementLimitExceededError
from app.services.settlement_service import SettlementService

router = APIRouter(tags=["Settlements"])


@router.get(
    "/settlements/{settlement_id}",
    response_model=SettlementResponse,
    summary="Retrieve single settlement recommendation by settlement ID",
)
def get_settlement(
    settlement_id: str,
    db: SessionDep,
) -> SettlementResponse:
    """Fetch settlement recommendation details by ID."""
    repo = SettlementRepository(db)
    settlement = repo.get_by_id(settlement_id)
    if not settlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settlement '{settlement_id}' not found",
        )
    return SettlementResponse.model_validate(settlement)


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
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )
    repo = SettlementRepository(db)
    settlements = repo.get_by_claim_id(claim_id)
    return [SettlementResponse.model_validate(s) for s in settlements]


@router.post(
    "/claims/{claim_id}/settlements/recommend",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a formal settlement recommendation for a claim",
)
def recommend_settlement(
    claim_id: str,
    service: Annotated[SettlementService, Depends(get_settlement_service)],
    db: SessionDep,
) -> SettlementResponse:
    """Compute and persist an actuarial settlement recommendation."""
    claim_repo = ClaimRepository(db)
    claim = claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )

    coverage_repo = CoverageRepository(db)
    coverages = coverage_repo.get_active_coverages_for_policy(claim.policy_id)
    if not coverages:
        coverages = coverage_repo.list_by_policy(claim.policy_id)
    if not coverages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No coverage terms found for policy '{claim.policy_id}'",
        )

    coverage = coverages[0]
    try:
        settlement = service.recommend_settlement(claim, coverage)
        return SettlementResponse.model_validate(settlement)
    except SettlementLimitExceededError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


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
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/settlements/{settlement_id}/disburse",
    response_model=SettlementPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Disburse payment for an approved settlement with duplicate payment protection",
)
@router.post(
    "/settlements/{settlement_id}/pay",
    response_model=SettlementPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Disburse payment for an approved settlement (alias)",
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
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DuplicatePaymentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
