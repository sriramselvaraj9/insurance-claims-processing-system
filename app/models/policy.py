from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PolicyStatus, PolicyType

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.coverage import Coverage
    from app.models.customer import Customer


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("expiration_date > effective_date", name="ck_policy_dates"),
        CheckConstraint("total_premium >= 0", name="ck_policy_premium_positive"),
        CheckConstraint("deductible >= 0", name="ck_policy_deductible_positive"),
    )

    id: Mapped[str] = mapped_column(String(60), primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.id"), nullable=False, index=True
    )
    policy_type: Mapped[PolicyType] = mapped_column(
        Enum(PolicyType, native_enum=False, length=30), nullable=False, index=True
    )
    status: Mapped[PolicyStatus] = mapped_column(
        Enum(PolicyStatus, native_enum=False, length=30),
        default=PolicyStatus.DRAFT,
        nullable=False,
        index=True,
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date] = mapped_column(Date, nullable=False)
    cancellation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_premium: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    deductible: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("500.00")
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="policies")
    coverages: Mapped[list["Coverage"]] = relationship(
        "Coverage", back_populates="policy"
    )
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="policy")
