"""Integration tests for claims processing REST API endpoints and handlers."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    get_claim_intake_service,
    get_claims_processing_service,
    get_document_service,
    get_settlement_service,
)
from app.api.v1.claims import (
    create_claim,
    get_claim,
    get_claim_assessments,
    get_claim_audit_trail,
    get_claim_status_history,
    process_claim,
    reassess_claim,
)
from app.api.v1.documents import (
    attach_document,
    list_claim_documents,
    list_document_requests,
    verify_document,
)
from app.api.v1.settlements import (
    approve_settlement,
    disburse_payment,
    get_claim_settlements,
)
from app.models.adjuster import Adjuster
from app.models.base import Base
from app.models.coverage import Coverage
from app.models.customer import Customer
from app.models.enums import (
    AdjusterSpecialization,
    AdjusterStatus,
    AssessmentOutcome,
    ClaimStatus,
    ClaimType,
    CoverageType,
    DocumentType,
    PaymentMethod,
    PaymentStatus,
    PolicyStatus,
    PolicyType,
    SettlementStatus,
    VerificationStatus,
)
from app.models.incident import Incident
from app.models.policy import Policy
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_item_repository import ClaimItemRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_status_history_repository import ClaimStatusHistoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_request_repository import DocumentRequestRepository
from app.repositories.settlement_repository import SettlementRepository
from app.schemas.claim_schemas import (
    ClaimIntakeRequest,
    ClaimItemCreate,
    ClaimResponse,
)
from app.schemas.document_schemas import DocumentCreateRequest, DocumentVerifyRequest
from app.schemas.settlement_schemas import SettlementApproveRequest, SettlementDisburseRequest


@pytest.fixture
def db_session():
    """In-memory SQLite session isolated per test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def seed_data(db_session: Session):
    """Seed base customer, policy, coverage, incident, and adjuster."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    customer = Customer(
        id="CUST-INT-0001",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="555-0100",
        date_of_birth=date(1985, 5, 20),
    )
    db_session.add(customer)

    policy = Policy(
        id="POL-INT-0001",
        customer_id=customer.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("1200.00"),
        deductible=Decimal("500.00"),
    )
    db_session.add(policy)

    coverage = Coverage(
        id="COV-INT-0001",
        policy_id=policy.id,
        coverage_type=CoverageType.COLLISION,
        coverage_limit=Decimal("50000.00"),
        deductible=Decimal("500.00"),
        copay_percentage=Decimal("0.00"),
        is_active=True,
        exclusions=[],
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
    )
    db_session.add(coverage)

    incident = Incident(
        id="INC-INT-0001",
        incident_type="VEHICLE_COLLISION",
        occurrence_date=datetime(2026, 6, 10, 14, 30, 0, tzinfo=timezone.utc),
        description="Two-vehicle rear-end collision at traffic signal.",
        location_street="I-25 Mile Marker 104",
        location_city="Denver",
        location_state="CO",
        location_zip="80202",
        police_report_filed=True,
        police_report_number="PD-CO-2026-9912",
    )
    db_session.add(incident)

    adjuster = Adjuster(
        id="ADJ-INT-0001",
        employee_id="EMP-INT-001",
        name="Marcus Vance",
        email="marcus.vance@yottaflex.ai",
        phone="+1-800-555-09",
        specialization=AdjusterSpecialization.AUTO,
        status=AdjusterStatus.ACTIVE,
        max_capacity=20,
        active_claims_count=2,
    )
    db_session.add(adjuster)

    db_session.commit()
    return {
        "customer": customer,
        "policy": policy,
        "coverage": coverage,
        "incident": incident,
        "adjuster": adjuster,
    }


def test_api_intake_claim_success(db_session: Session, seed_data):
    """Test claim intake endpoint with valid payload."""
    service = get_claim_intake_service(db_session)
    payload = ClaimIntakeRequest(
        customer_id=seed_data["customer"].id,
        policy_id=seed_data["policy"].id,
        incident_id=seed_data["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("3200.00"),
        description="Front bumper collision damage",
        line_items=[
            ClaimItemCreate(
                item_description="Front Bumper Replacement",
                quantity=1,
                unit_amount=Decimal("2200.00"),
                total_amount=Decimal("2200.00"),
            ),
            ClaimItemCreate(
                item_description="Paint and Labor",
                quantity=1,
                unit_amount=Decimal("1000.00"),
                total_amount=Decimal("1000.00"),
            ),
        ],
    )
    resp = create_claim(payload=payload, service=service)
    assert resp.id.startswith("CLM-")
    assert resp.status == ClaimStatus.SUBMITTED
    assert resp.customer_id == seed_data["customer"].id
    assert resp.policy_id == seed_data["policy"].id
    assert resp.claimed_amount == Decimal("3200.00")

    item_repo = ClaimItemRepository(db_session)
    items = item_repo.list_by_claim(resp.id)
    assert len(items) == 2


def test_api_intake_claim_ownership_mismatch(db_session: Session, seed_data):
    """Test intake rejection when customer does not own policy (NEG-01)."""
    service = get_claim_intake_service(db_session)
    # Create an actual secondary customer who does not own the policy
    other_cust = Customer(
        id="CUST-OTHER-0002",
        first_name="Bob",
        last_name="Jones",
        email="bob.jones@example.com",
        phone="555-0200",
        date_of_birth=date(1990, 1, 1),
    )
    db_session.add(other_cust)
    db_session.commit()

    payload = ClaimIntakeRequest(
        customer_id=other_cust.id,
        policy_id=seed_data["policy"].id,
        incident_id=seed_data["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("3000.00"),
        description="Ownership mismatch test",
        line_items=[],
    )
    with pytest.raises(HTTPException) as exc_info:
        create_claim(payload=payload, service=service)
    assert exc_info.value.status_code == 400
    assert "does not own policy" in str(exc_info.value.detail)


def test_api_intake_claim_nonexistent_policy(db_session: Session, seed_data):
    """Test intake rejection when policy does not exist."""
    service = get_claim_intake_service(db_session)
    payload = ClaimIntakeRequest(
        customer_id=seed_data["customer"].id,
        policy_id="POL-NONEXISTENT",
        incident_id=seed_data["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("3000.00"),
        description="Nonexistent policy test",
        line_items=[],
    )
    with pytest.raises(HTTPException) as exc_info:
        create_claim(payload=payload, service=service)
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail).lower()


def test_api_get_claim_endpoint(db_session: Session, seed_data):
    """Test retrieval of an existing claim by ID."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=seed_data["customer"].id,
            policy_id=seed_data["policy"].id,
            incident_id=seed_data["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, 9, 0, 0, tzinfo=timezone.utc),
            claimed_amount=Decimal("1500.00"),
            description="Minor scrape",
            claim_items=[],
        )
    )
    fetched = get_claim(claim_id=claim.id, db=db_session)
    assert fetched.id == claim.id
    assert fetched.claimed_amount == Decimal("1500.00")

    with pytest.raises(HTTPException) as exc_info:
        get_claim(claim_id="CLM-UNKNOWN-9999", db=db_session)
    assert exc_info.value.status_code == 404


