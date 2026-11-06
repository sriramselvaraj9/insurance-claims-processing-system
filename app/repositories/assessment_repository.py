from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.repositories.base import BaseRepository


class AssessmentRepository(BaseRepository[Assessment]):
    def __init__(self, session: Session) -> None:
        super().__init__(Assessment, session)

    def get_latest_by_claim(self, claim_id: str) -> Assessment | None:
        """Fetch the most recent eligibility assessment for a claim."""
        stmt = (
            select(Assessment)
            .where(Assessment.claim_id == claim_id)
            .order_by(Assessment.assessed_at.desc(), Assessment.id.desc())
        )
        return self.session.scalars(stmt).first()

    def list_by_claim(self, claim_id: str) -> list[Assessment]:
        """Fetch all assessments and reassessments for a claim."""
        stmt = (
            select(Assessment)
            .where(Assessment.claim_id == claim_id)
            .order_by(Assessment.assessed_at.desc(), Assessment.id.desc())
        )
        return list(self.session.scalars(stmt).all())
