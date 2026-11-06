from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import IncidentType

if TYPE_CHECKING:
    from app.models.claim import Claim


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_dedup", "occurrence_date", "location_city", "location_street"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    incident_type: Mapped[IncidentType] = mapped_column(
        Enum(IncidentType, native_enum=False, length=50), nullable=False, index=True
    )
    occurrence_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_street: Mapped[str] = mapped_column(String(255), nullable=False)
    location_city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location_state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    location_zip: Mapped[str] = mapped_column(String(20), nullable=False)
    police_report_filed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    police_report_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="incident")

