from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.coverage import Coverage


class ClaimItem(Base):
    __tablename__ = "claim_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_claim_item_quantity_positive"),
        CheckConstraint("unit_amount >= 0", name="ck_claim_item_unit_amount_positive"),
        CheckConstraint("total_amount >= 0", name="ck_claim_item_total_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    coverage_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("coverages.id"), nullable=True, index=True
    )
    item_description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="claim_items")
    coverage: Mapped["Coverage | None"] = relationship(
        "Coverage", back_populates="claim_items"
    )

