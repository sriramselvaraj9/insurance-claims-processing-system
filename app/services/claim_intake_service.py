"""Claim intake service validating prerequisites, line items, and recording initial intake audits."""

from datetime import datetime, timezone
from decimal import Decimal

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.claim_item import ClaimItem
from app.models.claim_status_history import ClaimStatusHistory
from app.models.enums import ActorType, AuditAction, ClaimStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_item_repository import ClaimItemRepository
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_status_history_repository import ClaimStatusHistoryRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.incident_repository import IncidentRepository
from app.repositories.policy_repository import PolicyRepository
from app.schemas.claim_schemas import ClaimIntakeRequest
from app.services.exceptions import (
    CustomerNotFoundError,
    CustomerPolicyMismatchError,
    DuplicateClaimSubmissionError,
    IncidentNotFoundError,
    InvalidFinancialValueError,
    PolicyNotFoundError,
)


class ClaimIntakeService:
    def __init__(
        self,
        claim_repo: ClaimRepository,
        claim_item_repo: ClaimItemRepository,
        customer_repo: CustomerRepository,
        policy_repo: PolicyRepository,
        incident_repo: IncidentRepository,
        audit_repo: AuditRepository,
        csh_repo: ClaimStatusHistoryRepository,
    ) -> None:
        self.claim_repo = claim_repo
        self.claim_item_repo = claim_item_repo
        self.customer_repo = customer_repo
        self.policy_repo = policy_repo
        self.incident_repo = incident_repo
        self.audit_repo = audit_repo
        self.csh_repo = csh_repo

    def intake_claim(
        self,
        payload: ClaimIntakeRequest,
        actor_id: str = "CUSTOMER_PORTAL",
        actor_type: ActorType = ActorType.API_SERVICE,
    ) -> Claim:
        """Validate submission integrity, check ownership and duplicates, persist claim and line items."""
        # 1. Customer verification
        customer = self.customer_repo.get_by_id(payload.customer_id)
        if not customer:
            raise CustomerNotFoundError(payload.customer_id)

        # 2. Policy verification
        policy = self.policy_repo.get_by_id(payload.policy_id)
        if not policy:
            raise PolicyNotFoundError(payload.policy_id)

        # 3. Incident verification
        incident = self.incident_repo.get_by_id(payload.incident_id)
        if not incident:
            raise IncidentNotFoundError(payload.incident_id)

        # 4. Ownership verification
        if policy.customer_id != payload.customer_id:
            raise CustomerPolicyMismatchError(
                claim_customer_id=payload.customer_id,
                policy_customer_id=policy.customer_id,
                policy_id=payload.policy_id,
            )

        # 5. Amount validation
        if payload.claimed_amount <= Decimal("0.00"):
            raise InvalidFinancialValueError(
                field_name="claimed_amount",
                value=str(payload.claimed_amount),
                reason="Claimed amount must be greater than zero",
            )

        # 6. Item summation validation
        if payload.line_items:
            items_total = sum(item.total_amount for item in payload.line_items)
            if abs(items_total - payload.claimed_amount) > Decimal("0.01"):
                raise InvalidFinancialValueError(
                    field_name="line_items",
                    value=str(items_total),
                    reason=f"Line items total (${items_total}) does not match claimed amount (${payload.claimed_amount})",
                )

        # 7. Exact duplicate detection
        potential_dups = self.claim_repo.find_potential_duplicates(
            policy_id=payload.policy_id,
            incident_id=payload.incident_id,
            amount=payload.claimed_amount,
        )
        if potential_dups:
            raise DuplicateClaimSubmissionError(
                existing_claim_id=potential_dups[0].id,
                reason="Identical claim already submitted for this policy, incident, and amount",
            )

        # 8. Generate Deterministic ID and persist Claim
        next_seq = self.claim_repo.count() + 1
        claim_id = IdGenerator.claim_id(next_seq)
        now = datetime.now(timezone.utc)

        claim = Claim(
            id=claim_id,
            customer_id=payload.customer_id,
            policy_id=payload.policy_id,
            incident_id=payload.incident_id,
            claim_type=payload.claim_type,
            status=ClaimStatus.SUBMITTED,
            reported_date=payload.reported_date or now,
            claimed_amount=payload.claimed_amount,
            estimated_loss=payload.claimed_amount,
            description=payload.description,
            assigned_adjuster_id=None,
            created_at=now,
            updated_at=now,
        )
        self.claim_repo.create(claim)

        # 9. Persist Line Items
        for seq, item_data in enumerate(payload.line_items, start=1):
            item_id = IdGenerator.claim_item_id(claim_id, seq)
            claim_item = ClaimItem(
                id=item_id,
                claim_id=claim_id,
                coverage_id=None,
                item_description=item_data.item_description,
                quantity=item_data.quantity,
                unit_amount=item_data.unit_amount,
                total_amount=item_data.total_amount,
                created_at=now,
            )
            self.claim_item_repo.create(claim_item)

        # 10. Record Status History
        csh = ClaimStatusHistory(
            id=IdGenerator.claim_status_history_id(claim_id, 1),
            claim_id=claim_id,
            previous_status=None,
            new_status=ClaimStatus.SUBMITTED.value,
            transition_reason="Digital claim intake received and validated.",
            changed_by=actor_id,
            timestamp=now,
        )
        self.csh_repo.create(csh)

        # 11. Record Audit Event
        aud = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Claim",
            entity_id=claim_id,
            action=AuditAction.CLAIM_CREATED,
            state_before=None,
            state_after={
                "status": ClaimStatus.SUBMITTED.value,
                "claimed_amount": str(payload.claimed_amount),
                "claim_type": payload.claim_type.value,
            },
            actor_type=actor_type,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "customer_id": payload.customer_id,
                "policy_id": payload.policy_id,
                "incident_id": payload.incident_id,
            },
        )
        self.audit_repo.create(aud)

        return claim
