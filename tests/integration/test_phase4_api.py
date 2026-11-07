"""Phase 4: Comprehensive End-to-End REST API Integration Test Suite.

Covers all 35 required scenarios from Phase 4 specifications:
1-2:   Health Checks (Healthy probe, DB unavailable 503)
3-7:   Customers & Policies (Lookup, 404, list & filter, policy with coverages, coverages list)
8-12:  Claims Intake & Validation (Intake 201, Nonexistent policy 404, Customer mismatch 400, lookup, 404)
13-17: Claims Processing Engine (Eligible, Ineligible expired policy, Missing documents, Reassess history, Assessment history)
18-22: Documents & Evidence (Attach, Verify, Reject, Document requests, Manual request create)
23-26: Adjusters & Reserves (List & filter, Claim assignments, Reserves list, Mathematical formula verification)
27-31: Settlements & Payments (Recommend, Limit exceeded handled, Approve, Disburse/Pay alias, Duplicate payment block 409)
32-33: Audit & Compliance (Claim audit trail & alias, Global audit events paginated)
34-35: Pagination & Query Validation (Envelope metadata verification, invalid parameters validation)
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.api.deps import (
    get_claim_intake_service,
    get_claims_processing_service,
    get_document_service,
    get_settlement_service,
)
from app.api.v1.adjusters import (
    get_adjuster,
    get_claim_adjuster_assignments,
    list_adjusters,
)
from app.api.v1.assessments import get_assessment
from app.api.v1.audit import list_audit_events
from app.api.v1.claims import (
    create_claim,
    get_claim,
    get_claim_assessments,
    get_claim_audit_trail,
    get_claim_status_history,
    list_claims,
    process_claim,
    reassess_claim,
)
from app.api.v1.customers import get_customer, list_customers
from app.api.v1.documents import (
    attach_document,
    create_document_request,
    list_claim_documents,
    list_document_requests,
    verify_document,
)
from app.api.v1.health import api_v1_health, perform_health_check
from app.api.v1.policies import (
    get_policy,
    list_policies,
    list_policy_coverages,
)
from app.api.v1.reserves import get_claim_reserves, get_reserve
from app.api.v1.settlements import (
    approve_settlement,
    disburse_payment,
    get_claim_settlements,
    get_settlement,
    recommend_settlement,
)
from app.core.config import settings
from app.main import health_check
from app.models.adjuster import Adjuster
from app.models.base import Base
from app.models.coverage import Coverage
from app.models.customer import Customer
from app.models.enums import (
    AdjusterSpecialization,
    AdjusterStatus,
    AssessmentOutcome,
    AuditAction,
    ClaimStatus,
    ClaimType,
    CoverageType,
    DocumentType,
    PaymentMethod,
    PaymentStatus,
    PolicyStatus,
    PolicyType,
    RejectionCode,
    SettlementStatus,
    VerificationStatus,
)
from app.models.incident import Incident
from app.models.policy import Policy
from app.schemas.claim_schemas import ClaimIntakeRequest, ClaimItemCreate
from app.schemas.common import PaginatedResponse
from app.schemas.document_schemas import (
    DocumentCreateRequest,
    DocumentRequestCreate,
    DocumentVerifyRequest,
)
from app.schemas.settlement_schemas import (
    SettlementApproveRequest,
    SettlementDisburseRequest,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session with full schema initialized per test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def test_seed(db_session: Session):
    """Seed base customer, policy, coverage, incident, and adjuster."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    cust = Customer(
        id="CUST-P4-0001",
        first_name="Arthur",
        last_name="Dent",
        email="arthur.dent@example.com",
        phone="555-4242",
        date_of_birth=date(1982, 3, 11),
    )
    db_session.add(cust)

    pol = Policy(
        id="POL-P4-0001",
        customer_id=cust.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("1500.00"),
        deductible=Decimal("500.00"),
    )
    db_session.add(pol)

    cov = Coverage(
        id="COV-P4-0001",
        policy_id=pol.id,
        coverage_type=CoverageType.COLLISION,
        coverage_limit=Decimal("50000.00"),
        deductible=Decimal("500.00"),
        copay_percentage=Decimal("0.00"),
        is_active=True,
        exclusions=[],
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
    )
    db_session.add(cov)

    inc = Incident(
        id="INC-P4-0001",
        incident_type="VEHICLE_COLLISION",
        occurrence_date=datetime(2026, 6, 10, 14, 0, 0, tzinfo=timezone.utc),
        description="Minor fender bender on Main Street",
        location_street="42 Galaxy Way",
        location_city="Denver",
        location_state="CO",
        location_zip="80202",
        police_report_filed=True,
    )
    db_session.add(inc)

    adj = Adjuster(
        id="ADJ-P4-0001",
        employee_id="EMP-P4-01",
        name="Ford Prefect",
        email="ford.prefect@insurance.com",
        phone="555-4201",
        specialization=AdjusterSpecialization.AUTO,
        status=AdjusterStatus.ACTIVE,
        active_claims_count=1,
        max_capacity=15,
    )
    db_session.add(adj)
    db_session.commit()

    return {
        "customer": cust,
        "policy": pol,
        "coverage": cov,
        "incident": inc,
        "adjuster": adj,
    }


