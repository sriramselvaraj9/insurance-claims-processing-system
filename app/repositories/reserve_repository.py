from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reserve import Reserve
from app.repositories.base import BaseRepository


class ReserveRepository(BaseRepository[Reserve]):
    def __init__(self, session: Session) -> None:
        super().__init__(Reserve, session)

    def get_latest_by_claim(self, claim_id: str) -> Reserve | None:
        """Fetch the latest preliminary reserve calculation for a claim."""
        stmt = (
            select(Reserve)
            .where(Reserve.claim_id == claim_id)
            .order_by(Reserve.calculated_at.desc(), Reserve.id.desc())
        )
        return self.session.scalars(stmt).first()

    def list_by_claim(self, claim_id: str) -> list[Reserve]:
        """Fetch full reserve calculation revision history for a claim."""
        stmt = (
            select(Reserve)
            .where(Reserve.claim_id == claim_id)
            .order_by(Reserve.calculated_at.desc(), Reserve.id.desc())
        )
        return list(self.session.scalars(stmt).all())

    get_by_claim_id = list_by_claim
