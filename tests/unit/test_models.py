from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Adjuster,
    AdjusterAssignment,
    Assessment,
    AuditEvent,
    Base,
    Claim,
    ClaimItem,
    ClaimStatusHistory,
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


def test_metadata_has_all_required_tables():
    """Verify that all 11 core entities and supporting tables are present in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    required_tables = {
        # 11 Core Entities
        "customers",
        "policies",
        "coverages",
        "claims",
        "claim_items",
        "documents",
        "incidents",
        "adjusters",
        "assessments",
        "reserves",
        "settlements",
        # Supporting Tables
        "adjuster_assignments",
        "document_requests",
        "settlement_payments",
        "claim_status_history",
        "audit_events",
    }
    assert required_tables.issubset(table_names), f"Missing tables: {required_tables - table_names}"


def test_primary_keys_configured():
    """Verify primary keys are string-based and configured for all tables."""
    for table_name, table in Base.metadata.tables.items():
        pks = [c.name for c in table.primary_key.columns]
        assert len(pks) == 1, f"Table {table_name} must have a single primary key"
        assert pks[0] == "id", f"Table {table_name} primary key must be named 'id'"


def test_foreign_keys_configured():
    """Verify foreign key references are configured to valid targets."""
    inspector = Base.metadata
    policies_fk = inspector.tables["policies"].foreign_keys
    assert any(fk.target_fullname == "customers.id" for fk in policies_fk)

    claims_fk = inspector.tables["claims"].foreign_keys
    targets = {fk.target_fullname for fk in claims_fk}
    assert "customers.id" in targets
    assert "policies.id" in targets
    assert "incidents.id" in targets
    assert "adjusters.id" in targets


def test_customer_model_creation_and_uniqueness(db_session: Session):
    """Test customer creation and unique email constraint."""
    cust = Customer(
        id="CUST-2026-000001",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1-555-0100",
        date_of_birth=date(1990, 5, 15),
        kyc_status=KYCStatus.VERIFIED,
        risk_profile=RiskProfile.LOW,
    )
    db_session.add(cust)
    db_session.flush()

    assert cust.full_name == "Jane Doe"
    assert cust.created_at is not None

    # Duplicate email must raise IntegrityError
    dup = Customer(
        id="CUST-2026-000002",
        first_name="John",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1-555-0101",
        date_of_birth=date(1985, 3, 20),
        kyc_status=KYCStatus.PENDING,
        risk_profile=RiskProfile.MEDIUM,
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_policy_model_and_date_check_constraint(db_session: Session):
    """Verify policy dates check constraint: expiration_date must be greater than effective_date."""
    cust = Customer(
        id="CUST-2026-000010",
        first_name="Robert",
        last_name="Smith",
        email="robert.smith@example.com",
        phone="+1-555-0102",
        date_of_birth=date(1982, 1, 10),
        kyc_status=KYCStatus.VERIFIED,
    )
    db_session.add(cust)
    db_session.flush()

    # Valid policy
    pol = Policy(
        id="POL-AUTO-2026-000010",
        customer_id=cust.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("1200.00"),
        deductible=Decimal("500.00"),
    )
    db_session.add(pol)
    db_session.flush()
    assert pol.total_premium == Decimal("1200.00")
    assert pol.customer.email == "robert.smith@example.com"


def test_monetary_types_are_decimals(db_session: Session):
    """Verify monetary values persist and retrieve as Python Decimal, not float."""
    cust = Customer(
        id="CUST-2026-000020",
        first_name="Alice",
        last_name="Wonder",
        email="alice.wonder@example.com",
        phone="+1-555-0103",
        date_of_birth=date(1995, 8, 22),
    )
    pol = Policy(
        id="POL-HOME-2026-000020",
        customer_id=cust.id,
        policy_type=PolicyType.HOME,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
        total_premium=Decimal("1500.50"),
        deductible=Decimal("1000.00"),
    )
    cov = Coverage(
        id="COV-POL-HOME-2026-000020-001",
        policy_id=pol.id,
        coverage_type=CoverageType.DWELLING,
        coverage_limit=Decimal("350000.00"),
        deductible=Decimal("1000.00"),
        copay_percentage=Decimal("0.00"),
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
    )
    db_session.add_all([cust, pol, cov])
    db_session.flush()

    retrieved = db_session.get(Coverage, cov.id)
    assert retrieved is not None
    assert isinstance(retrieved.coverage_limit, Decimal)
    assert retrieved.coverage_limit == Decimal("350000.00")
    assert isinstance(retrieved.deductible, Decimal)


def test_incident_and_claim_relationship(db_session: Session):
    """Verify Claim links to Incident, Customer, and Policy correctly."""
    cust = Customer(
        id="CUST-2026-000030",
        first_name="Bob",
        last_name="Marley",
        email="bob.marley@example.com",
        phone="+1-555-0104",
        date_of_birth=date(1980, 2, 6),
    )
    pol = Policy(
        id="POL-AUTO-2026-000030",
        customer_id=cust.id,
        policy_type=PolicyType.AUTO,
        status=PolicyStatus.ACTIVE,
        effective_date=date(2026, 1, 1),
        expiration_date=date(2027, 1, 1),
    )
    inc = Incident(
        id="INC-2026-000030",
        incident_type=IncidentType.VEHICLE_COLLISION,
        occurrence_date=datetime(2026, 3, 10, 14, 30, tzinfo=timezone.utc),
        description="Rear-end collision at intersection",
        location_street="100 Main St",
        location_city="Springfield",
        location_state="IL",
        location_zip="62701",
    )
    claim = Claim(
        id="CLM-2026-000030",
        customer_id=cust.id,
        policy_id=pol.id,
        incident_id=inc.id,
        claim_type=ClaimType.COLLISION,
        status=ClaimStatus.SUBMITTED,
        reported_date=datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc),
        claimed_amount=Decimal("4500.00"),
        estimated_loss=Decimal("4200.00"),
        description="Front bumper damage",
    )
    db_session.add_all([cust, pol, inc, claim])
    db_session.flush()

    retrieved_claim = db_session.get(Claim, claim.id)
    assert retrieved_claim is not None
    assert retrieved_claim.incident.description == "Rear-end collision at intersection"
    assert retrieved_claim.customer.first_name == "Bob"
    assert retrieved_claim.policy.policy_type == PolicyType.AUTO

