from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ClaimStatus, ClaimType

if TYPE_CHECKING:
    from app.models.adjuster import Adjuster
    from app.models.adjuster_assignment import AdjusterAssignment
    from app.models.assessment import Assessment
    from app.models.claim_item import ClaimItem
    from app.models.claim_status_history import ClaimStatusHistory
    from app.models.customer import Customer
    from app.models.document import Document
    from app.models.incident import Incident
    from app.models.policy import Policy
    from app.models.reserve import Reserve
    from app.models.settlement import Settlement


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("claimed_amount >= 0", name="ck_claim_claimed_amount_positive"),
        CheckConstraint("estimated_loss >= 0", name="ck_claim_estimated_loss_positive"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    customer_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("customers.id"), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(
        String(60), ForeignKey("policies.id"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("incidents.id"), nullable=False, index=True
    )
    claim_type: Mapped[ClaimType] = mapped_column(
        Enum(ClaimType, native_enum=False, length=50), nullable=False, index=True
    )
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, native_enum=False, length=30),
        default=ClaimStatus.SUBMITTED,
        nullable=False,
        index=True,
    )
    reported_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    claimed_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    estimated_loss: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_adjuster_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("adjusters.id"), nullable=True, index=True
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="claims")
    policy: Mapped["Policy"] = relationship("Policy", back_populates="claims")
    incident: Mapped["Incident"] = relationship("Incident", back_populates="claims")
    assigned_adjuster: Mapped["Adjuster | None"] = relationship(
        "Adjuster", back_populates="claims"
    )
    claim_items: Mapped[list["ClaimItem"]] = relationship(
        "ClaimItem", back_populates="claim"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="claim"
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="claim"
    )
    reserves: Mapped[list["Reserve"]] = relationship(
        "Reserve", back_populates="claim"
    )
    settlements: Mapped[list["Settlement"]] = relationship(
        "Settlement", back_populates="claim"
    )
    status_history: Mapped[list["ClaimStatusHistory"]] = relationship(
        "ClaimStatusHistory", back_populates="claim"
    )
    adjuster_assignments: Mapped[list["AdjusterAssignment"]] = relationship(
        "AdjusterAssignment", back_populates="claim"
    )

