"""Claims intake, status inquiry, and workflow orchestration endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    SessionDep,
    get_claim_intake_service,
    get_claims_processing_service,
)
from app.models.enums import ClaimStatus, ClaimType
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_status_history_repository import ClaimStatusHistoryRepository
from app.schemas.assessment_schemas import AssessmentResponse
from app.schemas.audit_schemas import AuditEventResponse, ClaimStatusHistoryResponse
from app.schemas.claim_schemas import (
    ClaimIntakeRequest,
    ClaimProcessingResultResponse,
    ClaimResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.claim_intake_service import ClaimIntakeService
from app.services.claims_processing_service import ClaimsProcessingService
from app.services.exceptions import (
    ClaimNotFoundError,
    CustomerNotFoundError,
    CustomerPolicyMismatchError,
    DuplicateClaimSubmissionError,
    IncidentNotFoundError,
    InvalidFinancialValueError,
    PolicyNotFoundError,
)

router = APIRouter(prefix="/claims", tags=["Claims"])


@router.get(
    "",
    response_model=PaginatedResponse[ClaimResponse],
    summary="List claims with database-level pagination and filtering",
)
def list_claims(
    db: SessionDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    status: Annotated[ClaimStatus | None, Query(description="Filter by claim status")] = None,
    claim_type: Annotated[ClaimType | None, Query(description="Filter by claim type")] = None,
    customer_id: Annotated[str | None, Query(description="Filter by customer ID")] = None,
    policy_id: Annotated[str | None, Query(description="Filter by policy ID")] = None,
) -> PaginatedResponse[ClaimResponse]:
    """Retrieve claims with database-level pagination and filtering."""
    repo = ClaimRepository(db)
    skip = (page - 1) * page_size
    items, total = repo.list_paginated(
        skip=skip,
        limit=page_size,
        status=status,
        claim_type=claim_type,
        customer_id=customer_id,
        policy_id=policy_id,
    )
    return PaginatedResponse.create(
        items=[ClaimResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new insurance claim (Intake)",
)
def create_claim(
    payload: ClaimIntakeRequest,
    service: Annotated[ClaimIntakeService, Depends(get_claim_intake_service)],
) -> ClaimResponse:
    """Intake a new claim with customer, policy, incident, ownership, and duplicate validation."""
    try:
        claim = service.intake_claim(payload)
        return ClaimResponse.model_validate(claim)
    except (CustomerNotFoundError, PolicyNotFoundError, IncidentNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except (CustomerPolicyMismatchError, InvalidFinancialValueError, DuplicateClaimSubmissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{claim_id}",
    response_model=ClaimResponse,
    summary="Retrieve claim details by claim ID",
)
def get_claim(
    claim_id: str,
    db: SessionDep,
) -> ClaimResponse:
    """Fetch current state of a claim."""
    repo = ClaimRepository(db)
    claim = repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found")
    return ClaimResponse.model_validate(claim)


@router.post(
    "/{claim_id}/process",
    response_model=ClaimProcessingResultResponse,
    summary="Execute multi-stage claims processing workflow",
)
def process_claim(
    claim_id: str,
    service: Annotated[ClaimsProcessingService, Depends(get_claims_processing_service)],
) -> ClaimProcessingResultResponse:
    """Run full automated policy, coverage, document, duplicate, and eligibility workflow."""
    try:
        result = service.process_claim(claim_id)
        return ClaimProcessingResultResponse(
            claim_id=result.claim_id,
            status=result.status,
            outcome=result.outcome.value,
            assessment_id=result.assessment_id,
            is_eligible=result.is_eligible,
            rejection_code=result.rejection_code,
            decision_reasons=result.decision_reasons,
            assigned_adjuster_id=result.assigned_adjuster_id,
            reserve_id=result.reserve_id,
            total_reserve=result.total_reserve,
            settlement_id=result.settlement_id,
            net_settlement_amount=result.net_settlement_amount,
            missing_document_types=result.missing_document_types,
            rule_results=result.rule_results,
            fraud_indicators=result.fraud_indicators,
        )
    except ClaimNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post(
    "/{claim_id}/reassess",
    response_model=ClaimProcessingResultResponse,
    summary="Re-evaluate claim eligibility preserving assessment history",
)
def reassess_claim(
    claim_id: str,
    service: Annotated[ClaimsProcessingService, Depends(get_claims_processing_service)],
) -> ClaimProcessingResultResponse:
    """Re-evaluate an existing claim after additional documentation or evidence."""
    try:
        result = service.reassess_claim(claim_id)
        return ClaimProcessingResultResponse(
            claim_id=result.claim_id,
            status=result.status,
            outcome=result.outcome.value,
            assessment_id=result.assessment_id,
            is_eligible=result.is_eligible,
            rejection_code=result.rejection_code,
            decision_reasons=result.decision_reasons,
            assigned_adjuster_id=result.assigned_adjuster_id,
            reserve_id=result.reserve_id,
            total_reserve=result.total_reserve,
            settlement_id=result.settlement_id,
            net_settlement_amount=result.net_settlement_amount,
            missing_document_types=result.missing_document_types,
            rule_results=result.rule_results,
            fraud_indicators=result.fraud_indicators,
        )
    except ClaimNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/{claim_id}/assessments",
    response_model=list[AssessmentResponse],
    summary="Retrieve full append-only eligibility assessment history for a claim",
)
def get_claim_assessments(
    claim_id: str,
    db: SessionDep,
) -> list[AssessmentResponse]:
    """Retrieve all historical assessment records for a claim."""
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found")
    repo = AssessmentRepository(db)
    assessments = repo.get_by_claim_id(claim_id)
    return [AssessmentResponse.model_validate(a) for a in assessments]


@router.get(
    "/{claim_id}/history",
    response_model=list[ClaimStatusHistoryResponse],
    summary="Retrieve full status transition audit trail for a claim",
)
def get_claim_status_history(
    claim_id: str,
    db: SessionDep,
) -> list[ClaimStatusHistoryResponse]:
    """Retrieve chronological claim status progression history."""
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found")
    repo = ClaimStatusHistoryRepository(db)
    history = repo.get_by_claim_id(claim_id)
    return [ClaimStatusHistoryResponse.model_validate(h) for h in history]


@router.get(
    "/{claim_id}/audit-trail",
    response_model=list[AuditEventResponse],
    summary="Retrieve full audit log for a claim",
)
@router.get(
    "/{claim_id}/audit",
    response_model=list[AuditEventResponse],
    summary="Retrieve full audit log for a claim (alias)",
)
def get_claim_audit_trail(
    claim_id: str,
    db: SessionDep,
) -> list[AuditEventResponse]:
    """Retrieve chronological audit trail of all actions taken on a claim."""
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found")
    repo = AuditRepository(db)
    events = repo.get_by_entity(entity_type="CLAIM", entity_id=claim_id)
    return [AuditEventResponse.model_validate(e) for e in events]
