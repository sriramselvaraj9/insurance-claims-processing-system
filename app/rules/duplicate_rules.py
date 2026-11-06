"""Duplicate claim and incident detection rules (DUPLICATE_001 to DUPLICATE_003)."""

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from app.models.claim import Claim
from app.models.incident import Incident
from app.rules.rule_base import RuleResult


def evaluate_duplicate_rules(
    current_claim: Claim,
    current_incident: Incident | None,
    existing_claims_for_policy: Sequence[Claim],
    existing_claims_for_incident: Sequence[Claim],
) -> tuple[list[RuleResult], bool]:
    """Evaluate duplicate claim submission, duplicate incident linkage, and short-window filings.

    Returns:
        (results, is_suspected_duplicate_flagged)
    """
    results: list[RuleResult] = []
    is_duplicate_flagged = False

    # DUPLICATE_001 — Exact duplicate claim
    # Same policy, same incident, and same claimed amount
    exact_duplicates = [
        c for c in existing_claims_for_policy
        if c.id != current_claim.id
        and c.incident_id == current_claim.incident_id
        and abs(c.claimed_amount - current_claim.claimed_amount) < Decimal("0.01")
    ]
    is_exact_dup = len(exact_duplicates) > 0
    if is_exact_dup:
        is_duplicate_flagged = True

    results.append(
        RuleResult(
            rule_id="DUPLICATE_001",
            name="Exact Duplicate Claim Detection",
            passed=not is_exact_dup,
            reason=(
                "No identical claim exists for this policy and incident"
                if not is_exact_dup
                else f"Exact duplicate claim detected: identical to claim '{exact_duplicates[0].id}'"
            ),
            entity_id=exact_duplicates[0].id if is_exact_dup else None,
            metadata={"duplicate_claim_ids": [c.id for c in exact_duplicates]},
        )
    )

    # DUPLICATE_002 — Duplicate incident linkage
    # Multiple claims referencing the same casualty event
    other_claims_on_incident = [
        c for c in existing_claims_for_incident
        if c.id != current_claim.id
    ]
    has_dup_incident = len(other_claims_on_incident) > 0
    if has_dup_incident:
        is_duplicate_flagged = True

    results.append(
        RuleResult(
            rule_id="DUPLICATE_002",
            name="Duplicate Incident Linkage",
            passed=not has_dup_incident,
            reason=(
                "Incident casualty record is unique to this claim"
                if not has_dup_incident
                else f"Incident '{current_claim.incident_id}' is already referenced by {len(other_claims_on_incident)} existing claim(s): {', '.join(c.id for c in other_claims_on_incident)}"
            ),
            entity_id=current_claim.incident_id,
            metadata={"conflicting_claim_ids": [c.id for c in other_claims_on_incident]},
        )
    )

    # DUPLICATE_003 — High velocity filings within 7 days
    recent_claims_7d = [
        c for c in existing_claims_for_policy
        if c.id != current_claim.id
        and abs((current_claim.reported_date - c.reported_date).total_seconds()) < (7 * 86400)
    ]
    has_recent_velocity = len(recent_claims_7d) > 0
    if has_recent_velocity:
        is_duplicate_flagged = True

    results.append(
        RuleResult(
            rule_id="DUPLICATE_003",
            name="Filing Velocity within 7 Days",
            passed=not has_recent_velocity,
            reason=(
                "No other claims filed under this policy within past 7 days"
                if not has_recent_velocity
                else f"Potential duplicate pattern: {len(recent_claims_7d)} claim(s) filed under this policy in 7-day window ({', '.join(c.id for c in recent_claims_7d)})"
            ),
            entity_id=current_claim.policy_id,
            metadata={"recent_claim_ids": [c.id for c in recent_claims_7d]},
        )
    )

    return results, is_duplicate_flagged
