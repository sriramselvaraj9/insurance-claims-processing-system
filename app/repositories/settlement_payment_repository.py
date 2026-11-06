from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PaymentStatus
from app.models.settlement_payment import SettlementPayment
from app.repositories.base import BaseRepository


class SettlementPaymentRepository(BaseRepository[SettlementPayment]):
    def __init__(self, session: Session) -> None:
        super().__init__(SettlementPayment, session)

    def get_by_payment_reference(self, reference: str) -> SettlementPayment | None:
        """Fetch payment by unique banking/processor reference."""
        stmt = select(SettlementPayment).where(SettlementPayment.payment_reference == reference)
        return self.session.scalars(stmt).first()

    def list_by_settlement(self, settlement_id: str) -> list[SettlementPayment]:
        """Fetch all payment attempts for a given settlement."""
        stmt = (
            select(SettlementPayment)
            .where(SettlementPayment.settlement_id == settlement_id)
            .order_by(SettlementPayment.payment_date.desc())
        )
        return list(self.session.scalars(stmt).all())

    def has_successful_payment(self, settlement_id: str) -> bool:
        """Check whether a settlement has already been disbursed (prevents duplicate payouts)."""
        stmt = select(SettlementPayment).where(
            SettlementPayment.settlement_id == settlement_id,
            SettlementPayment.status == PaymentStatus.COMPLETED,
        )
        return bool(self.session.scalars(stmt).first())

