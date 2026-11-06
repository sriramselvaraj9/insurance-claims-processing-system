"""Anomaly injector orchestrating the 6 mandatory negative scenarios and ground truth tracking."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import random

from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import (
    ClaimStatus,
    ClaimType,
    CoverageType,
    ExceptionSeverity,
    PolicyStatus,
    RejectionCode,
)
from app.models.incident import Incident
from app.models.policy import Policy
from scripts.generation_config import GenerationConfig


@dataclass
class GroundTruthRecord:
    entity_id: str
    issue_type: str
    expected_decision: str
    expected_anomaly_label: str  # "ANOMALOUS" or "CLEAN"
    reason: str
    severity: str
    relevant_rule_id: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AnomalyInjectionPlan:
    pre_effective_claim_ids: set[str]
    post_cancel_claim_ids: set[str]
    uncovered_peril_claim_ids: set[str]
    untimely_filing_claim_ids: set[str]
    missing_doc_claim_ids: set[str]
    excessive_amount_claim_ids: set[str]
    exceeds_limit_claim_ids: set[str]
    duplicate_claim_ids: set[str]
    duplicate_incident_claim_ids: set[str]
    double_payment_claim_ids: set[str]
    ground_truth_records: list[GroundTruthRecord]


def plan_and_inject_anomalies(
    config: GenerationConfig,
    claims: list[Claim],
    policies: list[Policy],
    coverages: list[Coverage],
    incidents: list[Incident],
    seed: int,
) -> AnomalyInjectionPlan:
    """Select target claims for each anomaly scenario and modify records while logging ground truth."""
    rng = random.Random(seed + 500)
    
    policies_by_id = {p.id: p for p in policies}
    incidents_by_id = {inc.id: inc for inc in incidents}
    coverages_by_policy = {}
    for cov in coverages:
        coverages_by_policy.setdefault(cov.policy_id, []).append(cov)

    claim_indices = list(range(len(claims)))
    rng.shuffle(claim_indices)

    cursor = 0

    def take_claims(count: int) -> list[Claim]:
        nonlocal cursor
        selected = [claims[idx] for idx in claim_indices[cursor : cursor + count]]
        cursor += count
        return selected

    gt_records: list[GroundTruthRecord] = []

    # 1. NEG-01: Claim / Incident date before policy effective date
    pre_effective_claims = take_claims(config.neg_01_pre_effective_count)
    pre_effective_ids = {c.id for c in pre_effective_claims}
    for c in pre_effective_claims:
        pol = policies_by_id[c.policy_id]
        inc = incidents_by_id[c.incident_id]
        # Shift incident date to 15 days before policy effective date
        new_inc_date = datetime(
            pol.effective_date.year,
            pol.effective_date.month,
            pol.effective_date.day,
            12, 0, 0, tzinfo=timezone.utc,
        ) - timedelta(days=15)
        inc.occurrence_date = new_inc_date
        c.reported_date = new_inc_date + timedelta(days=2)
        c.status = ClaimStatus.REJECTED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="DATE_BEFORE_POLICY_START",
                expected_decision="DENIED",
                expected_anomaly_label="ANOMALOUS",
                reason=f"Incident date ({new_inc_date.date()}) occurred prior to policy inception ({pol.effective_date})",
                severity=ExceptionSeverity.HIGH.value,
                relevant_rule_id="R-ELIG-001",
            )
        )

    # 2. NEG-01: Policy cancelled before incident
    post_cancel_claims = take_claims(config.neg_01_post_cancel_count)
    post_cancel_ids = {c.id for c in post_cancel_claims}
    for c in post_cancel_claims:
        pol = policies_by_id[c.policy_id]
        inc = incidents_by_id[c.incident_id]
        # Set policy to CANCELLED 20 days prior to incident
        cancel_date = inc.occurrence_date.date() - timedelta(days=20)
        pol.status = PolicyStatus.CANCELLED
        pol.cancellation_date = cancel_date
        c.status = ClaimStatus.REJECTED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="POLICY_CANCELLED_BEFORE_INCIDENT",
                expected_decision="DENIED",
                expected_anomaly_label="ANOMALOUS",
                reason=f"Policy cancelled on {cancel_date} prior to incident on {inc.occurrence_date.date()}",
                severity=ExceptionSeverity.HIGH.value,
                relevant_rule_id="R-ELIG-001",
            )
        )

    # 3. NEG-02: Uncovered peril
    uncovered_claims = take_claims(config.neg_02_uncovered_peril_count)
    uncovered_ids = {c.id for c in uncovered_claims}
    for c in uncovered_claims:
        # Strip matching coverages from this policy so claim peril is uncovered
        policy_covs = coverages_by_policy.get(c.policy_id, [])
        for cov in policy_covs:
            # Change coverage type to TRIP_INTERRUPTION or something irrelevant
            cov.coverage_type = CoverageType.TRIP_INTERRUPTION
        c.status = ClaimStatus.REJECTED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="UNCOVERED_PERIL",
                expected_decision="DENIED",
                expected_anomaly_label="ANOMALOUS",
                reason=f"Peril '{c.claim_type.value}' is not covered under active policy coverages",
                severity=ExceptionSeverity.HIGH.value,
                relevant_rule_id="R-ELIG-002",
            )
        )

    # 4. NEG-03: Untimely filing
    untimely_claims = take_claims(config.neg_03_untimely_filing_count)
    untimely_ids = {c.id for c in untimely_claims}
    for c in untimely_claims:
        inc = incidents_by_id[c.incident_id]
        # Set reported date 65 days after incident (> 30 statutory window)
        c.reported_date = inc.occurrence_date + timedelta(days=65)
        c.status = ClaimStatus.REJECTED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="UNTIMELY_FILING",
                expected_decision="DENIED",
                expected_anomaly_label="ANOMALOUS",
                reason="Claim submitted 65 days post-incident, exceeding statutory window of 30 days",
                severity=ExceptionSeverity.MEDIUM.value,
                relevant_rule_id="R-ELIG-003",
            )
        )

    # 5. NEG-04: Missing mandatory document
    missing_doc_claims = take_claims(config.neg_04_missing_document_count)
    missing_doc_ids = {c.id for c in missing_doc_claims}
    for c in missing_doc_claims:
        c.status = ClaimStatus.INFO_REQUESTED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="MISSING_MANDATORY_DOCUMENT",
                expected_decision="REQUEST_INFO",
                expected_anomaly_label="ANOMALOUS",
                reason=f"Claim type '{c.claim_type.value}' lacks mandatory evidentiary verification document",
                severity=ExceptionSeverity.MEDIUM.value,
                relevant_rule_id="R-DOC-001",
            )
        )

    # 6. NEG-05: Excessive claim amount (> 200% coverage limit)
    excessive_claims = take_claims(config.neg_05_excessive_amount_count)
    excessive_ids = {c.id for c in excessive_claims}
    for c in excessive_claims:
        policy_covs = coverages_by_policy.get(c.policy_id, [])
        max_limit = max((cov.coverage_limit for cov in policy_covs), default=Decimal("50000.00"))
        c.claimed_amount = (max_limit * Decimal("2.5")).quantize(Decimal("0.01"))
        c.estimated_loss = c.claimed_amount
        c.status = ClaimStatus.FLAGGED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="EXCESSIVE_CLAIM_AMOUNT",
                expected_decision="INVESTIGATION",
                expected_anomaly_label="ANOMALOUS",
                reason=f"Claimed amount (${c.claimed_amount}) exceeds 250% of policy coverage limit (${max_limit})",
                severity=ExceptionSeverity.HIGH.value,
                relevant_rule_id="R-FRAUD-003",
            )
        )

    # 7. NEG-05: Settlement exceeding coverage limit
    exceeds_limit_claims = take_claims(config.neg_05_exceeds_coverage_limit_count)
    exceeds_limit_ids = {c.id for c in exceeds_limit_claims}
    for c in exceeds_limit_claims:
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="SETTLEMENT_EXCEEDS_COVERAGE_LIMIT",
                expected_decision="REJECTED",
                expected_anomaly_label="ANOMALOUS",
                reason="Calculated net settlement exceeds allowable policy coverage ceiling",
                severity=ExceptionSeverity.CRITICAL.value,
                relevant_rule_id="R-FIN-003",
            )
        )

    # 8. NEG-06: Duplicate claim within 7 days
    duplicate_claims = take_claims(config.neg_06_duplicate_claim_count)
    duplicate_ids = {c.id for c in duplicate_claims}
    for c in duplicate_claims:
        c.status = ClaimStatus.FLAGGED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="DUPLICATE_CLAIM",
                expected_decision="FLAGGED",
                expected_anomaly_label="ANOMALOUS",
                reason="Duplicate claim filing detected for identical customer, policy, and loss within 7 days",
                severity=ExceptionSeverity.CRITICAL.value,
                relevant_rule_id="R-FRAUD-001",
            )
        )

    # 9. NEG-06: Duplicate incident
    dup_incident_claims = take_claims(config.neg_06_duplicate_incident_count)
    dup_incident_ids = {c.id for c in dup_incident_claims}
    for c in dup_incident_claims:
        c.status = ClaimStatus.FLAGGED
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="DUPLICATE_INCIDENT",
                expected_decision="FLAGGED",
                expected_anomaly_label="ANOMALOUS",
                reason="Identical loss event details duplicated across multiple policy claims",
                severity=ExceptionSeverity.HIGH.value,
                relevant_rule_id="R-FRAUD-002",
            )
        )

    # 10. NEG-06: Claim paid twice (Double payment)
    double_payment_claims = take_claims(config.neg_06_double_payment_count)
    double_payment_ids = {c.id for c in double_payment_claims}
    for c in double_payment_claims:
        gt_records.append(
            GroundTruthRecord(
                entity_id=c.id,
                issue_type="CLAIM_PAID_TWICE",
                expected_decision="FLAGGED",
                expected_anomaly_label="ANOMALOUS",
                reason="Multiple disbursement settlement payments executed against single approved claim",
                severity=ExceptionSeverity.CRITICAL.value,
                relevant_rule_id="R-SETTLE-003",
            )
        )

    return AnomalyInjectionPlan(
        pre_effective_claim_ids=pre_effective_ids,
        post_cancel_claim_ids=post_cancel_ids,
        uncovered_peril_claim_ids=uncovered_ids,
        untimely_filing_claim_ids=untimely_ids,
        missing_doc_claim_ids=missing_doc_ids,
        excessive_amount_claim_ids=excessive_ids,
        exceeds_limit_claim_ids=exceeds_limit_ids,
        duplicate_claim_ids=duplicate_ids,
        duplicate_incident_claim_ids=dup_incident_ids,
        double_payment_claim_ids=double_payment_ids,
        ground_truth_records=gt_records,
    )