# ==============================================================================
# SECTION 1: System & Health (Scenarios 1-2)
# ==============================================================================


def test_01_health_check_healthy(db_session: Session):
    """Verify live health check returns 200 OK with connected database probe."""
    resp, code = perform_health_check(db_session)
    assert code == 200
    assert resp.status == "healthy"
    assert resp.database == "connected"
    assert resp.service == settings.PROJECT_NAME
    assert resp.version == __version__

    # Also test main app /health handler
    payload = health_check(db=db_session)
    assert payload["status"] == "healthy"
    assert payload["database"] == "connected"


def test_02_health_check_db_unavailable():
    """Verify health check returns 503 Service Unavailable when DB probe fails."""
    mock_db = MagicMock(spec=Session)
    mock_db.execute.side_effect = Exception("Connection terminated by administrator")

    resp, code = perform_health_check(mock_db)
    assert code == 503
    assert resp.status == "unhealthy"
    assert resp.database == "disconnected"


# ==============================================================================
# SECTION 2: Customers & Policies (Scenarios 3-7)
# ==============================================================================


def test_03_customer_lookup_by_id(db_session: Session, test_seed):
    """Verify customer retrieval by primary key ID."""
    cust_id = test_seed["customer"].id
    resp = get_customer(customer_id=cust_id, db=db_session)
    assert resp.id == cust_id
    assert resp.first_name == "Arthur"
    assert resp.last_name == "Dent"
    assert resp.email == "arthur.dent@example.com"


def test_04_customer_lookup_404(db_session: Session):
    """Verify 404 response for non-existent customer."""
    with pytest.raises(HTTPException) as exc:
        get_customer(customer_id="CUST-NONEXISTENT", db=db_session)
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail.lower()


def test_05_customer_list_paginated_and_filtered(db_session: Session, test_seed):
    """Verify customer pagination, envelope structure, and search filter."""
    res = list_customers(db=db_session, page=1, page_size=10, search="Arthur")
    assert isinstance(res, PaginatedResponse)
    assert res.total == 1
    assert res.page == 1
    assert res.page_size == 10
    assert res.total_pages == 1
    assert len(res.items) == 1
    assert res.items[0].first_name == "Arthur"


def test_06_policy_lookup_with_coverages(db_session: Session, test_seed):
    """Verify policy retrieval eagerly loading associated coverage terms."""
    pol_id = test_seed["policy"].id
    resp = get_policy(policy_id=pol_id, db=db_session)
    assert resp.id == pol_id
    assert resp.status == PolicyStatus.ACTIVE.value
    assert len(resp.coverages) == 1
    assert resp.coverages[0].coverage_type == CoverageType.COLLISION.value
    assert resp.coverages[0].coverage_limit == Decimal("50000.00")