def test_api_workflow_end_to_end_lifecycle(db_session: Session, seed_data):
    """Test complete API workflow lifecycle: intake -> process -> attach docs -> verify -> reassess -> approve -> disburse -> duplicate payment block."""
    intake_svc = get_claim_intake_service(db_session)
    workflow_svc = get_claims_processing_service(db_session)
    doc_svc = get_document_service(db_session)
    settlement_svc = get_settlement_service(db_session)

    # 1. Intake
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=seed_data["customer"].id,
            policy_id=seed_data["policy"].id,
            incident_id=seed_data["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=seed_data["incident"].occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("4000.00"),
            description="Complete lifecycle test",
            line_items=[
                ClaimItemCreate(
                    item_description="Collision repair work",
                    quantity=1,
                    unit_amount=Decimal("4000.00"),
                    total_amount=Decimal("4000.00"),
                )
            ],
        )
    )

    # 2. Process claim (Missing documents -> PENDING_DOCUMENTS outcome and INFO_REQUESTED status)
    proc_res = process_claim(claim_id=claim.id, service=workflow_svc)
    assert proc_res.outcome == AssessmentOutcome.PENDING_DOCUMENTS.value
    assert proc_res.status == ClaimStatus.INFO_REQUESTED
    assert len(proc_res.missing_document_types) >= 1

    # 3. Attach required documents
    doc_ids = []
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        doc_upload = DocumentCreateRequest(
            document_type=dt,
            file_name=f"{dt.value.lower()}.pdf",
            file_type="application/pdf",
            file_path=f"/storage/claims/{claim.id}/{dt.value.lower()}.pdf",
            file_size_bytes=1024,
            checksum_sha256="a" * 64,
        )
        doc_resp = attach_document(claim_id=claim.id, payload=doc_upload, service=doc_svc)
        doc_ids.append(doc_resp.id)

    # 4. Verify all documents
    for doc_id in doc_ids:
        verify_req = DocumentVerifyRequest(
            verification_status=VerificationStatus.VERIFIED,
            verified_by="QA_OFFICER",
        )
        verify_resp = verify_document(document_id=doc_id, payload=verify_req, service=doc_svc)
        assert verify_resp.verification_status == VerificationStatus.VERIFIED

    # 5. Reassess claim
    reassess_res = reassess_claim(claim_id=claim.id, service=workflow_svc)
    assert reassess_res.outcome == AssessmentOutcome.ELIGIBLE.value
    assert reassess_res.status == ClaimStatus.SETTLEMENT_RECOMMENDED
    assert reassess_res.assigned_adjuster_id is not None
    # Indemnity (3500) + 12% expense ratio (420) = 3920.00
    assert reassess_res.total_reserve == Decimal("3920.00")
    assert reassess_res.settlement_id is not None
    settlement_id = reassess_res.settlement_id

    # 6. Verify assessment history preserves both records
    assessments = get_claim_assessments(claim_id=claim.id, db=db_session)
    assert len(assessments) == 2
    assert {a.is_eligible for a in assessments} == {False, True}

    # 7. Approve settlement
    approve_req = SettlementApproveRequest(approved_by="SUPERVISOR-01")
    settle_resp = approve_settlement(settlement_id=settlement_id, payload=approve_req, service=settlement_svc)
    assert settle_resp.status == SettlementStatus.APPROVED

    # 8. Disburse payment
    disburse_req = SettlementDisburseRequest(
        payment_method=PaymentMethod.ACH,
        processed_by="FINANCE-SERVICE",
    )
    pay_resp = disburse_payment(settlement_id=settlement_id, payload=disburse_req, service=settlement_svc)
    assert pay_resp.status == PaymentStatus.COMPLETED
    # Net settlement = 4000 claimed - 500 deductible = 3500
    assert pay_resp.payment_amount == Decimal("3500.00")

    # 9. Strict duplicate payment prevention: second disbursement must raise HTTP 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        disburse_payment(settlement_id=settlement_id, payload=disburse_req, service=settlement_svc)
    assert exc_info.value.status_code == 409
    assert "Duplicate payment blocked" in str(exc_info.value.detail)

    # 10. Audit trail verification
    audit_events = get_claim_audit_trail(claim_id=claim.id, db=db_session)
    assert len(audit_events) >= 3
    actions = [e["action"] for e in audit_events]
    assert any("CLAIM" in str(a) for a in actions)
    assert any("ADJUSTER" in str(a) for a in actions)

    # 11. Lifecycle status history verification
    histories = get_claim_status_history(claim_id=claim.id, db=db_session)
    assert len(histories) >= 3
    to_statuses = [h["new_status"] for h in histories]
    assert ClaimStatus.SUBMITTED.value in to_statuses
    assert ClaimStatus.INFO_REQUESTED.value in to_statuses
    assert ClaimStatus.SETTLEMENT_RECOMMENDED.value in to_statuses
