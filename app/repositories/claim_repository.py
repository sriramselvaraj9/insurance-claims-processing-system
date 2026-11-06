from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.claim import Claim
from app.models.enums import ClaimStatus
from app.repositories.base import BaseRepository


class ClaimRepository(BaseRepository[Claim]):
    def __init__(self, session: Session) -> None:
        super().__init__(Claim, session)

    def list_by_customer(self, customer_id: str) -> list[Claim]:
        """Fetch all claims submitted by a customer."""
        stmt = select(Claim).where(Claim.customer_id == customer_id).order_by(Claim.reported_date.desc())
        return list(self.session.scalars(stmt).all())

    def list_by_policy(self, policy_id: str) -> list[Claim]:
        """Fetch all claims tied to a policy."""
        stmt = select(Claim).where(Claim.policy_id == policy_id).order_by(Claim.reported_date.desc())
        return list(self.session.scalars(stmt).all())

    def list_by_status(self, status: ClaimStatus, skip: int = 0, limit: int = 100) -> list[Claim]:
        """List claims filtered by lifecycle state."""
        stmt = (
            select(Claim)
            .where(Claim.status == status)
            .order_by(Claim.reported_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_with_details(self, claim_id: str) -> Claim | None:
        """Fetch claim eagerly loading all child domain entities."""
        stmt = (
            select(Claim)
            .where(Claim.id == claim_id)
            .options(
                selectinload(Claim.customer),
                selectinload(Claim.policy),
                selectinload(Claim.incident),
                selectinload(Claim.claim_items),
                selectinload(Claim.documents),
                selectinload(Claim.assessments),
                selectinload(Claim.reserves),
                selectinload(Claim.settlements),
                selectinload(Claim.assigned_adjuster),
            )
        )
        return self.session.scalars(stmt).first()

    def find_potential_duplicates(
        self,
        policy_id: str,
        incident_id: str,
        claimed_amount: Decimal,
        exclude_claim_id: str | None = None,
    ) -> list[Claim]:
        """Identify potential duplicate claims for the same policy and incident (NEG-06 check)."""
        stmt = select(Claim).where(
            Claim.policy_id == policy_id,
            Claim.incident_id == incident_id,
            Claim.claimed_amount == claimed_amount,
        )
        if exclude_claim_id:
            stmt = stmt.where(Claim.id != exclude_claim_id)
        return list(self.session.scalars(stmt).all())