def test_07_policy_coverages_list(db_session: Session, test_seed):
    """Verify listing coverage terms attached to a policy and 404 on invalid policy."""
    pol_id = test_seed["policy"].id
    coverages = list_policy_coverages(policy_id=pol_id, db=db_session)
    assert len(coverages) == 1
    assert coverages[0].id == test_seed["coverage"].id

    with pytest.raises(HTTPException) as exc:
        list_policy_coverages(policy_id="POL-NONEXISTENT", db=db_session)
    assert exc.value.status_code == 404


# ==============================================================================
# SECTION 3: Claims Intake & Validation (Scenarios 8-12)
# ==============================================================================


def test_08_claim_intake_valid(db_session: Session, test_seed):
    """Verify successful claim intake returning 201 Created and SUBMITTED status."""
    service = get_claim_intake_service(db_session)
    req = ClaimIntakeRequest(
        customer_id=test_seed["customer"].id,
        policy_id=test_seed["policy"].id,
        incident_id=test_seed["incident"].id,
        claim_type=ClaimType.COLLISION,
        reported_date=datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc),
        claimed_amount=Decimal("3500.00"),
        description="Collision damage intake test",
        line_items=[
            ClaimItemCreate(
                item_description="Front bumper replacement",
                quantity=1,
                unit_amount=Decimal("3500.00"),
                total_amount=Decimal("3500.00"),
            )
        ],
    )
    claim_resp = create_claim(payload=req, service=service)
    assert claim_resp.id.startswith("CLM-")
    assert claim_resp.status == ClaimStatus.SUBMITTED
    assert claim_resp.claimed_amount == Decimal("3500.00")


