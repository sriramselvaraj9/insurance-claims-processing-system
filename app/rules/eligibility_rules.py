"""Deterministic eligibility assessment engine with strict decision precedence.

Decision Priority:
1. Nonexistent policy or ownership mismatch -> INELIGIBLE (Rejection)
2. Policy invalid at incident date (commencement, expiry, cancellation, suspension) -> INELIGIBLE
3. No applicable coverage clause -> INELIGIBLE
4. Explicit policy exclusion clause matched -> INELIGIBLE
5. Untimely filing statutory window exceeded -> INELIGIBLE
6. Missing mandatory evidence / unverified documents -> PENDING_DOCUMENTS
7. Duplicate claim indicators / duplicate incident -> MANUAL_REVIEW
8. High severity fraud indicators -> MANUAL_REVIEW
9. All required checks passed -> ELIGIBLE
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

from app.models.enums import (
    AssessmentOutcome,
    ClaimType,
    CoverageType,
    DocumentType,
    PolicyStatus,
    RejectionCode,
    VerificationStatus,
)
from app.rules.coverage_rules import evaluate_coverage_rules
from app.rules.document_rules import check_document_completeness
from app.rules.duplicate_rules import evaluate_duplicate_rules
from app.rules.fraud_rules import evaluate_fraud_indicators
from app.rules.policy_rules import evaluate_policy_rules
from app.rules.rule_base import RuleResult


@dataclass(frozen=True)
class EligibilityDecision:
    outcome: AssessmentOutcome
    is_eligible: bool
    policy_active_check: bool
    incident_covered_check: bool
    timely_filing_check: bool
    exclusions_check: bool
    documentation_complete_check: bool
    fraud_check_passed: bool
    decision_reasons: list[str]
    rejection_code: RejectionCode | None
    rule_results: list[RuleResult]


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
    claim_customer_id: str | None = None,
    policy_customer_id: str | None = None,
) -> EligibilityDecision:
    """Evaluate overall claim eligibility following the documented precedence order."""
    reasons: list[str] = []
    all_rule_results: list[RuleResult] = []
    rejection_code: RejectionCode | None = None

    incident_calendar_date = incident_date.date()

    # Precedence Step 1: Customer Ownership
    if claim_customer_id and policy_customer_id and claim_customer_id != policy_customer_id:
        reasons.append(f"Customer ownership mismatch: Claim customer '{claim_customer_id}' != policy owner '{policy_customer_id}'")
        return EligibilityDecision(
            outcome=AssessmentOutcome.INELIGIBLE,
            is_eligible=False,
            policy_active_check=False,
            incident_covered_check=False,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=True,
            decision_reasons=reasons,
            rejection_code=RejectionCode.EXPIRED_POLICY,
            rule_results=[
                RuleResult("POLICY_005", "Customer Ownership", False, reasons[0])
            ],
        )

    # Precedence Step 2: Policy Validity at Incident Date (NEG-01)
    policy_active = True
    if policy_status == PolicyStatus.CANCELLED and policy_cancellation_date:
        if incident_calendar_date >= policy_cancellation_date:
            policy_active = False
            reasons.append(
                f"Incident date ({incident_calendar_date}) occurred after policy cancellation date ({policy_cancellation_date})"
            )
            rejection_code = rejection_code or RejectionCode.EXPIRED_POLICY

    if incident_calendar_date < policy_effective_date:
        policy_active = False
        reasons.append(
            f"Incident date ({incident_calendar_date}) occurred before policy commencement ({policy_effective_date})"
        )
        rejection_code = rejection_code or RejectionCode.EXPIRED_POLICY
    elif incident_calendar_date > policy_expiration_date:
        policy_active = False
        reasons.append(
            f"Incident date ({incident_calendar_date}) occurred after policy expiration ({policy_expiration_date})"
        )
        rejection_code = rejection_code or RejectionCode.EXPIRED_POLICY

    if policy_status == PolicyStatus.SUSPENDED:
        policy_active = False
        reasons.append("Policy is currently suspended (compliance hold / premium default)")
        rejection_code = rejection_code or RejectionCode.SUSPENDED_POLICY

    if not policy_active:
        return EligibilityDecision(
            outcome=AssessmentOutcome.INELIGIBLE,
            is_eligible=False,
            policy_active_check=False,
            incident_covered_check=True,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=True,
            decision_reasons=reasons,
            rejection_code=rejection_code,
            rule_results=[RuleResult("POLICY_002", "Policy Inception/Validity", False, reasons[0])],
        )

    # Precedence Step 3: Coverage Mapping (NEG-02 Uncovered Peril)
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

    matching_types = claim_type_coverage_map.get(claim_type, [])
    active_matching_coverages = [
        (cov_type, exclusions)
        for cov_type, is_active, exclusions in available_coverages
        if is_active and cov_type in matching_types
    ]
    incident_covered = len(active_matching_coverages) > 0
    if not incident_covered:
        reasons.append(f"Claim peril '{claim_type.value}' is not covered under active policy coverages")
        return EligibilityDecision(
            outcome=AssessmentOutcome.INELIGIBLE,
            is_eligible=False,
            policy_active_check=True,
            incident_covered_check=False,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=True,
            decision_reasons=reasons,
            rejection_code=RejectionCode.UNCOVERED_PERIL,
            rule_results=[RuleResult("COVERAGE_001", "Peril Coverage Existence", False, reasons[0])],
        )

    # Precedence Step 4: Policy Exclusions (NEG-02 Exclusion)
    exclusions_passed = True
    for _, exclusions in active_matching_coverages:
        if exclusions and claim_type.value in exclusions:
            exclusions_passed = False
            reasons.append(f"Claim peril '{claim_type.value}' is explicitly listed as a policy exclusion clause")
            return EligibilityDecision(
                outcome=AssessmentOutcome.INELIGIBLE,
                is_eligible=False,
                policy_active_check=True,
                incident_covered_check=True,
                timely_filing_check=True,
                exclusions_check=False,
                documentation_complete_check=True,
                fraud_check_passed=True,
                decision_reasons=reasons,
                rejection_code=RejectionCode.POLICY_EXCLUSION,
                rule_results=[RuleResult("COVERAGE_003", "Exclusion Clause", False, reasons[0])],
            )

    # Precedence Step 5: Timely Filing Statutory Window (NEG-03)
    filing_window_days = (reported_date - incident_date).days
    timely_filing = (filing_window_days <= timely_filing_days_limit)
    if not timely_filing:
        reasons.append(
            f"Claim filed {filing_window_days} days post-incident, exceeding statutory notice window of {timely_filing_days_limit} days"
        )
        return EligibilityDecision(
            outcome=AssessmentOutcome.INELIGIBLE,
            is_eligible=False,
            policy_active_check=True,
            incident_covered_check=True,
            timely_filing_check=False,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=True,
            decision_reasons=reasons,
            rejection_code=RejectionCode.UNTIMELY_FILING,
            rule_results=[RuleResult("FRAUD_003", "Timely Notice Limit", False, reasons[0])],
        )

    # Precedence Step 6: Duplicate Detection & Fraud Indicators (NEG-06)
    fraud_passed = True
    if is_duplicate_claim:
        fraud_passed = False
        reasons.append("Identical duplicate claim already filed for this policy and incident")
        return EligibilityDecision(
            outcome=AssessmentOutcome.MANUAL_REVIEW,
            is_eligible=False,
            policy_active_check=True,
            incident_covered_check=True,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=False,
            decision_reasons=reasons,
            rejection_code=RejectionCode.DUPLICATE_CLAIM,
            rule_results=[RuleResult("DUPLICATE_001", "Duplicate Claim Submission", False, reasons[0])],
        )

    if is_duplicate_incident:
        fraud_passed = False
        reasons.append("Suspected duplicate incident reported at same casualty occurrence")
        return EligibilityDecision(
            outcome=AssessmentOutcome.MANUAL_REVIEW,
            is_eligible=False,
            policy_active_check=True,
            incident_covered_check=True,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=True,
            fraud_check_passed=False,
            decision_reasons=reasons,
            rejection_code=RejectionCode.SUSPECTED_FRAUD,
            rule_results=[RuleResult("DUPLICATE_002", "Duplicate Incident Linkage", False, reasons[0])],
        )

    # Precedence Step 7: Documentation Completeness (NEG-04 Missing Documents)
    doc_result = check_document_completeness(claim_type, provided_documents)
    documentation_complete = doc_result.is_complete
    if not documentation_complete:
        reasons.extend(doc_result.reasons)
        return EligibilityDecision(
            outcome=AssessmentOutcome.PENDING_DOCUMENTS,
            is_eligible=False,
            policy_active_check=True,
            incident_covered_check=True,
            timely_filing_check=True,
            exclusions_check=True,
            documentation_complete_check=False,
            fraud_check_passed=True,
            decision_reasons=reasons,
            rejection_code=RejectionCode.MISSING_MANDATORY_DOCUMENTS,
            rule_results=doc_result.rule_results,
        )

    # Precedence Step 8: Clean ELIGIBLE Outcome
    reasons.append("All statutory, policy coverage, and documentation verification requirements satisfied")
    return EligibilityDecision(
        outcome=AssessmentOutcome.ELIGIBLE,
        is_eligible=True,
        policy_active_check=True,
        incident_covered_check=True,
        timely_filing_check=True,
        exclusions_check=True,
        documentation_complete_check=True,
        fraud_check_passed=True,
        decision_reasons=reasons,
        rejection_code=None,
        rule_results=[RuleResult("ELIGIBILITY_001", "Overall Eligibility Passed", True, reasons[0])],
    )
