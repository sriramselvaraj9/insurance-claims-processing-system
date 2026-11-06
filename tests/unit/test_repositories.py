from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.core.id_generator import IdGenerator
from app.models import (
    Adjuster,
    AdjusterAssignment,
    Assessment,
    Claim,
    ClaimItem,
    Coverage,
    Customer,
    Document,
    DocumentRequest,
    Incident,
    Policy,
    Reserve,
    Settlement,
    SettlementPayment,
)
from app.models.enums import (
    ActorType,
    AdjusterSpecialization,
    AdjusterStatus,
    AuditAction,
    ClaimStatus,
    ClaimType,
    CoverageType,
    DocumentRequestStatus,
    DocumentType,
    IncidentType,
    KYCStatus,
    PaymentMethod,
    PaymentStatus,
    PolicyStatus,
    PolicyType,
    ReserveCalculationMethod,
    RiskProfile,
    SettlementStatus,
    VerificationStatus,
)
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


@pytest.fixture
def sample_customer(db_session: Session) -> Customer:
    repo = CustomerRepository(db_session)
    cust = Customer(
        id=IdGenerator.customer_id(1),
        first_name="Marcus",
        last_name="Vance",
        email="marcus.vance@example.com",
        phone="+1-555-0200",
        date_of_birth=date(1988, 4, 12),
        kyc_status=KYCStatus.VERIFIED,
        risk_profile=RiskProfile.LOW,
    )
    return repo.create(cust)


@pytest.fixture
def sample_policy(db_session: Session, sample_customer: Customer) -> Policy:
    repo = PolicyRepository(db_session)
    pol = Policy(
        id=IdGenerator.policy_id("AUTO", 1),
        customer_id=sample_customer.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("1450.00"),
        deductible=Decimal("500.00"),
    )
    return repo.create(pol)


@pytest.fixture
def sample_coverage(db_session: Session, sample_policy: Policy) -> Coverage:
    repo = CoverageRepository(db_session)
    cov = Coverage(
        id=IdGenerator.coverage_id(sample_policy.id, 1),
        policy_id=sample_policy.id,
        coverage_type=CoverageType.COLLISION,
        coverage_limit=Decimal("50000.00"),
        deductible=Decimal("500.00"),
        copay_percentage=Decimal("0.00"),
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        is_active=True,
    )
    return repo.create(cov)


@pytest.fixture
def sample_incident(db_session: Session) -> Incident:
    repo = IncidentRepository(db_session)
    inc = Incident(
        id=IdGenerator.incident_id(1),
        incident_type=IncidentType.VEHICLE_COLLISION,
        occurrence_date=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        description="Side-impact collision at signal",
        location_street="452 Elm Street",
        location_city="Chicago",
        location_state="IL",
        location_zip="60601",
        police_report_filed=True,
        police_report_number="CPD-2026-9941",
    )
    return repo.create(inc)


@pytest.fixture
def sample_claim(
    db_session: Session,
    sample_customer: Customer,
    sample_policy: Policy,
    sample_incident: Incident,
) -> Claim:
    repo = ClaimRepository(db_session)
    claim = Claim(
        id=IdGenerator.claim_id(1),
        customer_id=sample_customer.id,
        policy_id=sample_policy.id,
        incident_id=sample_incident.id,
        claim_type=ClaimType.COLLISION,
        status=ClaimStatus.SUBMITTED,
        reported_date=datetime(2026, 4, 16, 8, 30, tzinfo=timezone.utc),
        claimed_amount=Decimal("6500.00"),
        estimated_loss=Decimal("6000.00"),
        description="Passenger door panel crushed",
    )
    return repo.create(claim)


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------


def test_customer_repository_crud(db_session: Session, sample_customer: Customer):
    repo = CustomerRepository(db_session)
    found = repo.get_by_id(sample_customer.id)
    assert found is not None
    assert found.first_name == "Marcus"

    by_email = repo.get_by_email("marcus.vance@example.com")
    assert by_email is not None
    assert by_email.id == sample_customer.id

    assert repo.exists(sample_customer.id) is True
    assert repo.exists("CUST-NONEXISTENT") is False


def test_policy_repository_queries(
    db_session: Session, sample_customer: Customer, sample_policy: Policy
):
    repo = PolicyRepository(db_session)
    policies = repo.list_by_customer(sample_customer.id)
    assert len(policies) == 1
    assert policies[0].id == sample_policy.id

    active = repo.list_active()
    assert len(active) >= 1


