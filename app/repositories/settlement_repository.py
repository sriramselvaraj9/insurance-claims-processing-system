from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SettlementStatus
from app.models.settlement import Settlement
from app.repositories.base import BaseRepository


class SettlementRepository(BaseRepository[Settlement]):
    def __init__(self, session: Session) -> None:
        super().__init__(Settlement, session)

    def get_by_claim(self, claim_id: str) -> Settlement | None:
        """Fetch the settlement associated with a claim."""
        stmt = (
            select(Settlement)
            .where(Settlement.claim_id == claim_id)
            .order_by(Settlement.created_at.desc())
        )
        return self.session.scalars(stmt).first()

    def list_by_status(self, status: SettlementStatus, skip: int = 0, limit: int = 100) -> list[Settlement]:
        """List settlements filtered by adjudication state."""
        stmt = (
            select(Settlement)
            .where(Settlement.status == status)
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_with_payments(self, settlement_id: str) -> Settlement | None:
        """Fetch settlement with payment disbursement history."""
        stmt = (
            select(Settlement)
            .where(Settlement.id == settlement_id)
            .options(selectinload(Settlement.payments))
        )
        return self.session.scalars(stmt).first()
