from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.adjuster import Adjuster
    from app.models.claim import Claim


class AdjusterAssignment(Base):
    __tablename__ = "adjuster_assignments"

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    adjuster_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("adjusters.id"), nullable=False, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assignment_reason: Mapped[str] = mapped_column(
        String(255), default="Initial assignment", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="adjuster_assignments")
    adjuster: Mapped["Adjuster"] = relationship("Adjuster", back_populates="assignments")
