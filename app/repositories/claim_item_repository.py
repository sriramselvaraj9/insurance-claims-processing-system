from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.claim_item import ClaimItem
from app.repositories.base import BaseRepository


class ClaimItemRepository(BaseRepository[ClaimItem]):
    def __init__(self, session: Session) -> None:
        super().__init__(ClaimItem, session)

    def list_by_claim(self, claim_id: str) -> list[ClaimItem]:
        """Fetch all itemized loss items for a given claim."""
        stmt = select(ClaimItem).where(ClaimItem.claim_id == claim_id)
        return list(self.session.scalars(stmt).all())

    def compute_total_claim_loss(self, claim_id: str) -> Decimal:
        """Sum total itemized amounts for a given claim."""
        stmt = select(func.sum(ClaimItem.total_amount)).where(ClaimItem.claim_id == claim_id)
        result = self.session.scalar(stmt)
        return result or Decimal("0.00")