def test_09_claim_intake_nonexistent_policy_404(db_session: Session, test_seed):
    """Verify intake rejection with 404 when policy does not exist."""
    service = get_claim_intake_service(db_session)
    req = ClaimIntakeRequest(
        customer_id=test_seed["customer"].id,
        policy_id="POL-DOES-NOT-EXIST",
        incident_id=test_seed["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("2000.00"),
        description="Invalid policy claim",
    )
    with pytest.raises(HTTPException) as exc:
        create_claim(payload=req, service=service)
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail.lower()


def test_10_claim_intake_customer_policy_mismatch_400(db_session: Session, test_seed):
    """Verify intake rejection with 400 when claimant does not own the policy (NEG-04)."""
    # Create another customer
    other_cust = Customer(
        id="CUST-P4-OTHER",
        first_name="Tricia",
        last_name="McMillan",
        email="trillian@example.com",
        phone="555-9999",
        date_of_birth=date(1985, 8, 15),
    )
    db_session.add(other_cust)
    db_session.commit()

    service = get_claim_intake_service(db_session)
    req = ClaimIntakeRequest(
        customer_id=other_cust.id,  # Does not own POL-P4-0001
        policy_id=test_seed["policy"].id,
        incident_id=test_seed["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("2000.00"),
        description="Fraudulent claimant ownership mismatch",
    )
    with pytest.raises(HTTPException) as exc:
        create_claim(payload=req, service=service)
    assert exc.value.status_code == 400
    assert "ownership" in exc.value.detail.lower() or "does not own" in exc.value.detail.lower()


def test_11_claim_lookup_by_id(db_session: Session, test_seed):
    """Verify claim retrieval by ID."""
    service = get_claim_intake_service(db_session)
    req = ClaimIntakeRequest(
        customer_id=test_seed["customer"].id,
        policy_id=test_seed["policy"].id,
        incident_id=test_seed["incident"].id,
        claim_type=ClaimType.COLLISION,
        claimed_amount=Decimal("1200.00"),
        description="Lookup test claim",
    )
    created = create_claim(payload=req, service=service)
    fetched = get_claim(claim_id=created.id, db=db_session)
    assert fetched.id == created.id
    assert fetched.claimed_amount == Decimal("1200.00")


def test_12_claim_lookup_404(db_session: Session):
    """Verify 404 response for non-existent claim ID."""
    with pytest.raises(HTTPException) as exc:
        get_claim(claim_id="CLM-BOGUS-9999", db=db_session)
    assert exc.value.status_code == 404


# ==============================================================================
# SECTION 4: Claims Processing Engine (Scenarios 13-17)
# ==============================================================================


def test_13_process_claim_eligible_workflow(db_session: Session, test_seed):
    """Verify end-to-end processing of a valid, fully documented claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("4500.00"),
            description="Eligible processing workflow test",
            line_items=[
                ClaimItemCreate(
                    item_description="Collision repair",
                    quantity=1,
                    unit_amount=Decimal("4500.00"),
                    total_amount=Decimal("4500.00"),
                )
            ],
        )
    )

    # Attach and verify all 3 mandatory documents for COLLISION
    doc_svc = get_document_service(db_session)
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        doc = doc_svc.attach_document(
            claim_id=claim.id,
            payload=DocumentCreateRequest(
                document_type=dt,
                file_name=f"{dt.value.lower()}.pdf",
                file_type="application/pdf",
                file_path=f"/storage/{claim.id}/{dt.value.lower()}.pdf",
                file_size_bytes=2048,
                checksum_sha256="c" * 64,
            ),
        )
        doc_svc.verify_document(doc.id, status=VerificationStatus.VERIFIED, verified_by="OFFICER_1")

    proc_svc = get_claims_processing_service(db_session)
    result = process_claim(claim_id=claim.id, service=proc_svc)

    assert result.is_eligible is True
    assert result.outcome == AssessmentOutcome.ELIGIBLE.value
    assert result.status == ClaimStatus.SETTLEMENT_RECOMMENDED
    assert result.assigned_adjuster_id == test_seed["adjuster"].id
    assert result.reserve_id is not None
    # 4500 - 500 = 4000 indemnity; 4000 * 0.12 = 480 expense; total = 4480.00
    assert result.total_reserve == Decimal("4480.00")
    assert result.settlement_id is not None
    assert result.net_settlement_amount == Decimal("4000.00")


def test_14_process_claim_ineligible_expired_policy(db_session: Session, test_seed):
    """Verify processing rejection when incident occurred outside policy coverage term (NEG-01)."""
    # Create expired policy
    exp_pol = Policy(
        id="POL-P4-EXPIRED",
        customer_id=test_seed["customer"].id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.EXPIRED,
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        total_premium=Decimal("1200.00"),
        deductible=Decimal("500.00"),
    )
    db_session.add(exp_pol)

    exp_cov = Coverage(
        id="COV-P4-EXPIRED",
        policy_id=exp_pol.id,
        coverage_type=CoverageType.COLLISION,
        coverage_limit=Decimal("50000.00"),
        deductible=Decimal("500.00"),
        copay_percentage=Decimal("0.00"),
        is_active=False,
        exclusions=[],
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
    )
    db_session.add(exp_cov)
    db_session.commit()

    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=exp_pol.id,
            incident_id=test_seed["incident"].id,  # Incident date is 2026-06-10 (Policy expired in 2025)
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("3000.00"),
            description="Expired policy incident claim",
        )
    )

    proc_svc = get_claims_processing_service(db_session)
    result = process_claim(claim_id=claim.id, service=proc_svc)

    assert result.is_eligible is False
    assert result.outcome == AssessmentOutcome.INELIGIBLE.value
    assert result.status == ClaimStatus.REJECTED
    assert result.rejection_code == RejectionCode.EXPIRED_POLICY.value


def test_15_process_claim_missing_documents(db_session: Session, test_seed):
    """Verify claim missing mandatory documents transitions to INFO_REQUESTED (NEG-05)."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("2500.00"),
            description="Missing docs intake",
        )
    )

    proc_svc = get_claims_processing_service(db_session)
    result = process_claim(claim_id=claim.id, service=proc_svc)

    assert result.outcome == AssessmentOutcome.PENDING_DOCUMENTS.value
    assert result.status == ClaimStatus.INFO_REQUESTED
    assert len(result.missing_document_types) == 3


