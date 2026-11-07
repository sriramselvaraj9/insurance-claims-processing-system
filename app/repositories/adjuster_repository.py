from sqlalchemy import func, select
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

    def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        specialization: AdjusterSpecialization | None = None,
        status: AdjusterStatus | None = None,
    ) -> tuple[list[Adjuster], int]:
        """Fetch paginated adjusters with database-level filtering."""
        stmt = select(Adjuster)
        count_stmt = select(func.count()).select_from(Adjuster)

        filters = []
        if specialization:
            filters.append(Adjuster.specialization == specialization)
        if status:
            filters.append(Adjuster.status == status)

        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = self.session.scalar(count_stmt) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(Adjuster.active_claims_count.asc(), Adjuster.id.asc()).offset(skip).limit(limit)
            ).all()
        )
        return items, total

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

    def find_available_by_specialization(self, specialization: AdjusterSpecialization) -> list[Adjuster]:
        """Fetch active adjusters matching specialization who are below max caseload capacity."""
        stmt = (
            select(Adjuster)
            .where(
                Adjuster.specialization == specialization,
                Adjuster.status == AdjusterStatus.ACTIVE,
                Adjuster.active_claims_count < Adjuster.max_capacity,
            )
            .order_by(Adjuster.active_claims_count.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_all_active(self) -> list[Adjuster]:
        """Fetch all currently active adjusters."""
        stmt = (
            select(Adjuster)
            .where(Adjuster.status == AdjusterStatus.ACTIVE)
            .order_by(Adjuster.active_claims_count.asc())
        )
        return list(self.session.scalars(stmt).all())

