"""Policy validation rules (POLICY_001 to POLICY_006).

Evaluates policy existence, commencement, expiry, cancellation, customer ownership, and active status.
"""

from datetime import datetime
from typing import Sequence

from app.models.enums import PolicyStatus
from app.models.policy import Policy
from app.rules.rule_base import RuleResult


def evaluate_policy_rules(
    claim_customer_id: str,
    incident_date: datetime,
    policy: Policy | None,
) -> list[RuleResult]:
    """Evaluate all policy validation rules for a claim."""
    results: list[RuleResult] = []

    # POLICY_001 — Policy existence
    if policy is None:
        results.append(
            RuleResult(
                rule_id="POLICY_001",
                name="Policy Existence",
                passed=False,
                reason="Referenced policy does not exist in the policy database",
                entity_id=None,
            )
        )
        return results

    results.append(
        RuleResult(
            rule_id="POLICY_001",
            name="Policy Existence",
            passed=True,
            reason=f"Policy '{policy.id}' exists and was successfully loaded",
            entity_id=policy.id,
        )
    )

    incident_calendar_date = incident_date.date()

    # POLICY_005 — Customer ownership
    is_owner = (policy.customer_id == claim_customer_id)
    results.append(
        RuleResult(
            rule_id="POLICY_005",
            name="Customer Ownership",
            passed=is_owner,
            reason=(
                f"Customer '{claim_customer_id}' verified as policy owner"
                if is_owner
                else f"Claim customer '{claim_customer_id}' does not match policy owner '{policy.customer_id}'"
            ),
            entity_id=policy.id,
            metadata={"claim_customer_id": claim_customer_id, "policy_customer_id": policy.customer_id},
        )
    )

    # POLICY_002 — Policy commencement
    commenced = (incident_calendar_date >= policy.effective_date)
    results.append(
        RuleResult(
            rule_id="POLICY_002",
            name="Policy Commencement",
            passed=commenced,
            reason=(
                f"Incident date ({incident_calendar_date}) is on or after policy inception ({policy.effective_date})"
                if commenced
                else f"Incident date ({incident_calendar_date}) occurred before policy commencement ({policy.effective_date})"
            ),
            entity_id=policy.id,
            metadata={"incident_date": incident_calendar_date.isoformat(), "effective_date": policy.effective_date.isoformat()},
        )
    )

    # POLICY_003 — Policy expiry
    unexpired = (incident_calendar_date <= policy.expiration_date)
    results.append(
        RuleResult(
            rule_id="POLICY_003",
            name="Policy Expiry",
            passed=unexpired,
            reason=(
                f"Incident date ({incident_calendar_date}) occurred within policy term (expires {policy.expiration_date})"
                if unexpired
                else f"Incident date ({incident_calendar_date}) occurred after policy expiration ({policy.expiration_date})"
            ),
            entity_id=policy.id,
            metadata={"incident_date": incident_calendar_date.isoformat(), "expiration_date": policy.expiration_date.isoformat()},
        )
    )

    # POLICY_004 — Policy cancellation
    not_cancelled_before_incident = True
    if policy.status == PolicyStatus.CANCELLED and policy.cancellation_date:
        if incident_calendar_date >= policy.cancellation_date:
            not_cancelled_before_incident = False

    results.append(
        RuleResult(
            rule_id="POLICY_004",
            name="Policy Cancellation",
            passed=not_cancelled_before_incident,
            reason=(
                "Policy was not cancelled prior to the incident occurrence date"
                if not_cancelled_before_incident
                else f"Policy was cancelled on {policy.cancellation_date} prior to or on incident date ({incident_calendar_date})"
            ),
            entity_id=policy.id,
            metadata={
                "policy_status": policy.status.value,
                "cancellation_date": policy.cancellation_date.isoformat() if policy.cancellation_date else None,
            },
        )
    )

    # POLICY_006 — Policy operational status (Active vs Suspended / Draft)
    is_active_status = (policy.status == PolicyStatus.ACTIVE)
    results.append(
        RuleResult(
            rule_id="POLICY_006",
            name="Policy Operational Status",
            passed=is_active_status,
            reason=(
                "Policy status is ACTIVE"
                if is_active_status
                else f"Policy status is {policy.status.value} (must be ACTIVE for automated coverage)"
            ),
            entity_id=policy.id,
            metadata={"status": policy.status.value},
        )
    )

    return results
