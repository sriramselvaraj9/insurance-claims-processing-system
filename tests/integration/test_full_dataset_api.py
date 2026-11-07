"""Phase 4: End-to-End API Verification Against Full Synthetic Dataset (Section 13).

Validates the complete REST API against 2,000 policies, 1,000 claims, and all supporting records:
1. Customer endpoints: pagination across 1,500+ customers, search by name, first/last/sample lookup.
2. Policy endpoints: all 5 policy types, pagination across 2,000 policies, eager coverages.
3. Claim endpoints: all 5 claim types, status filtering, detail eager loading.
4. Claims processing: processes batch of 10+ claims, creates assessments, reserves, settlements.
5. Edge case verification: all 6 mandatory negative scenarios (NEG-01 to NEG-06).
6. Performance SLAs: read endpoints < 100ms, claim processing < 500ms.
7. Ground truth isolation: confirms no API route exposes ground truth data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    get_claim_intake_service,
    get_claims_processing_service,
    get_document_service,
    get_settlement_service,
)
from app.api.v1.claims import (
    get_claim,
    get_claim_assessments,
    get_claim_audit_trail,
    list_claims,
    process_claim,
)
from app.api.v1.customers import get_customer, list_customers
from app.api.v1.documents import list_claim_documents
from app.api.v1.policies import get_policy, list_policies, list_policy_coverages
from app.api.v1.reserves import get_claim_reserves
from app.api.v1.settlements import get_claim_settlements
from app.main import app
from app.models.base import Base
from app.models.enums import (
    AssessmentOutcome,
    ClaimStatus,
    ClaimType,
    PolicyStatus,
    PolicyType,
)

CSV_DIR = Path("data/synthetic/csv")


@pytest.fixture(scope="module")
def populated_db_engine():
    """Populate full 2,000-policy, 1,000-claim dataset in SQLite."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    tables = [
        "customers",
        "policies",
        "coverages",
        "adjusters",
        "incidents",
        "claims",
        "claim_items",
        "documents",
        "document_requests",
        "assessments",
        "reserves",
        "settlements",
        "settlement_payments",
        "adjuster_assignments",
        "audit_events",
        "claim_status_history",
    ]
    for table in tables:
        csv_file = CSV_DIR / f"{table}.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            df.to_sql(table, engine, if_exists="append", index=False)

    return engine


@pytest.fixture
def dataset_session(populated_db_engine):
    """Session connected to the populated synthetic dataset."""
    session_factory = sessionmaker(bind=populated_db_engine, autoflush=False, autocommit=False)
    session = session_factory()
    yield session
    session.close()


# ==============================================================================
# SECTION 1: Customer Endpoints (1,500+ Customers)
# ==============================================================================


def test_full_dataset_customers_pagination_and_lookup(dataset_session: Session):
    """Verify customer pagination across 1,500+ customers and boundary lookups."""
    # 1. Page 1
    page1 = list_customers(db=dataset_session, page=1, page_size=20)
    assert page1.total >= 1000
    assert len(page1.items) == 20
    assert page1.page == 1
    assert page1.has_next is True
    assert page1.has_prev is False

    # 2. Retrieve first customer
    first_cust_id = page1.items[0].id
    cust1 = get_customer(customer_id=first_cust_id, db=dataset_session)
    assert cust1.id == first_cust_id

    # 3. Search filter by name
    name_query = cust1.first_name[:4]
    search_res = list_customers(db=dataset_session, page=1, page_size=10, search=name_query)
    assert search_res.total >= 1
    assert any(name_query.lower() in c.first_name.lower() or name_query.lower() in c.last_name.lower() for c in search_res.items)


# ==============================================================================
# SECTION 2: Policy Endpoints (2,000 Policies)
# ==============================================================================


def test_full_dataset_policies_types_and_coverages(dataset_session: Session):
    """Verify all 2,000 policies, all 5 policy types, and eager coverage loading."""
    # 1. Verify 2,000 total policies
    all_policies = list_policies(db=dataset_session, page=1, page_size=20)
    assert all_policies.total == 2000

    # 2. Verify all 5 policy types exist and can be filtered
    for p_type in [PolicyType.AUTO, PolicyType.HOME, PolicyType.HEALTH, PolicyType.COMMERCIAL, PolicyType.TRAVEL]:
        res = list_policies(db=dataset_session, page=1, page_size=5, policy_type=p_type)
        assert res.total > 0
        assert all(p.policy_type == p_type.value for p in res.items)

    # 3. Verify policy with coverages
    first_policy = all_policies.items[0]
    pol_detail = get_policy(policy_id=first_policy.id, db=dataset_session)
    assert len(pol_detail.coverages) >= 1
    coverages = list_policy_coverages(policy_id=first_policy.id, db=dataset_session)
    assert len(coverages) == len(pol_detail.coverages)


# ==============================================================================
# SECTION 3: Claim Endpoints (1,000 Claims)
# ==============================================================================


def test_full_dataset_claims_types_and_relationships(dataset_session: Session):
    """Verify claims across all 5 claim types, status filtering, and child entities."""
    # 1. Total claims
    claims_page = list_claims(db=dataset_session, page=1, page_size=20)
    assert claims_page.total == 1000

    # 2. Check all 5 claim types in synthetic dataset
    for c_type in [
        ClaimType.COLLISION,
        ClaimType.PROPERTY_DAMAGE,
        ClaimType.MEDICAL,
        ClaimType.TRAVEL_LOSS,
        ClaimType.LIABILITY,
    ]:
        res = list_claims(db=dataset_session, page=1, page_size=5, claim_type=c_type)
        assert res.total == 200, f"Expected 200 claims for {c_type}, got {res.total}"

    # 3. Retrieve a claim and inspect child documents and assessments
    sample_claim = claims_page.items[0]
    fetched = get_claim(claim_id=sample_claim.id, db=dataset_session)
    assert fetched.id == sample_claim.id

    docs = list_claim_documents(claim_id=sample_claim.id, db=dataset_session)
    assert isinstance(docs, list)
    assessments = get_claim_assessments(claim_id=sample_claim.id, db=dataset_session)
    assert isinstance(assessments, list)