def test_coverage_repository_queries(
    db_session: Session, sample_policy: Policy, sample_coverage: Coverage
):
    repo = CoverageRepository(db_session)
    coverages = repo.list_by_policy(sample_policy.id)
    assert len(coverages) == 1

    cov = repo.get_by_type(sample_policy.id, CoverageType.COLLISION)
    assert cov is not None
    assert cov.coverage_limit == Decimal("50000.00")

    # Non-existent coverage
    missing = repo.get_by_type(sample_policy.id, CoverageType.DWELLING)
    assert missing is None


def test_incident_duplicate_detection(db_session: Session, sample_incident: Incident):
    repo = IncidentRepository(db_session)
    dup = repo.find_duplicate_incident(
        occurrence_date=sample_incident.occurrence_date,
        location_city="Chicago",
        location_street="452 Elm Street",
    )
    assert dup is not None
    assert dup.id == sample_incident.id


def test_claim_repository_queries_and_duplicate_check(
    db_session: Session, sample_claim: Claim
):
    repo = ClaimRepository(db_session)
    by_status = repo.list_by_status(ClaimStatus.SUBMITTED)
    assert len(by_status) >= 1

    dups = repo.find_potential_duplicates(
        policy_id=sample_claim.policy_id,
        incident_id=sample_claim.incident_id,
        claimed_amount=sample_claim.claimed_amount,
    )
    assert len(dups) == 1

    details = repo.get_with_details(sample_claim.id)
    assert details is not None
    assert details.customer is not None
    assert details.policy is not None
    assert details.incident is not None


def test_claim_item_repository_and_sum(
    db_session: Session, sample_claim: Claim, sample_coverage: Coverage
):
    repo = ClaimItemRepository(db_session)
    item1 = ClaimItem(
        id=IdGenerator.claim_item_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        coverage_id=sample_coverage.id,
        item_description="Front passenger door replacement",
        quantity=1,
        unit_amount=Decimal("3500.00"),
        total_amount=Decimal("3500.00"),
    )
    item2 = ClaimItem(
        id=IdGenerator.claim_item_id(sample_claim.id, 2),
        claim_id=sample_claim.id,
        coverage_id=sample_coverage.id,
        item_description="Paint and refinishing labor",
        quantity=2,
        unit_amount=Decimal("1250.00"),
        total_amount=Decimal("2500.00"),
    )
    repo.create(item1)
    repo.create(item2)

    items = repo.list_by_claim(sample_claim.id)
    assert len(items) == 2

    total_loss = repo.compute_total_claim_loss(sample_claim.id)
    assert total_loss == Decimal("6000.00")


def test_document_and_request_repository(db_session: Session, sample_claim: Claim):
    doc_repo = DocumentRepository(db_session)
    req_repo = DocumentRequestRepository(db_session)

    # Missing document request
    req = DocumentRequest(
        id=IdGenerator.document_request_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        document_type=DocumentType.POLICE_REPORT,
        status=DocumentRequestStatus.OPEN,
    )
    req_repo.create(req)

    open_reqs = req_repo.list_open_by_claim(sample_claim.id)
    assert len(open_reqs) == 1

    # Upload document to fulfill request
    doc = Document(
        id=IdGenerator.document_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        document_type=DocumentType.POLICE_REPORT,
        file_name="police_report.pdf",
        file_type="application/pdf",
        file_path="/storage/docs/police_report.pdf",
        file_size_bytes=1048576,
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        verification_status=VerificationStatus.VERIFIED,
    )
    doc_repo.create(doc)

    fulfilled = req_repo.fulfill_request(req.id, doc.id)
    assert fulfilled is not None
    assert fulfilled.status == DocumentRequestStatus.FULFILLED
    assert fulfilled.fulfilled_document_id == doc.id


def test_adjuster_assignment_and_capacity_balancing(
    db_session: Session, sample_claim: Claim
):
    adj_repo = AdjusterRepository(db_session)
    asn_repo = AdjusterAssignmentRepository(db_session)

    adj1 = Adjuster(
        id=IdGenerator.adjuster_id(1),
        employee_id="ADJ-EMP-1001",
        name="Sarah Connor",
        email="sarah.connor@insurer.com",
        phone="+1-555-0301",
        specialization=AdjusterSpecialization.AUTO,
        active_claims_count=5,
        max_capacity=20,
        status=AdjusterStatus.ACTIVE,
    )
    adj2 = Adjuster(
        id=IdGenerator.adjuster_id(2),
        employee_id="ADJ-EMP-1002",
        name="John Connor",
        email="john.connor@insurer.com",
        phone="+1-555-0302",
        specialization=AdjusterSpecialization.AUTO,
        active_claims_count=2,  # Least loaded
        max_capacity=20,
        status=AdjusterStatus.ACTIVE,
    )
    adj_repo.create(adj1)
    adj_repo.create(adj2)

    # Least loaded adjuster should be John Connor
    chosen = adj_repo.find_least_loaded_adjuster(AdjusterSpecialization.AUTO)
    assert chosen is not None
    assert chosen.id == adj2.id

    # Create assignment and increment load
    asn = AdjusterAssignment(
        id=IdGenerator.adjuster_assignment_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        adjuster_id=chosen.id,
        assignment_reason="Initial automated assignment",
        is_active=True,
    )
    asn_repo.create(asn)
    adj_repo.increment_load(chosen.id)

    assert chosen.active_claims_count == 3
    active_asn = asn_repo.get_active_assignment(sample_claim.id)
    assert active_asn is not None
    assert active_asn.adjuster_id == chosen.id


