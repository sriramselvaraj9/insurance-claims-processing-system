"""Coverage validation rules (COVERAGE_001 to COVERAGE_005).

Validates coverage type compatibility, temporal coverage window, policy exclusions,
and coverage limits vs claimed loss amounts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from app.models.coverage import Coverage
from app.models.enums import ClaimType, CoverageType
from app.rules.rule_base import RuleResult

# Documented mapping of ClaimType to compatible CoverageTypes
CLAIM_TO_COVERAGE_TYPES: dict[ClaimType, list[CoverageType]] = {
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


def evaluate_coverage_rules(
    claim_type: ClaimType,
    incident_date: datetime,
    claimed_amount: Decimal,
    available_coverages: Sequence[Coverage],
) -> tuple[list[RuleResult], Coverage | None]:
    """Evaluate coverage compatibility, temporal validity, exclusions, and limit adequacy."""
    results: list[RuleResult] = []
    incident_calendar_date = incident_date.date()

    compatible_types = CLAIM_TO_COVERAGE_TYPES.get(claim_type, [])

    # 1. Identify matching active coverages
    matching_coverages = [
        cov for cov in available_coverages
        if cov.is_active and cov.coverage_type in compatible_types
    ]

    # COVERAGE_001 — Applicable coverage existence
    has_coverage = len(matching_coverages) > 0
    results.append(
        RuleResult(
            rule_id="COVERAGE_001",
            name="Applicable Coverage Existence",
            passed=has_coverage,
            reason=(
                f"Active coverage found for peril '{claim_type.value}'"
                if has_coverage
                else f"No active policy coverage found compatible with claim peril '{claim_type.value}'"
            ),
            entity_id=matching_coverages[0].id if matching_coverages else None,
            metadata={"claim_type": claim_type.value, "compatible_types": [c.value for c in compatible_types]},
        )
    )

    if not has_coverage:
        return results, None

    # Select primary applicable coverage
    primary_cov = matching_coverages[0]

    # COVERAGE_002 — Coverage temporal validity
    in_period = (
        primary_cov.effective_date <= incident_calendar_date <= primary_cov.expiration_date
    )
    results.append(
        RuleResult(
            rule_id="COVERAGE_002",
            name="Coverage Period Validity",
            passed=in_period,
            reason=(
                f"Incident date ({incident_calendar_date}) is within coverage period ({primary_cov.effective_date} to {primary_cov.expiration_date})"
                if in_period
                else f"Incident date ({incident_calendar_date}) occurred outside coverage period ({primary_cov.effective_date} to {primary_cov.expiration_date})"
            ),
            entity_id=primary_cov.id,
            metadata={
                "incident_date": incident_calendar_date.isoformat(),
                "coverage_effective": primary_cov.effective_date.isoformat(),
                "coverage_expiration": primary_cov.expiration_date.isoformat(),
            },
        )
    )

    # COVERAGE_003 — Policy exclusions check
    exclusions = primary_cov.exclusions or []
    is_excluded = claim_type.value in exclusions
    results.append(
        RuleResult(
            rule_id="COVERAGE_003",
            name="Policy Exclusions Check",
            passed=not is_excluded,
            reason=(
                f"Peril '{claim_type.value}' is not excluded under policy terms"
                if not is_excluded
                else f"Claim peril '{claim_type.value}' is explicitly listed as a policy exclusion clause"
            ),
            entity_id=primary_cov.id,
            metadata={"exclusions": exclusions, "claim_type": claim_type.value},
        )
    )

    # COVERAGE_004 — Coverage limit adequacy
    within_limit = (claimed_amount <= primary_cov.coverage_limit)
    results.append(
        RuleResult(
            rule_id="COVERAGE_004",
            name="Coverage Limit Adequacy",
            passed=within_limit,
            reason=(
                f"Claimed amount (${claimed_amount}) is within coverage limit (${primary_cov.coverage_limit})"
                if within_limit
                else f"Claimed amount (${claimed_amount}) exceeds coverage limit (${primary_cov.coverage_limit})"
            ),
            entity_id=primary_cov.id,
            metadata={
                "claimed_amount": str(claimed_amount),
                "coverage_limit": str(primary_cov.coverage_limit),
                "deductible": str(primary_cov.deductible),
                "copay_percentage": str(primary_cov.copay_percentage),
            },
        )
    )

    return results, primary_cov
