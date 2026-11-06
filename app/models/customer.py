from datetime import date
from typing import TYPE_CHECKING
from sqlalchemy import Date, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import KYCStatus, RiskProfile

if TYPE_CHECKING:
    from app.models.claim import Claim
    from app.models.policy import Policy


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    kyc_status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, native_enum=False, length=30),
        default=KYCStatus.PENDING,
        nullable=False,
    )
    risk_profile: Mapped[RiskProfile] = mapped_column(
        Enum(RiskProfile, native_enum=False, length=20),
        default=RiskProfile.MEDIUM,
        nullable=False,
    )

    # Relationships
    policies: Mapped[list["Policy"]] = relationship(
        "Policy", back_populates="customer"
    )
    claims: Mapped[list["Claim"]] = relationship(
        "Claim", back_populates="customer"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
