from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ReserveCalculationMethod

if TYPE_CHECKING:
    from app.models.claim import Claim


class Reserve(Base):
    __tablename__ = "reserves"
    __table_args__ = (
        CheckConstraint(
            "estimated_indemnity_reserve >= 0",
            name="ck_reserve_indemnity_positive",
        ),
        CheckConstraint(
            "estimated_expense_reserve >= 0",
            name="ck_reserve_expense_positive",
        ),
        CheckConstraint(
            "total_reserve >= 0",
            name="ck_reserve_total_positive",
        ),
    )

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    estimated_indemnity_reserve: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estimated_expense_reserve: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_reserve: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    expense_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.1200")
    )
    calculation_method: Mapped[ReserveCalculationMethod] = mapped_column(
        Enum(ReserveCalculationMethod, native_enum=False, length=50),
        default=ReserveCalculationMethod.FORMULAIC_STANDARD,
        nullable=False,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    calculated_by: Mapped[str] = mapped_column(
        String(100), default="SYSTEM_RULE_RESERVE", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="reserves")