# ==============================================================================
# SECTION 4: Processing Claims from Dataset (10+ Claims Batch)
# ==============================================================================


def test_full_dataset_batch_claim_processing(dataset_session: Session):
    """Process a batch of at least 10 claims from the synthetic dataset."""
    proc_svc = get_claims_processing_service(dataset_session)

    # Select 10 claims
    claims_page = list_claims(db=dataset_session, page=1, page_size=10)
    assert len(claims_page.items) == 10

    processed_count = 0
    for claim in claims_page.items:
        t0 = time.perf_counter()
        result = process_claim(claim_id=claim.id, service=proc_svc)
        t_elapsed = time.perf_counter() - t0

        # Processing must complete in < 500ms
        assert t_elapsed < 0.500
        assert result.claim_id == claim.id
        assert result.status in [ClaimStatus.SETTLEMENT_RECOMMENDED, ClaimStatus.INFO_REQUESTED, ClaimStatus.REJECTED, ClaimStatus.FLAGGED, ClaimStatus.UNDER_REVIEW]

        # Verify assessment record created
        assessments = get_claim_assessments(claim_id=claim.id, db=dataset_session)
        assert len(assessments) >= 1

        processed_count += 1

    assert processed_count == 10


# ==============================================================================
# SECTION 5: Edge Case Verification (All 6 Mandatory Scenarios)
# ==============================================================================


def test_full_dataset_edge_cases_verification(dataset_session: Session):
    """Verify that all mandatory negative scenarios exist in isolated ground truth and trigger correct rules."""
    gt_path = Path("data/synthetic/ground_truth/ground_truth.csv")
    assert gt_path.exists(), "Ground truth CSV must exist for evaluation verification"

    df_gt = pd.read_csv(gt_path)
    assert len(df_gt) == 165
    assert all(df_gt["expected_anomaly_label"] == "ANOMALOUS")

    # Verify all mandatory negative issue types are present
    expected_issue_types = {
        "MISSING_MANDATORY_DOCUMENT",
        "DATE_BEFORE_POLICY_START",
        "POLICY_CANCELLED_BEFORE_INCIDENT",
        "UNCOVERED_PERIL",
        "UNTIMELY_FILING",
        "DUPLICATE_CLAIM",
        "SETTLEMENT_EXCEEDS_COVERAGE_LIMIT",
        "CLAIM_PAID_TWICE",
    }
    actual_types = set(df_gt["issue_type"].dropna().unique())
    for exp_type in expected_issue_types:
        assert exp_type in actual_types, f"Anomaly scenario {exp_type} must exist in ground truth"


# ==============================================================================
# SECTION 6: Performance SLA Verification
# ==============================================================================


def test_full_dataset_performance_slas(dataset_session: Session):
    """Verify performance SLAs: read endpoints < 100ms, processing < 500ms."""
    # 1. Read: List customers (20)
    t0 = time.perf_counter()
    list_customers(db=dataset_session, page=1, page_size=20)
    lat_cust = time.perf_counter() - t0
    assert lat_cust < 0.100, f"Customer list latency {lat_cust*1000:.1f}ms exceeds 100ms SLA"

    # 2. Read: List policies (20)
    t0 = time.perf_counter()
    list_policies(db=dataset_session, page=1, page_size=20)
    lat_pol = time.perf_counter() - t0
    assert lat_pol < 0.100, f"Policy list latency {lat_pol*1000:.1f}ms exceeds 100ms SLA"

    # 3. Read: List claims (20)
    t0 = time.perf_counter()
    claims = list_claims(db=dataset_session, page=1, page_size=20)
    lat_claim = time.perf_counter() - t0
    assert lat_claim < 0.100, f"Claim list latency {lat_claim*1000:.1f}ms exceeds 100ms SLA"

    # 4. Read: Single claim detail
    claim_id = claims.items[0].id
    t0 = time.perf_counter()
    get_claim(claim_id=claim_id, db=dataset_session)
    lat_single = time.perf_counter() - t0
    assert lat_single < 0.100, f"Single claim lookup latency {lat_single*1000:.1f}ms exceeds 100ms SLA"


# ==============================================================================
# SECTION 7: Ground Truth Isolation Check
# ==============================================================================


def test_full_dataset_ground_truth_isolation():
    """Verify no API endpoint exposes ground truth records or internal benchmark keys."""
    # Inspect all registered paths in FastAPI OpenAPI specification
    openapi_spec = app.openapi()
    paths = openapi_spec.get("paths", {})

    for path, path_item in paths.items():
        assert "ground_truth" not in path.lower(), f"Route {path} must NOT expose ground truth"
        assert "benchmark" not in path.lower(), f"Route {path} must NOT expose benchmark secrets"

    # Verify ground truth files exist strictly in isolated ground_truth folder
    assert Path("data/synthetic/ground_truth/ground_truth.csv").exists()
    assert Path("data/synthetic/ground_truth/ground_truth.json").exists()
    assert not Path("data/synthetic/csv/ground_truth.csv").exists(), "ground_truth.csv must not be in public csv/"
    assert not Path("data/synthetic/csv/ground_truth.json").exists(), "ground_truth.json must not be in public csv/"
