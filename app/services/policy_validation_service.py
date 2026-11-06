"""Policy validation service executing POLICY_001 through POLICY_006 against actual records."""

from datetime import datetime, timezone
from dataclasses import dataclass

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.enums import ActorType, AuditAction
from app.models.incident import Incident
from app.repositories.audit_repository import AuditRepository
from app.repositories.policy_repository import PolicyRepository
from app.rules.policy_rules import evaluate_policy_rules
from app.rules.rule_base import RuleResult


@dataclass(frozen=True)
class PolicyValidationResult:
    is_valid: bool
    policy_id: str
    rule_results: list[RuleResult]
    failure_reasons: list[str]


class PolicyValidationService:
    def __init__(
        self,
        policy_repo: PolicyRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.policy_repo = policy_repo
        self.audit_repo = audit_repo

    def validate_policy(
        self,
        claim: Claim,
        incident: Incident,
        actor_id: str = "POLICY_VALIDATION_ENGINE",
    ) -> PolicyValidationResult:
        """Execute policy validation rules and record an audit event."""
        policy = self.policy_repo.get_by_id(claim.policy_id)

        rule_results = evaluate_policy_rules(
            claim_customer_id=claim.customer_id,
            incident_date=incident.occurrence_date,
            policy=policy,
        )

        failures = [r.reason for r in rule_results if not r.passed]
        is_valid = len(failures) == 0

        now = datetime.now(timezone.utc)
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Policy",
            entity_id=claim.policy_id,
            action=AuditAction.POLICY_VALIDATED,
            state_before=None,
            state_after={"is_valid": is_valid, "rules_evaluated": len(rule_results)},
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "claim_id": claim.id,
                "failures": failures,
                "rule_ids": [r.rule_id for r in rule_results],
            },
        )
        self.audit_repo.create(audit_event)

        return PolicyValidationResult(
            is_valid=is_valid,
            policy_id=claim.policy_id,
            rule_results=rule_results,
            failure_reasons=failures,
        )
