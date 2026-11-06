"""Fraud indicators evaluation service."""

from datetime import datetime, timezone
from decimal import Decimal

from app.models.claim import Claim
from app.models.incident import Incident
from app.models.policy import Policy
from app.repositories.claim_repository import ClaimRepository
from app.repositories.incident_repository import IncidentRepository
from app.rules.fraud_rules import FraudAssessment, evaluate_fraud_indicators


def _to_naive_utc(dt: datetime | None) -> datetime:
    """Normalize datetime to naive UTC for safe arithmetic."""
    if dt is None:
        return datetime.utcnow()
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class FraudService:
    def __init__(
        self,
        claim_repo: ClaimRepository,
        incident_repo: IncidentRepository | None = None,
    ) -> None:
        self.claim_repo = claim_repo
        self.incident_repo = incident_repo

    def evaluate_claim_fraud(
        self,
        claim: Claim,
        policy: Policy,
        coverage_limit: Decimal,
        is_duplicate_claim: bool = False,
        is_duplicate_incident: bool = False,
        incident: Incident | None = None,
    ) -> FraudAssessment:
        """Calculate filing lag, query historical claim frequency, and run deterministic indicators."""
        # Calculate filing lag in days from incident occurrence
        ref_date = None
        if incident is not None:
            ref_date = incident.occurrence_date
        elif self.incident_repo is not None and claim.incident_id:
            inc = self.incident_repo.get_by_id(claim.incident_id)
            if inc:
                ref_date = inc.occurrence_date
        elif getattr(claim, "incident", None) is not None:
            ref_date = claim.incident.occurrence_date
        elif claim.created_at is not None:
            ref_date = claim.created_at

        if ref_date is not None:
            lag_days = max(0, (_to_naive_utc(claim.reported_date) - _to_naive_utc(ref_date)).days)
        else:
            lag_days = 0

        # Count claims filed under this policy in past 30 days
        all_policy_claims = self.claim_repo.get_by_policy_id(policy.id)
        current_rep = _to_naive_utc(claim.reported_date)
        recent_count = sum(
            1
            for c in all_policy_claims
            if c.id != claim.id
            and abs((current_rep - _to_naive_utc(c.reported_date)).total_seconds()) <= (30 * 86400)
        )

        return evaluate_fraud_indicators(
            claim_id=claim.id,
            policy_status=policy.status,
            claimed_amount=claim.claimed_amount,
            coverage_limit=coverage_limit,
            filing_lag_days=lag_days,
            claims_in_past_30d=recent_count,
            is_duplicate_claim=is_duplicate_claim,
            is_duplicate_incident=is_duplicate_incident,
        )
