from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AdjusterSpecialization, AdjusterStatus

if TYPE_CHECKING:
    from app.models.adjuster_assignment import AdjusterAssignment
    from app.models.claim import Claim


class Adjuster(Base, TimestampMixin):
    __tablename__ = "adjusters"
    __table_args__ = (
        CheckConstraint("active_claims_count >= 0", name="ck_adjuster_active_claims_positive"),
        CheckConstraint("max_capacity > 0", name="ck_adjuster_capacity_positive"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    specialization: Mapped[AdjusterSpecialization] = mapped_column(
        Enum(AdjusterSpecialization, native_enum=False, length=50),
        nullable=False,
        index=True,
    )
    active_claims_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    max_capacity: Mapped[int] = mapped_column(
        Integer, default=20, nullable=False
    )
    status: Mapped[AdjusterStatus] = mapped_column(
        Enum(AdjusterStatus, native_enum=False, length=30),
        default=AdjusterStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Relationships
    claims: Mapped[list["Claim"]] = relationship(
        "Claim", back_populates="assigned_adjuster"
    )
    assignments: Mapped[list["AdjusterAssignment"]] = relationship(
        "AdjusterAssignment", back_populates="adjuster"
    )

    @property
    def has_capacity(self) -> bool:
        return self.status == AdjusterStatus.ACTIVE and self.active_claims_count < self.max_capacity
