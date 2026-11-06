"""Comprehensive unit tests covering all 26 required domain and workflow scenarios.

Uses an isolated in-memory SQLite database session.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.adjuster import Adjuster
from app.models.base import Base
from app.models.claim import Claim
from app.models.claim_item import ClaimItem
from app.models.coverage import Coverage
from app.models.customer import Customer
from app.models.document import Document
from app.models.enums import (
    AdjusterSpecialization,
    AdjusterStatus,
    AssessmentOutcome,
    ClaimStatus,
    ClaimType,
    CoverageType,
    DocumentRequestStatus,
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
from app.schemas.claim_schemas import ClaimIntakeRequest, ClaimItemCreate
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
from app.services.exceptions import (
    CustomerPolicyMismatchError,
    DuplicatePaymentError,
    SettlementLimitExceededError,
)


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
def base_fixture(db_session: Session):
    """Populate base domain records."""
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Customer
    cust = Customer(
        id="CUST-2026-000001",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1-555-0199",
        date_of_birth=date(1985, 4, 12),
    )
    db_session.add(cust)

    # 2. Policy
    pol = Policy(
        id="POL-AUTO-2026-000001",
        customer_id=cust.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2026, 12, 31),
        cancellation_date=None,
        total_premium=Decimal("1200.00"),
        deductible=Decimal("500.00"),
    )
    db_session.add(pol)

    # 3. Coverage
    cov = Coverage(
        id="COV-POL-AUTO-2026-000001-001",
        policy_id=pol.id,
        coverage_type=CoverageType.COLLISION,
        coverage_limit=Decimal("50000.00"),
        deductible=Decimal("500.00"),
        copay_percentage=Decimal("0.00"),
        exclusions=None,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2026, 12, 31),
        is_active=True,
    )
    db_session.add(cov)

    # 4. Incident
    inc = Incident(
        id="INC-2026-000001",
        incident_type="VEHICLE_COLLISION",
        occurrence_date=now - timedelta(days=5),
        description="Rear bumper impact at signal",
        location_street="100 Main St",
        location_city="Springfield",
        location_state="IL",
        location_zip="62701",
        police_report_filed=True,
        police_report_number="PD-IL-2026-00123",
    )
    db_session.add(inc)

    # 5. Adjusters
    adj_auto = Adjuster(
        id="ADJ-2026-000001",
        employee_id="EMP-2026-001",
        name="Alex Smith",
        email="alex.smith@claims.com",
        phone="+1-800-555-01",
        specialization=AdjusterSpecialization.AUTO,
        active_claims_count=1,
        max_capacity=20,
        status=AdjusterStatus.ACTIVE,
    )
    adj_general = Adjuster(
        id="ADJ-2026-000002",
        employee_id="EMP-2026-002",
        name="Sam Taylor",
        email="sam.taylor@claims.com",
        phone="+1-800-555-02",
        specialization=AdjusterSpecialization.GENERAL,
        active_claims_count=0,
        max_capacity=20,
        status=AdjusterStatus.ACTIVE,
    )
    db_session.add_all([adj_auto, adj_general])
    db_session.commit()

    return {
        "customer": cust,
        "policy": pol,
        "coverage": cov,
        "incident": inc,
        "adjuster_auto": adj_auto,
        "adjuster_general": adj_general,
    }


@pytest.fixture
def services(db_session: Session):
    """Instantiate domain services."""
    claim_repo = ClaimRepository(db_session)
    claim_item_repo = ClaimItemRepository(db_session)
    customer_repo = CustomerRepository(db_session)
    policy_repo = PolicyRepository(db_session)
    incident_repo = IncidentRepository(db_session)
    coverage_repo = CoverageRepository(db_session)
    doc_repo = DocumentRepository(db_session)
    doc_req_repo = DocumentRequestRepository(db_session)
    adj_repo = AdjusterRepository(db_session)
    asn_repo = AdjusterAssignmentRepository(db_session)
    reserve_repo = ReserveRepository(db_session)
    settle_repo = SettlementRepository(db_session)
    pay_repo = SettlementPaymentRepository(db_session)
    asm_repo = AssessmentRepository(db_session)
    audit_repo = AuditRepository(db_session)
    csh_repo = ClaimStatusHistoryRepository(db_session)

    policy_val_svc = PolicyValidationService(policy_repo, audit_repo)
    cov_svc = CoverageService(coverage_repo, audit_repo)
    doc_svc = DocumentService(doc_repo, doc_req_repo, audit_repo)
    dup_svc = DuplicateDetectionService(claim_repo, incident_repo)
    fraud_svc = FraudService(claim_repo)
    elig_svc = EligibilityService(asm_repo, audit_repo)
    adj_svc = AdjusterService(adj_repo, asn_repo, claim_repo, audit_repo)
    res_svc = ReserveService(reserve_repo, audit_repo)
    settle_svc = SettlementService(settle_repo, pay_repo, claim_repo, audit_repo)
    intake_svc = ClaimIntakeService(
        claim_repo, claim_item_repo, customer_repo, policy_repo, incident_repo, audit_repo, csh_repo
    )
    workflow_svc = ClaimsProcessingService(
        claim_repo=claim_repo,
        policy_repo=policy_repo,
        incident_repo=incident_repo,
        csh_repo=csh_repo,
        policy_validation_service=policy_val_svc,
        coverage_service=cov_svc,
        document_service=doc_svc,
        duplicate_service=dup_svc,
        fraud_service=fraud_svc,
        eligibility_service=elig_svc,
        adjuster_service=adj_svc,
        reserve_service=res_svc,
        settlement_service=settle_svc,
    )

    return {
        "intake": intake_svc,
        "policy_val": policy_val_svc,
        "coverage": cov_svc,
        "document": doc_svc,
        "duplicate": dup_svc,
        "fraud": fraud_svc,
        "eligibility": elig_svc,
        "adjuster": adj_svc,
        "reserve": res_svc,
        "settlement": settle_svc,
        "workflow": workflow_svc,
        "repos": {
            "claim": claim_repo,
            "doc": doc_repo,
            "doc_req": doc_req_repo,
            "policy": policy_repo,
            "coverage": coverage_repo,
            "incident": incident_repo,
            "audit": audit_repo,
            "settle": settle_repo,
            "pay": pay_repo,
            "asm": asm_repo,
        },
    }


class TestClaimsProcessingServices:
    # 1. Valid Active Policy
    def test_01_valid_active_policy(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000001",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("3500.00"),
            description="Front bumper damage",
        )
        res = services["policy_val"].validate_policy(claim, incident)
        assert res.is_valid is True
        assert len(res.failure_reasons) == 0

    # 2. Expired Policy
    def test_02_expired_policy(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        # Set incident after policy expiration
        incident.occurrence_date = datetime(2027, 2, 1, 10, 0, tzinfo=timezone.utc)
        claim = Claim(
            id="CLM-2026-000002",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime(2027, 2, 2, tzinfo=timezone.utc),
            claimed_amount=Decimal("2000.00"),
            description="Post expiration loss",
        )
        res = services["policy_val"].validate_policy(claim, incident)
        assert res.is_valid is False
        assert any("expired" in r.lower() or "expiration" in r.lower() for r in res.failure_reasons)

    # 3. Cancelled Policy
    def test_03_cancelled_policy(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        policy.status = PolicyStatus.CANCELLED
        policy.cancellation_date = date(2026, 3, 1)
        incident.occurrence_date = datetime(2026, 4, 15, tzinfo=timezone.utc)
        claim = Claim(
            id="CLM-2026-000003",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime(2026, 4, 16, tzinfo=timezone.utc),
            claimed_amount=Decimal("1500.00"),
            description="Post cancellation loss",
        )
        res = services["policy_val"].validate_policy(claim, incident)
        assert res.is_valid is False
        assert any("cancelled" in r.lower() for r in res.failure_reasons)

    # 4. Incident Before Policy Commencement
    def test_04_incident_before_policy_commencement(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        # Effective date is 2026-01-01; incident is 2025-12-15
        incident.occurrence_date = datetime(2025, 12, 15, tzinfo=timezone.utc)
        claim = Claim(
            id="CLM-2026-000004",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime(2026, 1, 2, tzinfo=timezone.utc),
            claimed_amount=Decimal("1500.00"),
            description="Pre inception loss",
        )
        res = services["policy_val"].validate_policy(claim, incident)
        assert res.is_valid is False
        assert any("commencement" in r.lower() or "before" in r.lower() for r in res.failure_reasons)

    # 5. Incident Outside Coverage
    def test_05_incident_outside_coverage(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        # Claim is MEDICAL, but policy only has COLLISION coverage
        claim = Claim(
            id="CLM-2026-000005",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.MEDICAL,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("4000.00"),
            description="Medical fees",
        )
        cov_res = services["coverage"].validate_coverage(claim, incident)
        assert cov_res.is_covered is False
        assert any("No active policy coverage found" in r for r in cov_res.failure_reasons)

    # 6. Excluded Incident
    def test_06_excluded_incident(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        coverage = base_fixture["coverage"]
        # Add COLLISION to exclusions list
        coverage.exclusions = ["COLLISION", "RACING"]
        services["repos"]["coverage"].update(coverage)

        claim = Claim(
            id="CLM-2026-000006",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("2500.00"),
            description="Racing collision",
        )
        cov_res = services["coverage"].validate_coverage(claim, incident)
        assert cov_res.is_covered is False
        assert any("exclusion" in r.lower() for r in cov_res.failure_reasons)

    # 7. Claim Within Coverage Limit
    def test_07_claim_within_coverage_limit(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000007",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("15000.00"),  # limit is 50,000
            description="Within limit collision",
        )
        cov_res = services["coverage"].validate_coverage(claim, incident)
        assert cov_res.is_covered is True
        rule_4 = next(r for r in cov_res.rule_results if r.rule_id == "COVERAGE_004")
        assert rule_4.passed is True

    # 8. Claim Exceeding Coverage Limit
    def test_08_claim_exceeding_coverage_limit(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000008",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("75000.00"),  # limit is 50,000
            description="Massive structural total loss",
        )
        cov_res = services["coverage"].validate_coverage(claim, incident)
        # Note: COVERAGE_004 flags that claim exceeds limit
        rule_4 = next(r for r in cov_res.rule_results if r.rule_id == "COVERAGE_004")
        assert rule_4.passed is False

    # 9. All Mandatory Documents Submitted & Verified
    def test_09_all_mandatory_documents_submitted(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000009",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("3000.00"),
            description="Complete evidence claim",
        )
        services["repos"]["claim"].create(claim)

        # Attach all 3 mandatory COLLISION docs
        now = datetime.now(timezone.utc)
        d1 = Document(
            id="DOC-CLM-2026-000009-001",
            claim_id=claim.id,
            document_type=DocumentType.POLICE_REPORT,
            file_name="police.pdf",
            file_type="application/pdf",
            file_path="/docs/police.pdf",
            file_size_bytes=1000,
            checksum_sha256="a" * 64,
            submission_date=now,
            verification_status=VerificationStatus.VERIFIED,
        )
        d2 = Document(
            id="DOC-CLM-2026-000009-002",
            claim_id=claim.id,
            document_type=DocumentType.REPAIR_ESTIMATE,
            file_name="repair.pdf",
            file_type="application/pdf",
            file_path="/docs/repair.pdf",
            file_size_bytes=2000,
            checksum_sha256="b" * 64,
            submission_date=now,
            verification_status=VerificationStatus.VERIFIED,
        )
        d3 = Document(
            id="DOC-CLM-2026-000009-003",
            claim_id=claim.id,
            document_type=DocumentType.DAMAGE_PHOTO,
            file_name="photo.jpg",
            file_type="image/jpeg",
            file_path="/docs/photo.jpg",
            file_size_bytes=3000,
            checksum_sha256="c" * 64,
            submission_date=now,
            verification_status=VerificationStatus.VERIFIED,
        )
        services["repos"]["doc"].create(d1)
        services["repos"]["doc"].create(d2)
        services["repos"]["doc"].create(d3)

        doc_res = services["document"].verify_claim_documents(claim)
        assert doc_res.is_complete is True
        assert len(doc_res.missing_document_types) == 0
        assert len(doc_res.created_document_requests) == 0

    # 10. Missing Mandatory Documents
    def test_10_missing_mandatory_documents(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000010",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("3000.00"),
            description="Incomplete evidence claim",
        )
        services["repos"]["claim"].create(claim)

        # Only 1 document provided
        d1 = Document(
            id="DOC-CLM-2026-000010-001",
            claim_id=claim.id,
            document_type=DocumentType.POLICE_REPORT,
            file_name="police.pdf",
            file_type="application/pdf",
            file_path="/docs/police.pdf",
            file_size_bytes=1000,
            checksum_sha256="a" * 64,
            submission_date=datetime.now(timezone.utc),
            verification_status=VerificationStatus.VERIFIED,
        )
        services["repos"]["doc"].create(d1)

        doc_res = services["document"].verify_claim_documents(claim)
        assert doc_res.is_complete is False
        assert DocumentType.REPAIR_ESTIMATE in doc_res.missing_document_types
        assert DocumentType.DAMAGE_PHOTO in doc_res.missing_document_types
        # DocumentRequests must have been emitted!
        assert len(doc_res.created_document_requests) == 2

    # 11. Rejected Documents
    def test_11_rejected_documents(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000011",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("3000.00"),
            description="Rejected document claim",
        )
        services["repos"]["claim"].create(claim)

        d1 = Document(
            id="DOC-CLM-2026-000011-001",
            claim_id=claim.id,
            document_type=DocumentType.POLICE_REPORT,
            file_name="police.pdf",
            file_type="application/pdf",
            file_path="/docs/police.pdf",
            file_size_bytes=1000,
            checksum_sha256="a" * 64,
            submission_date=datetime.now(timezone.utc),
            verification_status=VerificationStatus.REJECTED,
            rejection_reason="Unreadable scan",
        )
        services["repos"]["doc"].create(d1)

        doc_res = services["document"].verify_claim_documents(claim)
        assert doc_res.is_complete is False
        assert DocumentType.POLICE_REPORT in doc_res.unverified_document_types

    # 12. Duplicate Claim Detection
    def test_12_duplicate_claim(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        c1 = Claim(
            id="CLM-2026-000012",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("2500.00"),
            description="First claim",
        )
        services["repos"]["claim"].create(c1)

        c2 = Claim(
            id="CLM-2026-000013",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("2500.00"),
            description="Duplicate claim submission",
        )
        services["repos"]["claim"].create(c2)

        dup_res = services["duplicate"].check_duplicates(c2, incident)
        assert dup_res.has_duplicates is True
        assert any(r.rule_id == "DUPLICATE_001" and not r.passed for r in dup_res.rule_results)

    # 13. Duplicate Incident Detection
    def test_13_duplicate_incident(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        c1 = Claim(
            id="CLM-2026-000014",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("2000.00"),
            description="First incident claim",
        )
        services["repos"]["claim"].create(c1)

        # Second claim with different amount on same incident
        c2 = Claim(
            id="CLM-2026-000015",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("4500.00"),
            description="Different claim on same incident",
        )
        services["repos"]["claim"].create(c2)

        dup_res = services["duplicate"].check_duplicates(c2, incident)
        assert dup_res.has_duplicates is True
        assert any(r.rule_id == "DUPLICATE_002" and not r.passed for r in dup_res.rule_results)

    # 14. Fraud Indicator Detection
    def test_14_fraud_indicator_detection(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000016",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=45),  # > 30 days
            claimed_amount=Decimal("150000.00"),  # > 200% of 50k
            description="Massive delayed claim",
        )
        fraud_res = services["fraud"].evaluate_claim_fraud(
            claim=claim,
            policy=policy,
            coverage_limit=Decimal("50000.00"),
        )
        assert fraud_res.is_fraudulent_or_quarantined is True
        types = {i.indicator_type for i in fraud_res.indicators}
        assert "EXCESSIVE_CLAIM_AMOUNT" in types

    # 15. Adjuster Specialization Matching
    def test_15_adjuster_specialization_matching(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000017",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,  # Targets AUTO
            status=ClaimStatus.ELIGIBLE,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("2000.00"),
            description="Auto claim",
        )
        services["repos"]["claim"].create(claim)

        assignment = services["adjuster"].assign_adjuster(claim)
        assert assignment.adjuster_id == "ADJ-2026-000001"  # Auto adjuster

    # 16. Adjuster Least-Loaded Selection
    def test_16_adjuster_workload_selection(self, base_fixture, services):
        # Create two adjusters with same specialization, one loaded
        db = services["repos"]["claim"].session
        adj1 = Adjuster(
            id="ADJ-2026-000010",
            employee_id="EMP-2026-010",
            name="Adjuster Ten",
            email="ten@claims.com",
            phone="+1-800-10",
            specialization=AdjusterSpecialization.PROPERTY,
            active_claims_count=5,
            max_capacity=20,
            status=AdjusterStatus.ACTIVE,
        )
        adj2 = Adjuster(
            id="ADJ-2026-000011",
            employee_id="EMP-2026-011",
            name="Adjuster Eleven",
            email="eleven@claims.com",
            phone="+1-800-11",
            specialization=AdjusterSpecialization.PROPERTY,
            active_claims_count=1,
            max_capacity=20,
            status=AdjusterStatus.ACTIVE,
        )
        db.add_all([adj1, adj2])
        db.commit()

        claim = Claim(
            id="CLM-2026-000018",
            customer_id=base_fixture["customer"].id,
            policy_id=base_fixture["policy"].id,
            incident_id=base_fixture["incident"].id,
            claim_type=ClaimType.PROPERTY_DAMAGE,
            status=ClaimStatus.ELIGIBLE,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("3000.00"),
            description="Property claim",
        )
        services["repos"]["claim"].create(claim)

        assignment = services["adjuster"].assign_adjuster(claim)
        assert assignment.adjuster_id == "ADJ-2026-000011"  # least loaded (1 vs 5)
        # Verify caseload incremented
        reloaded = services["repos"]["claim"].session.get(Adjuster, "ADJ-2026-000011")
        assert reloaded.active_claims_count == 2

    # 17. Reserve Arithmetic
    def test_17_reserve_arithmetic(self, base_fixture, services):
        coverage = base_fixture["coverage"]
        claim = Claim(
            id="CLM-2026-000019",
            customer_id=base_fixture["customer"].id,
            policy_id=base_fixture["policy"].id,
            incident_id=base_fixture["incident"].id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.UNDER_REVIEW,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("10000.00"),
            estimated_loss=Decimal("10000.00"),
            description="Collision damage",
        )
        services["repos"]["claim"].create(claim)

        # Coverage: limit 50,000, deductible 500
        # Covered loss = 10,000
        # Indemnity reserve = 10,000 - 500 = 9,500
        # Expense reserve = 9,500 * 0.12 = 1,140
        # Total reserve = 10,640
        reserve = services["reserve"].calculate_claim_reserve(claim, coverage)
        assert reserve.estimated_indemnity_reserve == Decimal("9500.00")
        assert reserve.estimated_expense_reserve == Decimal("1140.00")
        assert reserve.total_reserve == Decimal("10640.00")

    # 18. Settlement Arithmetic
    def test_18_settlement_arithmetic(self, base_fixture, services):
        coverage = base_fixture["coverage"]
        claim = Claim(
            id="CLM-2026-000020",
            customer_id=base_fixture["customer"].id,
            policy_id=base_fixture["policy"].id,
            incident_id=base_fixture["incident"].id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.ELIGIBLE,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("8000.00"),
            estimated_loss=Decimal("8000.00"),
            description="Collision settlement",
        )
        services["repos"]["claim"].create(claim)

        # Allowable = 8,000, deductible = 500, copay = 0
        # Net = 7,500
        settlement = services["settlement"].recommend_settlement(claim, coverage)
        assert settlement.recommended_amount == Decimal("8000.00")
        assert settlement.deductible_applied == Decimal("500.00")
        assert settlement.net_settlement_amount == Decimal("7500.00")
        assert settlement.status == SettlementStatus.PROPOSED

    # 19. Settlement Limit Enforcement (Scenario 4)
    def test_19_settlement_limit_enforcement(self, base_fixture, services):
        coverage = base_fixture["coverage"]
        claim = Claim(
            id="CLM-2026-000021",
            customer_id=base_fixture["customer"].id,
            policy_id=base_fixture["policy"].id,
            incident_id=base_fixture["incident"].id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.ELIGIBLE,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("80000.00"),
            estimated_loss=Decimal("80000.00"),
            description="Exceeds limit claim",
        )
        services["repos"]["claim"].create(claim)

        # Test control for Scenario 4: uncapped settlement blocked
        with pytest.raises(SettlementLimitExceededError):
            services["settlement"].recommend_settlement(claim, coverage, force_exceed_limit_for_test=True)

    # 20. Duplicate Payment Prevention (Scenario 6)
    def test_20_duplicate_payment_prevention(self, base_fixture, services):
        coverage = base_fixture["coverage"]
        claim = Claim(
            id="CLM-2026-000022",
            customer_id=base_fixture["customer"].id,
            policy_id=base_fixture["policy"].id,
            incident_id=base_fixture["incident"].id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.ELIGIBLE,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("5000.00"),
            estimated_loss=Decimal("5000.00"),
            description="Settlement payment test",
        )
        services["repos"]["claim"].create(claim)

        settlement = services["settlement"].recommend_settlement(claim, coverage)
        services["settlement"].approve_settlement(settlement.id, approved_by="SUPERVISOR_1")

        # First disbursement succeeds
        pay1 = services["settlement"].disburse_payment(settlement.id, payment_method=PaymentMethod.ACH)
        assert pay1.status == PaymentStatus.COMPLETED

        # Second disbursement must be blocked (Scenario 6)
        with pytest.raises(DuplicatePaymentError):
            services["settlement"].disburse_payment(settlement.id, payment_method=PaymentMethod.ACH)

    # 21. Audit Event Persistence
    def test_21_audit_event_persistence(self, base_fixture, services):
        audit_repo = services["repos"]["audit"]
        initial_count = audit_repo.count()

        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000023",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime.now(timezone.utc),
            claimed_amount=Decimal("1200.00"),
            description="Audit test claim",
        )
        services["policy_val"].validate_policy(claim, incident)
        assert audit_repo.count() > initial_count

    # 22. Reassessment History Preservation
    def test_22_reassessment_history_preservation(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000024",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("2000.00"),
            description="Reassessment test",
        )
        services["repos"]["claim"].create(claim)

        # First processing pass (missing docs -> PENDING_DOCUMENTS)
        res1 = services["workflow"].process_claim(claim.id)
        assert res1.outcome == AssessmentOutcome.PENDING_DOCUMENTS

        # Upload missing documents
        now = datetime.now(timezone.utc)
        for seq, dt in enumerate([DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO], 1):
            d = Document(
                id=f"DOC-{claim.id}-{seq:03d}",
                claim_id=claim.id,
                document_type=dt,
                file_name=f"{dt.value.lower()}.pdf",
                file_type="application/pdf",
                file_path=f"/docs/{dt.value.lower()}.pdf",
                file_size_bytes=1000,
                checksum_sha256="d" * 64,
                submission_date=now,
                verification_status=VerificationStatus.VERIFIED,
            )
            services["repos"]["doc"].create(d)

        # Second processing pass (reassessment)
        res2 = services["workflow"].reassess_claim(claim.id)
        assert res2.outcome == AssessmentOutcome.ELIGIBLE

        # Verify BOTH assessment records are preserved in history (ordered desc by default)
        history = services["repos"]["asm"].get_by_claim_id(claim.id)
        assert len(history) == 2
        # Latest assessment is eligible, prior assessment was ineligible / pending docs
        assert history[0].is_eligible is True
        assert history[1].is_eligible is False

    # 23. Complete Eligible Claim Workflow
    def test_23_complete_eligible_claim_workflow(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000025",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("4500.00"),
            estimated_loss=Decimal("4500.00"),
            description="End-to-end eligible collision claim",
        )
        services["repos"]["claim"].create(claim)

        # Attach all mandatory documents
        now = datetime.now(timezone.utc)
        for seq, dt in enumerate([DocumentType.POLICE_REPORT, DocumentType.REPAIR_ESTIMATE, DocumentType.DAMAGE_PHOTO], 1):
            d = Document(
                id=f"DOC-{claim.id}-{seq:03d}",
                claim_id=claim.id,
                document_type=dt,
                file_name=f"{dt.value.lower()}.pdf",
                file_type="application/pdf",
                file_path=f"/docs/{dt.value.lower()}.pdf",
                file_size_bytes=1000,
                checksum_sha256="e" * 64,
                submission_date=now,
                verification_status=VerificationStatus.VERIFIED,
            )
            services["repos"]["doc"].create(d)

        res = services["workflow"].process_claim(claim.id)
        assert res.outcome == AssessmentOutcome.ELIGIBLE
        assert res.is_eligible is True
        assert res.assigned_adjuster_id is not None
        assert res.reserve_id is not None
        assert res.total_reserve > Decimal("0.00")
        assert res.settlement_id is not None
        assert res.net_settlement_amount == Decimal("4000.00")  # 4500 - 500 deductible

    # 24. Complete Pending-Document Workflow
    def test_24_complete_pending_document_workflow(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        claim = Claim(
            id="CLM-2026-000026",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("4500.00"),
            description="Pending documents test",
        )
        services["repos"]["claim"].create(claim)

        res = services["workflow"].process_claim(claim.id)
        assert res.outcome == AssessmentOutcome.PENDING_DOCUMENTS
        assert res.is_eligible is False
        assert res.status == ClaimStatus.INFO_REQUESTED
        # Verify DocumentRequests were generated
        open_reqs = services["repos"]["doc_req"].get_open_by_claim_id(claim.id)
        assert len(open_reqs) == 3

    # 25. Complete Manual-Review Workflow
    def test_25_complete_manual_review_workflow(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        # Create an existing claim to trigger duplicate
        c_orig = Claim(
            id="CLM-2026-000027",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=1),
            claimed_amount=Decimal("5000.00"),
            description="Original loss",
        )
        services["repos"]["claim"].create(c_orig)

        # Duplicate claim
        c_dup = Claim(
            id="CLM-2026-000028",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=incident.occurrence_date + timedelta(days=2),
            claimed_amount=Decimal("5000.00"),
            description="Duplicate claim triggering SIU",
        )
        services["repos"]["claim"].create(c_dup)

        res = services["workflow"].process_claim(c_dup.id)
        assert res.outcome == AssessmentOutcome.MANUAL_REVIEW
        assert res.status == ClaimStatus.FLAGGED
        assert res.assigned_adjuster_id is not None  # Assigned for investigation

    # 26. Ineligible Claim Workflow
    def test_26_ineligible_claim_workflow(self, base_fixture, services):
        policy = base_fixture["policy"]
        incident = base_fixture["incident"]
        # Policy is cancelled prior to incident
        policy.status = PolicyStatus.CANCELLED
        policy.cancellation_date = date(2026, 2, 1)
        incident.occurrence_date = datetime(2026, 5, 1, tzinfo=timezone.utc)
        services["repos"]["policy"].update(policy)

        claim = Claim(
            id="CLM-2026-000029",
            customer_id=policy.customer_id,
            policy_id=policy.id,
            incident_id=incident.id,
            claim_type=ClaimType.COLLISION,
            status=ClaimStatus.SUBMITTED,
            reported_date=datetime(2026, 5, 2, tzinfo=timezone.utc),
            claimed_amount=Decimal("3000.00"),
            description="Ineligible cancelled policy claim",
        )
        services["repos"]["claim"].create(claim)

        res = services["workflow"].process_claim(claim.id)
        assert res.outcome == AssessmentOutcome.INELIGIBLE
        assert res.is_eligible is False
        assert res.status == ClaimStatus.REJECTED
        assert res.rejection_code == "EXPIRED_POLICY"
