from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.coverage import Coverage
from app.models.enums import CoverageType
from app.repositories.base import BaseRepository


class CoverageRepository(BaseRepository[Coverage]):
    def __init__(self, session: Session) -> None:
        super().__init__(Coverage, session)

    def list_by_policy(self, policy_id: str) -> list[Coverage]:
        """Fetch all coverages attached to a given policy."""
        stmt = select(Coverage).where(Coverage.policy_id == policy_id)
        return list(self.session.scalars(stmt).all())

    def get_by_type(self, policy_id: str, coverage_type: CoverageType) -> Coverage | None:
        """Fetch specific coverage clause for a given policy and type."""
        stmt = select(Coverage).where(
            Coverage.policy_id == policy_id,
            Coverage.coverage_type == coverage_type,
            Coverage.is_active == True,  # noqa: E712
        )
        return self.session.scalars(stmt).first()
