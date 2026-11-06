"""Duplicate claim and incident detection service."""

from dataclasses import dataclass
from typing import Sequence

from app.models.claim import Claim
from app.models.incident import Incident
from app.repositories.claim_repository import ClaimRepository
from app.repositories.incident_repository import IncidentRepository
from app.rules.duplicate_rules import evaluate_duplicate_rules
from app.rules.rule_base import RuleResult


@dataclass(frozen=True)
class DuplicateDetectionResult:
    has_duplicates: bool
    rule_results: list[RuleResult]
    failure_reasons: list[str]


class DuplicateDetectionService:
    def __init__(
        self,
        claim_repo: ClaimRepository,
        incident_repo: IncidentRepository,
    ) -> None:
        self.claim_repo = claim_repo
        self.incident_repo = incident_repo

    def check_duplicates(
        self,
        claim: Claim,
        incident: Incident | None,
    ) -> DuplicateDetectionResult:
        """Query existing claims for the policy and incident, then evaluate duplicate rules."""
        claims_for_policy = self.claim_repo.get_by_policy_id(claim.policy_id)
        claims_for_incident = self.claim_repo.get_by_incident_id(claim.incident_id)

        rule_results, is_flagged = evaluate_duplicate_rules(
            current_claim=claim,
            current_incident=incident,
            existing_claims_for_policy=claims_for_policy,
            existing_claims_for_incident=claims_for_incident,
        )

        failures = [r.reason for r in rule_results if not r.passed]

        return DuplicateDetectionResult(
            has_duplicates=is_flagged,
            rule_results=rule_results,
            failure_reasons=failures,
        )
