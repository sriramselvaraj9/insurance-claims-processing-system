from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.adjuster import Adjuster
from app.models.enums import AdjusterSpecialization, AdjusterStatus
from app.repositories.base import BaseRepository


class AdjusterRepository(BaseRepository[Adjuster]):
    def __init__(self, session: Session) -> None:
        super().__init__(Adjuster, session)

    def get_by_employee_id(self, employee_id: str) -> Adjuster | None:
        """Find an adjuster by internal corporate employee ID."""
        stmt = select(Adjuster).where(Adjuster.employee_id == employee_id)
        return self.session.scalars(stmt).first()

    def find_least_loaded_adjuster(
        self, specialization: AdjusterSpecialization
    ) -> Adjuster | None:
        """Find the active adjuster matching specialization with lowest current active load under max capacity."""
        # Try matching exact specialization first
        stmt = (
            select(Adjuster)
            .where(
                Adjuster.specialization == specialization,
                Adjuster.status == AdjusterStatus.ACTIVE,
                Adjuster.active_claims_count < Adjuster.max_capacity,
            )
            .order_by(Adjuster.active_claims_count.asc())
        )
        adjuster = self.session.scalars(stmt).first()

        # Fallback to GENERAL specialization if no domain specialist available
        if not adjuster and specialization != AdjusterSpecialization.GENERAL:
            fallback_stmt = (
                select(Adjuster)
                .where(
                    Adjuster.specialization == AdjusterSpecialization.GENERAL,
                    Adjuster.status == AdjusterStatus.ACTIVE,
                    Adjuster.active_claims_count < Adjuster.max_capacity,
                )
                .order_by(Adjuster.active_claims_count.asc())
            )
            adjuster = self.session.scalars(fallback_stmt).first()

        return adjuster

    def increment_load(self, adjuster_id: str) -> None:
        """Increment active claim count by 1."""
        adjuster = self.get_by_id(adjuster_id)
        if adjuster:
            adjuster.active_claims_count += 1
            self.session.flush()

    def decrement_load(self, adjuster_id: str) -> None:
        """Decrement active claim count by 1."""
        adjuster = self.get_by_id(adjuster_id)
        if adjuster and adjuster.active_claims_count > 0:
            adjuster.active_claims_count -= 1
            self.session.flush()
