from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Enum, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ActorType, AuditAction


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=30), nullable=False, index=True
    )
    state_before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    state_after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, native_enum=False, length=30), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON, nullable=True
    )

