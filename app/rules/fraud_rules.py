"""Deterministic fraud detection indicators and risk rules (FRAUD_001 to FRAUD_005).

A fraud indicator is an alert triggering MANUAL_REVIEW for human investigation,
not proof of fraud.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from app.models.enums import ExceptionSeverity, PolicyStatus, RejectionCode
from app.rules.rule_base import RuleResult

SEVERITY_RANK = {
    ExceptionSeverity.LOW: 1,
    ExceptionSeverity.MEDIUM: 2,
    ExceptionSeverity.HIGH: 3,
    ExceptionSeverity.CRITICAL: 4,
}


@dataclass(frozen=True)
class FraudIndicator:
    indicator_id: str
    claim_id: str
    indicator_type: str
    severity: ExceptionSeverity
    explanation: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "claim_id": self.claim_id,
            "indicator_type": self.indicator_type,
            "severity": self.severity.value,
            "explanation": self.explanation,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class FraudAssessment:
    is_fraudulent_or_quarantined: bool
    rejection_code: RejectionCode | None
    severity: ExceptionSeverity
    flags: list[str]
    indicators: list[FraudIndicator]
    rule_results: list[RuleResult]


def evaluate_fraud_indicators(
    policy_status: PolicyStatus,
    claimed_amount: Decimal,
    coverage_limit: Decimal,
    claim_id: str = "CLM-TEST-000001",
    filing_lag_days: int = 0,
    claims_in_past_30d: int = 0,
    is_duplicate_claim: bool = False,
    is_duplicate_incident: bool = False,
) -> FraudAssessment:
    """Evaluate deterministic fraud indicators and return structured findings."""
    indicators: list[FraudIndicator] = []
    rule_results: list[RuleResult] = []
    flags: list[str] = []
    rejection_code: RejectionCode | None = None
    max_severity = ExceptionSeverity.LOW
    is_quarantined = False

    # FRAUD_001 — Excessive claim amount (> 200% coverage limit)
    limit_ratio = (claimed_amount / coverage_limit) if coverage_limit > Decimal("0.00") else Decimal("999.00")
    is_excessive = limit_ratio > Decimal("2.00")
    if is_excessive:
        is_quarantined = True
        flags.append(f"Claimed amount (${claimed_amount}) exceeds 200% of policy coverage limit (${coverage_limit})")
        max_severity = max(max_severity, ExceptionSeverity.HIGH, key=lambda s: SEVERITY_RANK[s])
        indicators.append(
            FraudIndicator(
                indicator_id=f"IND-{claim_id}-001",
                claim_id=claim_id,
                indicator_type="EXCESSIVE_CLAIM_AMOUNT",
                severity=ExceptionSeverity.HIGH,
                explanation=f"Claimed amount is {limit_ratio:.1f}x the applicable coverage ceiling",
                evidence={"claimed_amount": str(claimed_amount), "coverage_limit": str(coverage_limit)},
            )
        )

    rule_results.append(
        RuleResult(
            rule_id="FRAUD_001",
            name="Claim vs Limit Ratio",
            passed=not is_excessive,
            reason=(
                f"Claimed amount is within acceptable ratio of coverage limit ({limit_ratio:.1f}x)"
                if not is_excessive
                else f"Claimed amount is {limit_ratio:.1f}x coverage limit (exceeds 2.0x threshold)"
            ),
            entity_id=claim_id,
            metadata={"ratio": float(limit_ratio)},
        )
    )

    # FRAUD_002 — High filing velocity (>= 3 claims in past 30 days)
    is_high_velocity = claims_in_past_30d >= 3
    if is_high_velocity:
        flags.append(f"High filing velocity detected: {claims_in_past_30d} claims submitted in past 30 days")
        max_severity = max(max_severity, ExceptionSeverity.MEDIUM, key=lambda s: SEVERITY_RANK[s])
        indicators.append(
            FraudIndicator(
                indicator_id=f"IND-{claim_id}-002",
                claim_id=claim_id,
                indicator_type="HIGH_FILING_VELOCITY",
                severity=ExceptionSeverity.MEDIUM,
                explanation=f"Customer or policy has {claims_in_past_30d} recent claims within 30 days",
                evidence={"claims_in_30d": claims_in_past_30d},
            )
        )

    rule_results.append(
        RuleResult(
            rule_id="FRAUD_002",
            name="Filing Velocity Threshold",
            passed=not is_high_velocity,
            reason=(
                f"Recent claim velocity is normal ({claims_in_past_30d} claims in 30 days)"
                if not is_high_velocity
                else f"Elevated frequency: {claims_in_past_30d} claims in 30 days (threshold >= 3)"
            ),
            entity_id=claim_id,
            metadata={"claims_in_30d": claims_in_past_30d},
        )
    )

    # FRAUD_003 — Late reporting lag (> 30 days post-incident)
    is_late_notice = filing_lag_days > 30
    if is_late_notice:
        flags.append(f"Delayed reporting: claim submitted {filing_lag_days} days post-incident")
        max_severity = max(max_severity, ExceptionSeverity.MEDIUM, key=lambda s: SEVERITY_RANK[s])
        indicators.append(
            FraudIndicator(
                indicator_id=f"IND-{claim_id}-003",
                claim_id=claim_id,
                indicator_type="UNTIMELY_REPORTING_LAG",
                severity=ExceptionSeverity.MEDIUM,
                explanation=f"Reporting delay of {filing_lag_days} days exceeds statutory 30-day notice window",
                evidence={"filing_lag_days": filing_lag_days},
            )
        )

    rule_results.append(
        RuleResult(
            rule_id="FRAUD_003",
            name="Timely Notice Window",
            passed=not is_late_notice,
            reason=(
                f"Claim reported within standard notice window ({filing_lag_days} days post-incident)"
                if not is_late_notice
                else f"Notice delayed by {filing_lag_days} days (statutory maximum is 30 days)"
            ),
            entity_id=claim_id,
            metadata={"filing_lag_days": filing_lag_days},
        )
    )

    # FRAUD_004 — Claim under Suspended Policy
    is_suspended = (policy_status == PolicyStatus.SUSPENDED)
    if is_suspended:
        is_quarantined = True
        flags.append("Claim submitted against suspended policy (compliance hold / premium default)")
        max_severity = max(max_severity, ExceptionSeverity.HIGH, key=lambda s: SEVERITY_RANK[s])
        rejection_code = rejection_code or RejectionCode.SUSPENDED_POLICY
        indicators.append(
            FraudIndicator(
                indicator_id=f"IND-{claim_id}-004",
                claim_id=claim_id,
                indicator_type="SUSPENDED_POLICY_SUBMISSION",
                severity=ExceptionSeverity.HIGH,
                explanation="Policy status is SUSPENDED at intake",
                evidence={"policy_status": policy_status.value},
            )
        )

    rule_results.append(
        RuleResult(
            rule_id="FRAUD_004",
            name="Policy Compliance Status",
            passed=not is_suspended,
            reason=(
                "Policy is in good compliance standing"
                if not is_suspended
                else "Policy is SUSPENDED due to administrative or non-payment hold"
            ),
            entity_id=claim_id,
            metadata={"status": policy_status.value},
        )
    )

    # FRAUD_005 — Duplicate filing indicator
    if is_duplicate_claim or is_duplicate_incident:
        is_quarantined = True
        dup_type = "DUPLICATE_CLAIM" if is_duplicate_claim else "DUPLICATE_INCIDENT"
        flags.append(f"Suspected duplicate submission: {dup_type}")
        max_severity = max(max_severity, ExceptionSeverity.CRITICAL, key=lambda s: SEVERITY_RANK[s])
        rejection_code = rejection_code or (
            RejectionCode.DUPLICATE_CLAIM if is_duplicate_claim else RejectionCode.SUSPECTED_FRAUD
        )
        indicators.append(
            FraudIndicator(
                indicator_id=f"IND-{claim_id}-005",
                claim_id=claim_id,
                indicator_type="DUPLICATE_SUBMISSION_FLAG",
                severity=ExceptionSeverity.CRITICAL,
                explanation=f"Duplicate submission pattern confirmed ({dup_type})",
                evidence={"is_duplicate_claim": is_duplicate_claim, "is_duplicate_incident": is_duplicate_incident},
            )
        )

    rule_results.append(
        RuleResult(
            rule_id="FRAUD_005",
            name="Duplicate Pattern Check",
            passed=not (is_duplicate_claim or is_duplicate_incident),
            reason=(
                "No duplicate filing patterns detected"
                if not (is_duplicate_claim or is_duplicate_incident)
                else "Duplicate claim or incident pattern detected"
            ),
            entity_id=claim_id,
            metadata={"is_duplicate_claim": is_duplicate_claim, "is_duplicate_incident": is_duplicate_incident},
        )
    )

    return FraudAssessment(
        is_fraudulent_or_quarantined=is_quarantined,
        rejection_code=rejection_code,
        severity=max_severity,
        flags=flags,
        indicators=indicators,
        rule_results=rule_results,
    )


# Backwards compatibility alias for existing Phase 2 tests
assess_fraud_risk = evaluate_fraud_indicators
