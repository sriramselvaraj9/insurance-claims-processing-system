from typing import Any
from sqlalchemy import select
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
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

