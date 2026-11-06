from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from sqlalchemy import Boolean, CheckConstraint, Date, Enum, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CoverageType

if TYPE_CHECKING:
    from app.models.claim_item import ClaimItem
    from app.models.policy import Policy


class Coverage(Base, TimestampMixin):
    __tablename__ = "coverages"
    __table_args__ = (
        CheckConstraint("coverage_limit > 0", name="ck_coverage_limit_positive"),
        CheckConstraint("deductible >= 0", name="ck_coverage_deductible_positive"),
        CheckConstraint(
            "copay_percentage >= 0 AND copay_percentage <= 100",
            name="ck_coverage_copay_range",
        ),
        CheckConstraint(
            "expiration_date >= effective_date",
            name="ck_coverage_period_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    policy_id: Mapped[str] = mapped_column(
        String(60), ForeignKey("policies.id"), nullable=False, index=True
    )
    coverage_type: Mapped[CoverageType] = mapped_column(
        Enum(CoverageType, native_enum=False, length=50), nullable=False, index=True
    )
    coverage_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deductible: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("500.00")
    )
    copay_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    exclusions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="coverages")
    claim_items: Mapped[list["ClaimItem"]] = relationship(
        "ClaimItem", back_populates="coverage"
    )

