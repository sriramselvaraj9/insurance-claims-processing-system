from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.claim import Claim


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    policy_active_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    incident_covered_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timely_filing_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exclusions_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    documentation_complete_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fraud_check_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    decision_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rejection_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    assessed_by: Mapped[str] = mapped_column(
        String(100), default="RULE_ENGINE_V1", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="assessments")

