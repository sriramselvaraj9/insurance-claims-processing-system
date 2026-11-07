from datetime import datetime
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.enums import ActorType, AuditAction
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(AuditEvent, session)

    def log_event(
        self,
        entity_type: str,
        entity_id: str,
        action: AuditAction,
        actor_id: str,
        actor_type: ActorType = ActorType.SYSTEM_RULE,
        state_before: dict[str, Any] | None = None,
        state_after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create and append an immutable audit event record."""
        total_events = self.count()
        event_id = IdGenerator.audit_event_id(total_events + 1)

        event = AuditEvent(
            id=event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            state_before=state_before,
            state_after=state_after,
            metadata_=metadata,
        )
        return self.create(event)

    def list_by_entity(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        """Fetch all chronological audit logs for a specific entity instance."""
        stmt = (
            select(AuditEvent)
            .where(
                func.upper(AuditEvent.entity_type) == entity_type.upper(),
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

    get_by_entity = list_by_entity

    def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: AuditAction | str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[AuditEvent], int]:
        """Fetch paginated audit events with database-level filtering."""
        stmt = select(AuditEvent)
        count_stmt = select(func.count()).select_from(AuditEvent)

        filters = []
        if entity_type:
            filters.append(func.upper(AuditEvent.entity_type) == entity_type.upper())
        if entity_id:
            filters.append(AuditEvent.entity_id == entity_id)
        if action:
            act_val = action.value if hasattr(action, "value") else str(action)
            filters.append(AuditEvent.action == act_val)
        if start_date:
            filters.append(AuditEvent.timestamp >= start_date)
        if end_date:
            filters.append(AuditEvent.timestamp <= end_date)

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.session.scalar(count_stmt) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc()).offset(skip).limit(limit)
            ).all()
        )
        return items, total