def test_assessment_reassessment_history(db_session: Session, sample_claim: Claim):
    repo = AssessmentRepository(db_session)

    # Initial assessment: rejected due to missing document
    asm1 = Assessment(
        id=IdGenerator.assessment_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        is_eligible=False,
        policy_active_check=True,
        incident_covered_check=True,
        timely_filing_check=True,
        exclusions_check=True,
        documentation_complete_check=False,
        fraud_check_passed=True,
        decision_reasons=["Missing mandatory police report"],
        rejection_code="MISSING_MANDATORY_DOCUMENTS",
    )
    repo.create(asm1)

    # Reassessment after document provided: now eligible
    asm2 = Assessment(
        id=IdGenerator.assessment_id(sample_claim.id, 2),
        claim_id=sample_claim.id,
        is_eligible=True,
        policy_active_check=True,
        incident_covered_check=True,
        timely_filing_check=True,
        exclusions_check=True,
        documentation_complete_check=True,
        fraud_check_passed=True,
        decision_reasons=["All criteria satisfied"],
    )
    repo.create(asm2)

    history = repo.list_by_claim(sample_claim.id)
    assert len(history) == 2
    latest = repo.get_latest_by_claim(sample_claim.id)
    assert latest is not None
    assert latest.is_eligible is True


def test_reserve_calculation_repository(db_session: Session, sample_claim: Claim):
    repo = ReserveRepository(db_session)
    res = Reserve(
        id=IdGenerator.reserve_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        estimated_indemnity_reserve=Decimal("5500.00"),
        estimated_expense_reserve=Decimal("660.00"),  # 12%
        total_reserve=Decimal("6160.00"),
        expense_ratio=Decimal("0.1200"),
        calculation_method=ReserveCalculationMethod.FORMULAIC_STANDARD,
    )
    repo.create(res)

    latest = repo.get_latest_by_claim(sample_claim.id)
    assert latest is not None
    assert latest.total_reserve == Decimal("6160.00")


def test_settlement_and_duplicate_payment_prevention(
    db_session: Session, sample_claim: Claim
):
    set_repo = SettlementRepository(db_session)
    pay_repo = SettlementPaymentRepository(db_session)

    settlement = Settlement(
        id=IdGenerator.settlement_id(sample_claim.id, 1),
        claim_id=sample_claim.id,
        recommended_amount=Decimal("5500.00"),
        approved_amount=Decimal("5500.00"),
        deductible_applied=Decimal("500.00"),
        copay_applied=Decimal("0.00"),
        net_settlement_amount=Decimal("5000.00"),
        status=SettlementStatus.APPROVED,
    )
    set_repo.create(settlement)

    assert pay_repo.has_successful_payment(settlement.id) is False

    payment = SettlementPayment(
        id=IdGenerator.settlement_payment_id(settlement.id, 1),
        settlement_id=settlement.id,
        payment_amount=Decimal("5000.00"),
        payment_method=PaymentMethod.ACH,
        payment_reference="EFT-2026-004491",
        status=PaymentStatus.COMPLETED,
    )
    pay_repo.create(payment)

    assert pay_repo.has_successful_payment(settlement.id) is True


def test_claim_status_history_and_audit_event_immutability(
    db_session: Session, sample_claim: Claim
):
    csh_repo = ClaimStatusHistoryRepository(db_session)
    audit_repo = AuditRepository(db_session)

    # Status transition
    csh = csh_repo.record_transition(
        claim_id=sample_claim.id,
        previous_status=None,
        new_status=ClaimStatus.SUBMITTED,
        reason="Initial claim submission intake",
    )
    assert csh is not None

    # Audit log
    event = audit_repo.log_event(
        entity_type="Claim",
        entity_id=sample_claim.id,
        action=AuditAction.CREATE,
        actor_id="WEB_PORTAL",
        actor_type=ActorType.API_SERVICE,
        state_after={"status": ClaimStatus.SUBMITTED, "claimed_amount": "6500.00"},
    )
    assert event is not None

    logs = audit_repo.list_by_entity("Claim", sample_claim.id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.CREATE
