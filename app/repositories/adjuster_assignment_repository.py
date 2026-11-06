from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.adjuster_assignment import AdjusterAssignment
from app.repositories.base import BaseRepository


class AdjusterAssignmentRepository(BaseRepository[AdjusterAssignment]):
    def __init__(self, session: Session) -> None:
        super().__init__(AdjusterAssignment, session)

    def get_active_assignment(self, claim_id: str) -> AdjusterAssignment | None:
        """Fetch the current active adjuster assignment for a claim."""
        stmt = select(AdjusterAssignment).where(
            AdjusterAssignment.claim_id == claim_id,
            AdjusterAssignment.is_active == True,  # noqa: E712
        )
        return self.session.scalars(stmt).first()

    def list_by_claim(self, claim_id: str) -> list[AdjusterAssignment]:
        """Fetch complete assignment and reassignment history for a claim."""
        stmt = (
            select(AdjusterAssignment)
            .where(AdjusterAssignment.claim_id == claim_id)
            .order_by(AdjusterAssignment.assigned_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def deactivate_current_assignments(self, claim_id: str) -> None:
        """Mark any active assignment as inactive when reassigning."""
        current = self.get_active_assignment(claim_id)
        if current:
            current.is_active = False
            current.unassigned_at = datetime.now(timezone.utc)
            self.session.flush()
