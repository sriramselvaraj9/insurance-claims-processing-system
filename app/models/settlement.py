from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SettlementStatus

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.settlement_payment import SettlementPayment


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("recommended_amount >= 0", name="ck_settlement_recommended_positive"),
        CheckConstraint("deductible_applied >= 0", name="ck_settlement_deductible_positive"),
        CheckConstraint("copay_applied >= 0", name="ck_settlement_copay_positive"),
        CheckConstraint("net_settlement_amount >= 0", name="ck_settlement_net_positive"),
    )

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    recommended_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    approved_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    deductible_applied: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    copay_applied: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    net_settlement_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus, native_enum=False, length=30),
        default=SettlementStatus.PROPOSED,
        nullable=False,
        index=True,
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    settled_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="settlements")
    payments: Mapped[list["SettlementPayment"]] = relationship(
        "SettlementPayment", back_populates="settlement"
    )

