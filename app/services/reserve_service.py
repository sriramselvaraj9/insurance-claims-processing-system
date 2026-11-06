"""Preliminary reserve calculation service using fixed-point Decimal arithmetic."""

from datetime import datetime, timezone
from decimal import Decimal

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import ActorType, AuditAction, ReserveCalculationMethod
from app.models.reserve import Reserve
from app.repositories.audit_repository import AuditRepository
from app.repositories.reserve_repository import ReserveRepository
from app.rules.financial_rules import DEFAULT_EXPENSE_RATIO, compute_total_reserve


class ReserveService:
    def __init__(
        self,
        reserve_repo: ReserveRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.reserve_repo = reserve_repo
        self.audit_repo = audit_repo

    def calculate_claim_reserve(
        self,
        claim: Claim,
        coverage: Coverage | None,
        expense_ratio: Decimal = DEFAULT_EXPENSE_RATIO,
        actor_id: str = "SYSTEM_ACTUARIAL_ENGINE",
    ) -> Reserve:
        """Compute preliminary indemnity and expense reserve using documented formula and persist record."""
        cov_limit = coverage.coverage_limit if coverage else claim.estimated_loss
        deductible = coverage.deductible if coverage else Decimal("0.00")

        # Covered loss = min(estimated loss, remaining coverage limit)
        # Indemnity reserve = max(covered loss - deductible, 0)
        # Expense reserve = indemnity reserve * 12%
        breakdown = compute_total_reserve(
            estimated_loss=claim.estimated_loss,
            coverage_limit=cov_limit,
            deductible=deductible,
            expense_ratio=expense_ratio,
        )

        now = datetime.now(timezone.utc)
        existing_reserves = self.reserve_repo.get_by_claim_id(claim.id)
        seq = len(existing_reserves) + 1
        res_id = IdGenerator.reserve_id(claim.id, seq)

        reserve = Reserve(
            id=res_id,
            claim_id=claim.id,
            estimated_indemnity_reserve=breakdown.indemnity_reserve,
            estimated_expense_reserve=breakdown.expense_reserve,
            total_reserve=breakdown.total_reserve,
            expense_ratio=expense_ratio,
            calculation_method=ReserveCalculationMethod.FORMULAIC_STANDARD,
            calculated_at=now,
            calculated_by=actor_id,
            created_at=now,
        )
        self.reserve_repo.create(reserve)

        # Record RESERVE_CALCULATED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Reserve",
            entity_id=res_id,
            action=AuditAction.RESERVE_CALCULATED,
            state_before=None,
            state_after={
                "indemnity_reserve": str(breakdown.indemnity_reserve),
                "expense_reserve": str(breakdown.expense_reserve),
                "total_reserve": str(breakdown.total_reserve),
            },
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "claim_id": claim.id,
                "coverage_limit": str(cov_limit),
                "deductible": str(deductible),
                "expense_ratio": str(expense_ratio),
                "sequence": seq,
            },
        )
        self.audit_repo.create(audit_event)

        return reserve
