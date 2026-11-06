from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.id_generator import IdGenerator
from app.models.claim_status_history import ClaimStatusHistory
from app.repositories.base import BaseRepository


class ClaimStatusHistoryRepository(BaseRepository[ClaimStatusHistory]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClaimStatusHistory, session)

    def list_by_claim(self, claim_id: str) -> list[ClaimStatusHistory]:
        """Fetch all chronological state transitions for a claim."""
        stmt = (
            select(ClaimStatusHistory)
            .where(ClaimStatusHistory.claim_id == claim_id)
            .order_by(ClaimStatusHistory.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

    get_by_claim_id = list_by_claim

    def record_transition(
        self,
        claim_id: str,
        previous_status: str | None,
        new_status: str,
        reason: str | None = None,
        changed_by: str = "SYSTEM",
    ) -> ClaimStatusHistory:
        """Append an immutable state transition record."""
        count = self.count([ClaimStatusHistory.claim_id == claim_id])
        history_id = IdGenerator.claim_status_history_id(claim_id, count + 1)

        history_entry = ClaimStatusHistory(
            id=history_id,
            claim_id=claim_id,
            previous_status=previous_status,
            new_status=new_status,
            transition_reason=reason,
            changed_by=changed_by,
        )
        return self.create(history_entry)

