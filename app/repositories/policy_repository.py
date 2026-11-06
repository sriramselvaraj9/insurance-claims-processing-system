from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import PolicyStatus
from app.models.policy import Policy
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[Policy]):
    def __init__(self, session: Session) -> None:
        super().__init__(Policy, session)

    def list_by_customer(self, customer_id: str) -> list[Policy]:
        """Fetch all policies belonging to a specific customer."""
        stmt = select(Policy).where(Policy.customer_id == customer_id).order_by(Policy.created_at.desc())
        return list(self.session.scalars(stmt).all())

    def list_active(self, skip: int = 0, limit: int = 100) -> list[Policy]:
        """Fetch all active policies."""
        stmt = (
            select(Policy)
            .where(Policy.status == PolicyStatus.ACTIVE)
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_with_coverages(self, policy_id: str) -> Policy | None:
        """Fetch policy eagerly loading attached coverages."""
        stmt = (
            select(Policy)
            .where(Policy.id == policy_id)
            .options(selectinload(Policy.coverages))
        )
        return self.session.scalars(stmt).first()