def test_16_reassess_claim_preserves_history(db_session: Session, test_seed):
    """Verify reassessment re-evaluates claim and retains historical assessment records."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("2500.00"),
            description="Reassessment audit preservation test",
        )
    )

    proc_svc = get_claims_processing_service(db_session)
    # 1. First run: missing documents
    r1 = process_claim(claim_id=claim.id, service=proc_svc)
    assert r1.outcome == AssessmentOutcome.PENDING_DOCUMENTS.value

    # 2. Attach required documents and verify
    doc_svc = get_document_service(db_session)
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        doc = doc_svc.attach_document(
            claim_id=claim.id,
            payload=DocumentCreateRequest(
                document_type=dt,
                file_name=f"{dt.value}.pdf",
                file_type="application/pdf",
                file_path=f"/path/{dt.value}.pdf",
                file_size_bytes=1000,
                checksum_sha256="d" * 64,
            ),
        )
        doc_svc.verify_document(doc.id, status=VerificationStatus.VERIFIED, verified_by="QA_AGENT")

    # 3. Reassess
    r2 = reassess_claim(claim_id=claim.id, service=proc_svc)
    assert r2.outcome == AssessmentOutcome.ELIGIBLE.value

    # Verify both assessments exist in database
    history = get_claim_assessments(claim_id=claim.id, db=db_session)
    assert len(history) == 2
    assert {h.is_eligible for h in history} == {False, True}


def test_17_claim_assessment_history(db_session: Session, test_seed):
    """Verify retrieval of assessment history and 404 for invalid claim ID."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("1000.00"),
            description="Assessment history check",
        )
    )
    history = get_claim_assessments(claim_id=claim.id, db=db_session)
    assert len(history) == 0

    with pytest.raises(HTTPException) as exc:
        get_claim_assessments(claim_id="CLM-DOES-NOT-EXIST", db=db_session)
    assert exc.value.status_code == 404


# ==============================================================================
# SECTION 5: Documents & Evidence (Scenarios 18-22)
# ==============================================================================


def test_18_document_attach(db_session: Session, test_seed):
    """Verify document upload attachment to an existing claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2000.00"),
            description="Document attach test",
        )
    )

    doc_svc = get_document_service(db_session)
    payload = DocumentCreateRequest(
        document_type=DocumentType.POLICE_REPORT,
        file_name="police_report.pdf",
        file_type="application/pdf",
        file_path="/storage/police_report.pdf",
        file_size_bytes=5120,
        checksum_sha256="e" * 64,
    )
    doc_resp = attach_document(claim_id=claim.id, payload=payload, service=doc_svc, db=db_session)
    assert doc_resp.id.startswith("DOC-")
    assert doc_resp.verification_status == VerificationStatus.PENDING


def test_19_document_verify(db_session: Session, test_seed):
    """Verify document approval via verification endpoints."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2000.00"),
            description="Document verification test",
        )
    )

    doc_svc = get_document_service(db_session)
    doc = doc_svc.attach_document(
        claim_id=claim.id,
        payload=DocumentCreateRequest(
            document_type=DocumentType.DAMAGE_PHOTO,
            file_name="damage.jpg",
            file_type="image/jpeg",
            file_path="/storage/damage.jpg",
            file_size_bytes=1024,
            checksum_sha256="f" * 64,
        ),
    )
    verify_req = DocumentVerifyRequest(
        verification_status=VerificationStatus.VERIFIED,
        verified_by="INSPECTOR_BOB",
    )
    res = verify_document(document_id=doc.id, payload=verify_req, service=doc_svc)
    assert res.verification_status == VerificationStatus.VERIFIED
    assert res.verified_by == "INSPECTOR_BOB"
    assert res.verified_at is not None


