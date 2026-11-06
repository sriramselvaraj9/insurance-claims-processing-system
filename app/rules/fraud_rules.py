"""Fraud detection and anomalous claim submission rules."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.models.enums import ExceptionSeverity, PolicyStatus, RejectionCode

SEVERITY_RANK = {
    ExceptionSeverity.LOW: 1,
    ExceptionSeverity.MEDIUM: 2,
    ExceptionSeverity.HIGH: 3,
    ExceptionSeverity.CRITICAL: 4,
}


@dataclass(frozen=True)
class FraudAssessment:
    is_fraudulent_or_quarantined: bool
    rejection_code: RejectionCode | None
    severity: ExceptionSeverity
    flags: list[str]


def assess_fraud_risk(
    policy_status: PolicyStatus,
    claimed_amount: Decimal,
    coverage_limit: Decimal,
    existing_claims_in_window: int = 0,
    is_duplicate_claim: bool = False,
    is_duplicate_incident: bool = False,
) -> FraudAssessment:
    """Assess claim for suspicious fraud patterns, duplicate filings, and anomalies."""
    flags: list[str] = []
    severity = ExceptionSeverity.LOW
    rejection_code: RejectionCode | None = None
    is_quarantined = False

    if is_duplicate_claim:
        is_quarantined = True
        flags.append("Identical duplicate claim filed for same policy and incident")
        severity = ExceptionSeverity.CRITICAL
        rejection_code = RejectionCode.DUPLICATE_CLAIM

    if is_duplicate_incident:
        is_quarantined = True
        flags.append("Incident details duplicate existing reported loss event")
        severity = ExceptionSeverity.HIGH
        rejection_code = rejection_code or RejectionCode.SUSPECTED_FRAUD

    if policy_status == PolicyStatus.SUSPENDED:
        is_quarantined = True
        flags.append("Claim filed under suspended policy (non-payment / compliance hold)")
        severity = ExceptionSeverity.HIGH
        rejection_code = rejection_code or RejectionCode.SUSPENDED_POLICY

    if existing_claims_in_window >= 3:
        flags.append(f"High frequency filing velocity: {existing_claims_in_window} claims within 30 days")
        severity = max(severity, ExceptionSeverity.MEDIUM, key=lambda s: SEVERITY_RANK[s])

    if claimed_amount > (coverage_limit * Decimal("2.0")):
        flags.append(f"Excessive claim amount exceeds 200% of policy coverage limit (${claimed_amount} vs ${coverage_limit})")
        severity = max(severity, ExceptionSeverity.HIGH, key=lambda s: SEVERITY_RANK[s])

    return FraudAssessment(
        is_fraudulent_or_quarantined=is_quarantined,
        rejection_code=rejection_code,
        severity=severity,
        flags=flags,
    )
