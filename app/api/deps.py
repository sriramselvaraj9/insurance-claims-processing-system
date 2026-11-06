"""FastAPI route dependencies and service factories."""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import (
    AdjusterAssignmentRepository,
    AdjusterRepository,
    AssessmentRepository,
    AuditRepository,
    ClaimItemRepository,
    ClaimRepository,
    ClaimStatusHistoryRepository,
    CoverageRepository,
    CustomerRepository,
    DocumentRepository,
    DocumentRequestRepository,
    IncidentRepository,
    PolicyRepository,
    ReserveRepository,
    SettlementPaymentRepository,
    SettlementRepository,
)
from app.services import (
    AdjusterService,
    ClaimIntakeService,
    ClaimsProcessingService,
    CoverageService,
    DocumentService,
    DuplicateDetectionService,
    EligibilityService,
    FraudService,
    PolicyValidationService,
    ReserveService,
    SettlementService,
)

SessionDep = Annotated[Session, Depends(get_db)]


def get_claim_intake_service(db: SessionDep) -> ClaimIntakeService:
    return ClaimIntakeService(
        claim_repo=ClaimRepository(db),
        claim_item_repo=ClaimItemRepository(db),
        customer_repo=CustomerRepository(db),
        policy_repo=PolicyRepository(db),
        incident_repo=IncidentRepository(db),
        audit_repo=AuditRepository(db),
        csh_repo=ClaimStatusHistoryRepository(db),
    )


def get_document_service(db: SessionDep) -> DocumentService:
    return DocumentService(
        doc_repo=DocumentRepository(db),
        doc_req_repo=DocumentRequestRepository(db),
        audit_repo=AuditRepository(db),
    )


def get_settlement_service(db: SessionDep) -> SettlementService:
    return SettlementService(
        settlement_repo=SettlementRepository(db),
        payment_repo=SettlementPaymentRepository(db),
        claim_repo=ClaimRepository(db),
        audit_repo=AuditRepository(db),
    )


def get_claims_processing_service(db: SessionDep) -> ClaimsProcessingService:
    claim_repo = ClaimRepository(db)
    policy_repo = PolicyRepository(db)
    incident_repo = IncidentRepository(db)
    coverage_repo = CoverageRepository(db)
    doc_repo = DocumentRepository(db)
    doc_req_repo = DocumentRequestRepository(db)
    adj_repo = AdjusterRepository(db)
    asn_repo = AdjusterAssignmentRepository(db)
    reserve_repo = ReserveRepository(db)
    settle_repo = SettlementRepository(db)
    pay_repo = SettlementPaymentRepository(db)
    asm_repo = AssessmentRepository(db)
    audit_repo = AuditRepository(db)
    csh_repo = ClaimStatusHistoryRepository(db)

    policy_validation_service = PolicyValidationService(policy_repo, audit_repo)
    coverage_service = CoverageService(coverage_repo, audit_repo)
    document_service = DocumentService(doc_repo, doc_req_repo, audit_repo)
    duplicate_service = DuplicateDetectionService(claim_repo, incident_repo)
    fraud_service = FraudService(claim_repo)
    eligibility_service = EligibilityService(asm_repo, audit_repo)
    adjuster_service = AdjusterService(adj_repo, asn_repo, claim_repo, audit_repo)
    reserve_service = ReserveService(reserve_repo, audit_repo)
    settlement_service = SettlementService(settle_repo, pay_repo, claim_repo, audit_repo)

    return ClaimsProcessingService(
        claim_repo=claim_repo,
        policy_repo=policy_repo,
        incident_repo=incident_repo,
        csh_repo=csh_repo,
        policy_validation_service=policy_validation_service,
        coverage_service=coverage_service,
        document_service=document_service,
        duplicate_service=duplicate_service,
        fraud_service=fraud_service,
        eligibility_service=eligibility_service,
        adjuster_service=adjuster_service,
        reserve_service=reserve_service,
        settlement_service=settlement_service,
    )