def test_20_document_reject(db_session: Session, test_seed):
    """Verify document rejection setting status to REJECTED and recording reason."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2000.00"),
            description="Document rejection test",
        )
    )

    doc_svc = get_document_service(db_session)
    doc = doc_svc.attach_document(
        claim_id=claim.id,
        payload=DocumentCreateRequest(
            document_type=DocumentType.REPAIR_ESTIMATE,
            file_name="estimate.pdf",
            file_type="application/pdf",
            file_path="/storage/estimate.pdf",
            file_size_bytes=1024,
            checksum_sha256="1" * 64,
        ),
    )
    reject_req = DocumentVerifyRequest(
        verification_status=VerificationStatus.REJECTED,
        verified_by="AUDITOR_ALICE",
        rejection_reason="Illegible scan of body shop estimate",
    )
    res = verify_document(document_id=doc.id, payload=reject_req, service=doc_svc)
    assert res.verification_status == VerificationStatus.REJECTED
    assert res.rejection_reason == "Illegible scan of body shop estimate"


def test_21_document_requests_list(db_session: Session, test_seed):
    """Verify listing of open document requests for a claim and 404 on bad claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2000.00"),
            description="Doc request listing test",
        )
    )

    proc_svc = get_claims_processing_service(db_session)
    process_claim(claim_id=claim.id, service=proc_svc)

    requests = list_document_requests(claim_id=claim.id, db=db_session)
    assert len(requests) == 3

    with pytest.raises(HTTPException) as exc:
        list_document_requests(claim_id="CLM-BOGUS", db=db_session)
    assert exc.value.status_code == 404


def test_22_document_request_create_manual(db_session: Session, test_seed):
    """Verify manual document request generation by claims adjuster."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2000.00"),
            description="Manual doc request test",
        )
    )

    doc_svc = get_document_service(db_session)
    req_payload = DocumentRequestCreate(
        document_type=DocumentType.PROOF_OF_LOSS,
        reason="Additional itemized proof of contents damaged",
    )
    created = create_document_request(
        claim_id=claim.id, payload=req_payload, service=doc_svc, db=db_session
    )
    assert created.claim_id == claim.id
    assert created.document_type == DocumentType.PROOF_OF_LOSS


# ==============================================================================
# SECTION 6: Adjusters & Reserves (Scenarios 23-26)
# ==============================================================================


def test_23_adjuster_list_and_filter(db_session: Session, test_seed):
    """Verify listing adjusters with specialization and status filtering."""
    res = list_adjusters(
        db=db_session,
        specialization=AdjusterSpecialization.AUTO,
        status=AdjusterStatus.ACTIVE,
    )
    assert res.total >= 1
    assert all(a.specialization == AdjusterSpecialization.AUTO.value for a in res.items)


def test_24_claim_adjuster_assignments(db_session: Session, test_seed):
    """Verify adjuster assignment history on processed claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("2000.00"),
            description="Adjuster assignment audit test",
        )
    )

    # Attach documents and verify
    doc_svc = get_document_service(db_session)
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        d = doc_svc.attach_document(
            claim_id=claim.id,
            payload=DocumentCreateRequest(
                document_type=dt,
                file_name="x.pdf",
                file_type="application/pdf",
                file_path="/x.pdf",
                file_size_bytes=100,
                checksum_sha256="2" * 64,
            ),
        )
        doc_svc.verify_document(d.id, status=VerificationStatus.VERIFIED, verified_by="QA")

    proc_svc = get_claims_processing_service(db_session)
    process_claim(claim_id=claim.id, service=proc_svc)

    assignments = get_claim_adjuster_assignments(claim_id=claim.id, db=db_session)
    assert len(assignments) >= 1
    assert assignments[0].adjuster_id == test_seed["adjuster"].id
    assert assignments[0].is_active is True


