from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import PaymentMethod, PaymentStatus

if TYPE_CHECKING:
    from app.models.settlement import Settlement


class SettlementPayment(Base):
    __tablename__ = "settlement_payments"
    __table_args__ = (
        CheckConstraint("payment_amount > 0", name="ck_payment_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    settlement_id: Mapped[str] = mapped_column(
        String(70), ForeignKey("settlements.id"), nullable=False, index=True
    )
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=50),
        default=PaymentMethod.ACH,
        nullable=False,
    )
    payment_reference: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=30),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Relationships
    settlement: Mapped["Settlement"] = relationship(
        "Settlement", back_populates="payments"
    )

