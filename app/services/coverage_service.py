"""Coverage validation service executing COVERAGE_001 through COVERAGE_004 against actual policy coverages."""

from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import ActorType, AuditAction
from app.models.incident import Incident
from app.repositories.audit_repository import AuditRepository
from app.repositories.coverage_repository import CoverageRepository
from app.rules.coverage_rules import evaluate_coverage_rules
from app.rules.rule_base import RuleResult


@dataclass(frozen=True)
class CoverageValidationResult:
    is_covered: bool
    applicable_coverage: Coverage | None
    coverage_limit: Decimal
    deductible: Decimal
    copay_percentage: Decimal
    rule_results: list[RuleResult]
    failure_reasons: list[str]


class CoverageService:
    def __init__(
        self,
        coverage_repo: CoverageRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.coverage_repo = coverage_repo
        self.audit_repo = audit_repo

    def validate_coverage(
        self,
        claim: Claim,
        incident: Incident,
        actor_id: str = "COVERAGE_VALIDATION_ENGINE",
    ) -> CoverageValidationResult:
        """Evaluate coverage compatibility, limits, exclusions, and record audit event."""
        available_coverages = self.coverage_repo.get_active_coverages_for_policy(claim.policy_id)

        rule_results, primary_cov = evaluate_coverage_rules(
            claim_type=claim.claim_type,
            incident_date=incident.occurrence_date,
            claimed_amount=claim.claimed_amount,
            available_coverages=available_coverages,
        )

        failures = [r.reason for r in rule_results if not r.passed]
        # COVERAGE_004 (limit adequacy) failure is not necessarily fatal (it caps, rather than denies coverage)
        # But COVERAGE_001 (existence), COVERAGE_002 (period), and COVERAGE_003 (exclusions) are fatal.
        fatal_failures = [
            r.reason for r in rule_results
            if not r.passed and r.rule_id in ("COVERAGE_001", "COVERAGE_002", "COVERAGE_003")
        ]
        is_covered = len(fatal_failures) == 0 and primary_cov is not None

        cov_limit = primary_cov.coverage_limit if primary_cov else Decimal("0.00")
        deductible = primary_cov.deductible if primary_cov else Decimal("0.00")
        copay_pct = primary_cov.copay_percentage if primary_cov else Decimal("0.00")

        now = datetime.now(timezone.utc)
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Coverage",
            entity_id=primary_cov.id if primary_cov else claim.policy_id,
            action=AuditAction.COVERAGE_VALIDATED,
            state_before=None,
            state_after={"is_covered": is_covered, "coverage_limit": str(cov_limit)},
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "claim_id": claim.id,
                "coverage_id": primary_cov.id if primary_cov else None,
                "failures": failures,
            },
        )
        self.audit_repo.create(audit_event)

        return CoverageValidationResult(
            is_covered=is_covered,
            applicable_coverage=primary_cov,
            coverage_limit=cov_limit,
            deductible=deductible,
            copay_percentage=copay_pct,
            rule_results=rule_results,
            failure_reasons=failures,
        )
