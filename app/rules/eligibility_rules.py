"""Deterministic eligibility assessment rules covering the 6 mandatory negative scenarios."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from app.models.enums import (
    ClaimType,
    CoverageType,
    DocumentType,
    PolicyStatus,
    RejectionCode,
    VerificationStatus,
)
from app.rules.document_rules import check_document_completeness


@dataclass(frozen=True)
class EligibilityDecision:
    is_eligible: bool
    policy_active_check: bool
    incident_covered_check: bool
    timely_filing_check: bool
    exclusions_check: bool
    documentation_complete_check: bool
    fraud_check_passed: bool
    decision_reasons: list[str]
    rejection_code: RejectionCode | None


def evaluate_eligibility(
    policy_status: PolicyStatus,
    policy_effective_date: date,
    policy_expiration_date: date,
    policy_cancellation_date: date | None,
    incident_date: datetime,
    reported_date: datetime,
    claim_type: ClaimType,
    available_coverages: Sequence[tuple[CoverageType, bool, list[str] | None]],  # (type, is_active, exclusions)
    provided_documents: Sequence[tuple[DocumentType, VerificationStatus]],
    is_duplicate_claim: bool = False,
    is_duplicate_incident: bool = False,
    timely_filing_days_limit: int = 30,
) -> EligibilityDecision:
    """Evaluate overall claim eligibility across all statutory and policy rules."""
    reasons: list[str] = []
    primary_rejection_code: RejectionCode | None = None

    incident_calendar_date = incident_date.date()

    # 1. Policy Active Check (NEG-01 Expired Policy & Policy Cancelled)
    policy_active = True
    if policy_status == PolicyStatus.CANCELLED and policy_cancellation_date:
        if incident_calendar_date > policy_cancellation_date:
            policy_active = False
            reasons.append(
                f"Incident date ({incident_calendar_date}) occurred after policy cancellation date ({policy_cancellation_date})"
            )
            primary_rejection_code = primary_rejection_code or RejectionCode.EXPIRED_POLICY

    if incident_calendar_date < policy_effective_date:
        policy_active = False
        reasons.append(
            f"Incident date ({incident_calendar_date}) occurred before policy effective date ({policy_effective_date})"
        )
        primary_rejection_code = primary_rejection_code or RejectionCode.EXPIRED_POLICY
    elif incident_calendar_date > policy_expiration_date:
        policy_active = False
        reasons.append(
            f"Incident date ({incident_calendar_date}) occurred after policy expiration date ({policy_expiration_date})"
        )
        primary_rejection_code = primary_rejection_code or RejectionCode.EXPIRED_POLICY

    if policy_status == PolicyStatus.SUSPENDED:
        policy_active = False
        reasons.append("Policy is currently suspended (e.g. non-payment of premium)")
        primary_rejection_code = primary_rejection_code or RejectionCode.SUSPENDED_POLICY

    # 2. Coverage Mapping Check (NEG-02 Uncovered Peril)
    # Map ClaimType to potential CoverageTypes
    claim_type_coverage_map: dict[ClaimType, list[CoverageType]] = {
        ClaimType.COLLISION: [CoverageType.COLLISION],
        ClaimType.COMPREHENSIVE: [CoverageType.COMPREHENSIVE],
        ClaimType.LIABILITY: [CoverageType.LIABILITY, CoverageType.BODILY_INJURY],
        ClaimType.PROPERTY_DAMAGE: [CoverageType.DWELLING, CoverageType.PERSONAL_PROPERTY],
        ClaimType.THEFT: [CoverageType.PERSONAL_PROPERTY, CoverageType.COMPREHENSIVE],
        ClaimType.WATER_DAMAGE: [CoverageType.DWELLING, CoverageType.PERSONAL_PROPERTY],
        ClaimType.FIRE: [CoverageType.DWELLING, CoverageType.PERSONAL_PROPERTY],
        ClaimType.BODILY_INJURY: [CoverageType.BODILY_INJURY, CoverageType.MEDICAL_PAYMENTS],
        ClaimType.MEDICAL: [CoverageType.MEDICAL_PAYMENTS, CoverageType.BODILY_INJURY],
        ClaimType.TRAVEL_LOSS: [CoverageType.TRIP_INTERRUPTION, CoverageType.BAGGAGE_LOSS],
    }

    matching_coverage_types = claim_type_coverage_map.get(claim_type, [])
    active_matching_coverages = [
        (cov_type, exclusions)
        for cov_type, is_active, exclusions in available_coverages
        if is_active and cov_type in matching_coverage_types
    ]

    incident_covered = len(active_matching_coverages) > 0
    if not incident_covered:
        reasons.append(
            f"Claim type '{claim_type.value}' is not covered under active policy coverages"
        )
        primary_rejection_code = primary_rejection_code or RejectionCode.UNCOVERED_PERIL

    # 3. Policy Exclusions Check (NEG-02 Exclusion)
    exclusions_passed = True
    for _, exclusions in active_matching_coverages:
        if exclusions and claim_type.value in exclusions:
            exclusions_passed = False
            reasons.append(
                f"Claim peril '{claim_type.value}' is explicitly listed as a policy exclusion clause"
            )
            primary_rejection_code = primary_rejection_code or RejectionCode.POLICY_EXCLUSION
            break

    # 4. Timely Filing Check (NEG-03 Untimely Filing)
    filing_window_days = (reported_date - incident_date).days
    timely_filing = filing_window_days <= timely_filing_days_limit
    if not timely_filing:
        reasons.append(
            f"Claim filed {filing_window_days} days post-incident, exceeding statutory window of {timely_filing_days_limit} days"
        )
        primary_rejection_code = primary_rejection_code or RejectionCode.UNTIMELY_FILING

    # 5. Documentation Completeness Check (NEG-04 Missing Documents)
    doc_result = check_document_completeness(claim_type, provided_documents)
    documentation_complete = doc_result.is_complete
    if not documentation_complete:
        reasons.extend(doc_result.reasons)
        primary_rejection_code = primary_rejection_code or RejectionCode.MISSING_MANDATORY_DOCUMENTS

    # 6. Fraud & Duplication Check (NEG-06 Fraud / Duplicate Claim)
    fraud_passed = True
    if is_duplicate_claim:
        fraud_passed = False
        reasons.append("Identical duplicate claim already filed within past 7 days")
        primary_rejection_code = primary_rejection_code or RejectionCode.DUPLICATE_CLAIM
    elif is_duplicate_incident:
        fraud_passed = False
        reasons.append("Suspected duplicate incident reported at same location and time")
        primary_rejection_code = primary_rejection_code or RejectionCode.SUSPECTED_FRAUD

    # Overall outcome: ALL checks must pass
    is_eligible = (
        policy_active
        and incident_covered
        and exclusions_passed
        and timely_filing
        and documentation_complete
        and fraud_passed
    )

    if is_eligible and not reasons:
        reasons.append("All statutory, coverage, and documentation requirements verified successfully")

    return EligibilityDecision(
        is_eligible=is_eligible,
        policy_active_check=policy_active,
        incident_covered_check=incident_covered,
        timely_filing_check=timely_filing,
        exclusions_check=exclusions_passed,
        documentation_complete_check=documentation_complete,
        fraud_check_passed=fraud_passed,
        decision_reasons=reasons,
        rejection_code=primary_rejection_code if not is_eligible else None,
    )