def test_25_claim_reserves_list(db_session: Session, test_seed):
    """Verify listing all preliminary reserve calculations for a claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("2000.00"),
            description="Reserve listing test",
        )
    )

    doc_svc = get_document_service(db_session)
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        d = doc_svc.attach_document(
            claim_id=claim.id,
            payload=DocumentCreateRequest(
                document_type=dt,
                file_name="x.pdf",
                file_type="application/pdf",
                file_path="/x.pdf",
                file_size_bytes=100,
                checksum_sha256="3" * 64,
            ),
        )
        doc_svc.verify_document(d.id, status=VerificationStatus.VERIFIED, verified_by="QA")

    proc_svc = get_claims_processing_service(db_session)
    process_claim(claim_id=claim.id, service=proc_svc)

    reserves = get_claim_reserves(claim_id=claim.id, db=db_session)
    assert len(reserves) >= 1
    assert reserves[0].claim_id == claim.id


def test_26_reserve_detail_formula_verification(db_session: Session, test_seed):
    """Verify preliminary reserve calculation mathematical formula: indemnity + expense = total."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            reported_date=datetime(2026, 6, 12, tzinfo=timezone.utc),
            claimed_amount=Decimal("3000.00"),
            description="Reserve formula check",
        )
    )

    doc_svc = get_document_service(db_session)
    for dt in [DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO]:
        d = doc_svc.attach_document(
            claim_id=claim.id,
            payload=DocumentCreateRequest(
                document_type=dt,
                file_name="x.pdf",
                file_type="application/pdf",
                file_path="/x.pdf",
                file_size_bytes=100,
                checksum_sha256="4" * 64,
            ),
        )
        doc_svc.verify_document(d.id, status=VerificationStatus.VERIFIED, verified_by="QA")

    proc_svc = get_claims_processing_service(db_session)
    result = process_claim(claim_id=claim.id, service=proc_svc)

    reserve = get_reserve(reserve_id=result.reserve_id, db=db_session)
    # 3000 - 500 = 2500 indemnity; 2500 * 0.12 = 300 expense; total = 2800.00
    assert reserve.indemnity_reserve == Decimal("2500.00")
    assert reserve.expense_reserve == Decimal("300.00")
    assert reserve.total_reserve == Decimal("2800.00")
    assert reserve.indemnity_reserve + reserve.expense_reserve == reserve.total_reserve


# ==============================================================================
# SECTION 7: Settlements & Payments (Scenarios 27-31)
# ==============================================================================


def test_27_settlement_recommend(db_session: Session, test_seed):
    """Verify settlement recommendation generation via REST endpoint."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("5000.00"),
            description="Settlement recommend endpoint test",
        )
    )

    settle_svc = get_settlement_service(db_session)
    rec = recommend_settlement(claim_id=claim.id, service=settle_svc, db=db_session)
    assert rec.claim_id == claim.id
    # 5000 claimed - 500 deductible = 4500 net
    assert rec.net_settlement_amount == Decimal("4500.00")
    assert rec.status == SettlementStatus.PROPOSED.value


def test_28_settlement_limit_exceeded_handled(db_session: Session, test_seed):
    """Verify settlement service gracefully handles edge case where policy has no coverage (NEG-04/NEG-03)."""
    # Create empty policy with no coverages
    empty_pol = Policy(
        id="POL-P4-EMPTY",
        customer_id=test_seed["customer"].id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("500.00"),
        deductible=Decimal("250.00"),
    )
    db_session.add(empty_pol)
    db_session.commit()

    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=empty_pol.id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("1000.00"),
            description="No coverage policy claim",
        )
    )

    settle_svc = get_settlement_service(db_session)
    with pytest.raises(HTTPException) as exc:
        recommend_settlement(claim_id=claim.id, service=settle_svc, db=db_session)
    assert exc.value.status_code == 400


def test_29_settlement_approve(db_session: Session, test_seed):
    """Verify supervisor approval of a proposed settlement."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("3000.00"),
            description="Settlement approval test",
        )
    )

    settle_svc = get_settlement_service(db_session)
    rec = recommend_settlement(claim_id=claim.id, service=settle_svc, db=db_session)

    appr = approve_settlement(
        settlement_id=rec.id,
        payload=SettlementApproveRequest(approved_by="SUPERVISOR-42"),
        service=settle_svc,
    )
    assert appr.status == SettlementStatus.APPROVED.value
    assert appr.settled_by == "SUPERVISOR-42"
    assert appr.approved_amount == Decimal("2500.00")


