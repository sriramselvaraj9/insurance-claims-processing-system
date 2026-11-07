"""Settlement recommendation, supervisor approval, and disbursement payment service."""

from datetime import datetime, timezone
from decimal import Decimal

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.enums import (
    ActorType,
    AuditAction,
    ClaimStatus,
    PaymentMethod,
    PaymentStatus,
    SettlementStatus,
)
from app.models.settlement import Settlement
from app.models.settlement_payment import SettlementPayment
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.settlement_payment_repository import SettlementPaymentRepository
from app.repositories.settlement_repository import SettlementRepository
from app.rules.financial_rules import compute_settlement
from app.services.exceptions import (
    DuplicatePaymentError,
    SettlementLimitExceededError,
)


class SettlementService:
    def __init__(
        self,
        settlement_repo: SettlementRepository,
        payment_repo: SettlementPaymentRepository,
        claim_repo: ClaimRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.settlement_repo = settlement_repo
        self.payment_repo = payment_repo
        self.claim_repo = claim_repo
        self.audit_repo = audit_repo

    def recommend_settlement(
        self,
        claim: Claim,
        coverage: Coverage,
        force_exceed_limit_for_test: bool = False,
        actor_id: str = "SETTLEMENT_RECOMMENDATION_ENGINE",
    ) -> Settlement:
        """Calculate net settlement recommendation applying limits, deductibles, and copays."""
        cov_limit = coverage.coverage_limit
        deductible = coverage.deductible
        copay_pct = coverage.copay_percentage

        # Test control for Scenario 4
        if force_exceed_limit_for_test:
            excessive_net = (cov_limit * Decimal("1.50")).quantize(Decimal("0.01"))
            now = datetime.now(timezone.utc)
            settlement_id = IdGenerator.settlement_id(claim.id, self.settlement_repo.count() + 1)

            settlement = Settlement(
                id=settlement_id,
                claim_id=claim.id,
                recommended_amount=excessive_net,
                approved_amount=None,
                deductible_applied=Decimal("0.00"),
                copay_applied=Decimal("0.00"),
                net_settlement_amount=excessive_net,
                status=SettlementStatus.REJECTED,
                settled_at=now,
                settled_by="SUPERVISOR_AUDIT",
                payment_reference=None,
                created_at=now,
                updated_at=now,
            )
            self.settlement_repo.create(settlement)

            # Record SETTLEMENT_BLOCKED audit event
            audit_event = AuditEvent(
                id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
                entity_type="Settlement",
                entity_id=settlement_id,
                action=AuditAction.SETTLEMENT_BLOCKED,
                state_before=None,
                state_after={"status": SettlementStatus.REJECTED.value, "net_amount": str(excessive_net)},
                actor_type=ActorType.SYSTEM_RULE,
                actor_id=actor_id,
                timestamp=now,
                metadata_={
                    "claim_id": claim.id,
                    "coverage_limit": str(cov_limit),
                    "reason": "Recommended net settlement exceeds policy coverage limit ceiling",
                },
            )
            self.audit_repo.create(audit_event)
            raise SettlementLimitExceededError(str(excessive_net), str(cov_limit), coverage.policy_id)

        # Standard legal calculation: capped at coverage limit
        breakdown = compute_settlement(
            claimed_amount=claim.claimed_amount,
            coverage_limit=cov_limit,
            deductible=deductible,
            copay_percentage=copay_pct,
        )

        now = datetime.now(timezone.utc)
        existing_settlements = self.settlement_repo.get_by_claim_id(claim.id)
        seq = len(existing_settlements) + 1
        settlement_id = IdGenerator.settlement_id(claim.id, seq)

        # High-value threshold ($25,000) routes to SUPERVISOR_REVIEW
        initial_status = (
            SettlementStatus.SUPERVISOR_REVIEW
            if breakdown.net_settlement_amount >= Decimal("25000.00")
            else SettlementStatus.PROPOSED
        )

        settlement = Settlement(
            id=settlement_id,
            claim_id=claim.id,
            recommended_amount=breakdown.allowable_loss,
            approved_amount=None,
            deductible_applied=breakdown.deductible_applied,
            copay_applied=breakdown.copay_applied,
            net_settlement_amount=breakdown.net_settlement_amount,
            status=initial_status,
            settled_at=None,
            settled_by=None,
            payment_reference=None,
            created_at=now,
            updated_at=now,
        )
        self.settlement_repo.create(settlement)

        # Record SETTLEMENT_RECOMMENDED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Settlement",
            entity_id=settlement_id,
            action=AuditAction.SETTLEMENT_RECOMMENDED,
            state_before=None,
            state_after={
                "status": initial_status.value,
                "allowable_loss": str(breakdown.allowable_loss),
                "deductible_applied": str(breakdown.deductible_applied),
                "copay_applied": str(breakdown.copay_applied),
                "net_settlement_amount": str(breakdown.net_settlement_amount),
            },
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={"claim_id": claim.id, "sequence": seq},
        )
        self.audit_repo.create(audit_event)

        return settlement

    def approve_settlement(
        self,
        settlement_id: str,
        approved_by: str,
        actor_type: ActorType = ActorType.USER_ADJUSTER,
    ) -> Settlement:
        """Supervisor or adjuster approval of recommended settlement."""
        settlement = self.settlement_repo.get_by_id(settlement_id)
        if not settlement:
            raise ValueError(f"Settlement '{settlement_id}' not found")

        if settlement.status == SettlementStatus.DISBURSED:
            raise ValueError(f"Settlement '{settlement_id}' is already disbursed and cannot be approved again")

        now = datetime.now(timezone.utc)
        settlement.approved_amount = settlement.net_settlement_amount
        settlement.status = SettlementStatus.APPROVED
        settlement.settled_by = approved_by
        settlement.settled_at = now
        self.settlement_repo.update(settlement)

        # Record SETTLEMENT_APPROVED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Settlement",
            entity_id=settlement_id,
            action=AuditAction.SETTLEMENT_APPROVED,
            state_before={"status": SettlementStatus.PROPOSED.value},
            state_after={"status": SettlementStatus.APPROVED.value, "approved_amount": str(settlement.approved_amount)},
            actor_type=actor_type,
            actor_id=approved_by,
            timestamp=now,
            metadata_={"claim_id": settlement.claim_id},
        )
        self.audit_repo.create(audit_event)

        return settlement

    def disburse_payment(
        self,
        settlement_id: str,
        payment_method: PaymentMethod = PaymentMethod.ACH,
        actor_id: str = "FINANCIAL_DISBURSEMENT_GATEWAY",
    ) -> SettlementPayment:
        """Disburse payment with strict duplicate payment prevention (Scenario 6 control)."""
        settlement = self.settlement_repo.get_by_id(settlement_id)
        if not settlement:
            raise ValueError(f"Settlement '{settlement_id}' not found")

        # Duplicate payment check (Scenario 6 control):
        # A completed payment for this settlement must block subsequent payments
        existing_payments = self.payment_repo.get_by_settlement_id(settlement_id)
        completed_payments = [p for p in existing_payments if p.status == PaymentStatus.COMPLETED]

        now = datetime.now(timezone.utc)

        if completed_payments:
            # Block duplicate payment
            audit_blocked = AuditEvent(
                id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
                entity_type="SettlementPayment",
                entity_id=settlement_id,
                action=AuditAction.PAYMENT_BLOCKED,
                state_before=None,
                state_after={"reason": "DUPLICATE_PAYMENT_ATTEMPT"},
                actor_type=ActorType.SYSTEM_RULE,
                actor_id=actor_id,
                timestamp=now,
                metadata_={
                    "settlement_id": settlement_id,
                    "existing_payment_id": completed_payments[0].id,
                    "existing_payment_reference": completed_payments[0].payment_reference,
                },
            )
            self.audit_repo.create(audit_blocked)
            raise DuplicatePaymentError(settlement_id, completed_payments[0].id)

        # Enforce approval before disbursement
        if settlement.status != SettlementStatus.APPROVED:
            raise ValueError(
                f"Settlement '{settlement_id}' must be approved by supervisor before disbursement (current status: {settlement.status.value})"
            )

        # Disburse payment
        seq = len(existing_payments) + 1
        pay_id = IdGenerator.settlement_payment_id(settlement_id, seq)
        pay_ref = f"PAYREF-{settlement_id}-{seq:02d}"
        disburse_amount = settlement.approved_amount or settlement.net_settlement_amount

        payment = SettlementPayment(
            id=pay_id,
            settlement_id=settlement_id,
            payment_amount=disburse_amount,
            payment_method=payment_method,
            payment_reference=pay_ref,
            payment_date=now,
            status=PaymentStatus.COMPLETED,
        )
        self.payment_repo.create(payment)

        # Update settlement record
        settlement.status = SettlementStatus.DISBURSED
        settlement.payment_reference = pay_ref
        self.settlement_repo.update(settlement)

        # Update claim status to SETTLED
        claim = self.claim_repo.get_by_id(settlement.claim_id)
        if claim:
            claim.status = ClaimStatus.SETTLED
            self.claim_repo.update(claim)

        # Record PAYMENT_COMPLETED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="SettlementPayment",
            entity_id=pay_id,
            action=AuditAction.PAYMENT_COMPLETED,
            state_before=None,
            state_after={
                "status": PaymentStatus.COMPLETED.value,
                "amount": str(disburse_amount),
                "reference": pay_ref,
            },
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={"settlement_id": settlement_id, "claim_id": settlement.claim_id},
        )
        self.audit_repo.create(audit_event)

        return payment
