"""Claims intake, status inquiry, and workflow orchestration endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    SessionDep,
    get_claim_intake_service,
    get_claims_processing_service,
)
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_status_history_repository import ClaimStatusHistoryRepository
from app.schemas.assessment_schemas import AssessmentResponse
from app.schemas.claim_schemas import (
    ClaimIntakeRequest,
    ClaimProcessingResultResponse,
    ClaimResponse,
)
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
    repo = AssessmentRepository(db)
    assessments = repo.get_by_claim_id(claim_id)
    return [AssessmentResponse.model_validate(a) for a in assessments]


@router.get(
    "/{claim_id}/history",
    summary="Retrieve full status transition audit trail for a claim",
)
def get_claim_status_history(
    claim_id: str,
    db: SessionDep,
) -> list[dict]:
    """Retrieve chronological claim status progression history."""
    repo = ClaimStatusHistoryRepository(db)
    history = repo.get_by_claim_id(claim_id)
    return [
        {
            "id": h.id,
            "claim_id": h.claim_id,
            "previous_status": h.previous_status,
            "new_status": h.new_status,
            "transition_reason": h.transition_reason,
            "changed_by": h.changed_by,
            "timestamp": h.timestamp.isoformat(),
        }
        for h in history
    ]


@router.get(
    "/{claim_id}/audit-trail",
    summary="Retrieve full audit log for a claim",
)
def get_claim_audit_trail(
    claim_id: str,
    db: SessionDep,
) -> list[dict]:
    """Retrieve chronological audit trail of all actions taken on a claim."""
    repo = AuditRepository(db)
    events = repo.get_by_entity(entity_type="CLAIM", entity_id=claim_id)
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "action": e.action,
            "actor_type": e.actor_type.value if hasattr(e.actor_type, "value") else str(e.actor_type),
            "actor_id": e.actor_id,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]