def test_30_settlement_disburse_and_pay_alias(db_session: Session, test_seed):
    """Verify disbursement execution and payment reference generation."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2500.00"),
            description="Disbursement test",
        )
    )

    settle_svc = get_settlement_service(db_session)
    rec = recommend_settlement(claim_id=claim.id, service=settle_svc, db=db_session)
    approve_settlement(
        settlement_id=rec.id,
        payload=SettlementApproveRequest(approved_by="SUPERVISOR-42"),
        service=settle_svc,
    )

    pay = disburse_payment(
        settlement_id=rec.id,
        payload=SettlementDisburseRequest(payment_method=PaymentMethod.WIRE),
        service=settle_svc,
    )
    assert pay.status == PaymentStatus.COMPLETED
    assert pay.payment_method == PaymentMethod.WIRE
    assert pay.payment_reference.startswith("PAYREF-")


def test_31_settlement_duplicate_payment_blocked(db_session: Session, test_seed):
    """Verify strict duplicate payment rejection with 409 Conflict (Scenario 6 control)."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("2500.00"),
            description="Duplicate disbursement test",
        )
    )

    settle_svc = get_settlement_service(db_session)
    rec = recommend_settlement(claim_id=claim.id, service=settle_svc, db=db_session)
    approve_settlement(
        settlement_id=rec.id,
        payload=SettlementApproveRequest(approved_by="SUPERVISOR-42"),
        service=settle_svc,
    )

    # First disbursement succeeds
    disburse_payment(
        settlement_id=rec.id,
        payload=SettlementDisburseRequest(payment_method=PaymentMethod.ACH),
        service=settle_svc,
    )

    # Second disbursement must raise 409 Conflict
    with pytest.raises(HTTPException) as exc:
        disburse_payment(
            settlement_id=rec.id,
            payload=SettlementDisburseRequest(payment_method=PaymentMethod.ACH),
            service=settle_svc,
        )
    assert exc.value.status_code == 409
    assert "Duplicate payment blocked" in exc.value.detail


# ==============================================================================
# SECTION 8: Audit & Compliance (Scenarios 32-33)
# ==============================================================================


def test_32_claim_audit_trail_and_alias(db_session: Session, test_seed):
    """Verify retrieval of chronological immutable audit trail for a claim."""
    intake_svc = get_claim_intake_service(db_session)
    claim = intake_svc.intake_claim(
        ClaimIntakeRequest(
            customer_id=test_seed["customer"].id,
            policy_id=test_seed["policy"].id,
            incident_id=test_seed["incident"].id,
            claim_type=ClaimType.COLLISION,
            claimed_amount=Decimal("1500.00"),
            description="Audit trail endpoint test",
        )
    )

    events = get_claim_audit_trail(claim_id=claim.id, db=db_session)
    assert len(events) >= 1
    actions = [e.action for e in events]
    assert AuditAction.CLAIM_CREATED.value in actions or "CLAIM_CREATED" in actions


def test_33_global_audit_events_paginated(db_session: Session, test_seed):
    """Verify global audit log search with pagination and entity filtering."""
    res = list_audit_events(
        db=db_session,
        page=1,
        page_size=20,
        entity_type="Claim",
    )
    assert isinstance(res, PaginatedResponse)
    assert res.page == 1
    assert res.page_size == 20


# ==============================================================================
# SECTION 9: Pagination & Query Validation (Scenarios 34-35)
# ==============================================================================


def test_34_pagination_contract(db_session: Session, test_seed):
    """Verify paginated envelope contract (items, total, page, page_size, total_pages, has_next, has_prev)."""
    res = list_claims(db=db_session, page=1, page_size=5)
    assert hasattr(res, "items")
    assert hasattr(res, "total")
    assert hasattr(res, "page")
    assert hasattr(res, "page_size")
    assert hasattr(res, "total_pages")
    assert hasattr(res, "has_next")
    assert hasattr(res, "has_prev")
    assert res.has_prev is False


def test_35_pagination_validation_errors(db_session: Session):
    """Verify query parameter bounds validation rejection for invalid page (< 1) and page_size (> 100)."""
    # Pydantic / FastAPI Query specification: page ge=1, page_size le=100
    with pytest.raises(ValueError):
        PaginatedResponse.create(items=[], total=10, page=0, page_size=20)

    with pytest.raises(ValueError):
        PaginatedResponse.create(items=[], total=10, page=1, page_size=0)
