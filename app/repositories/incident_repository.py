from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import IncidentType
from app.models.incident import Incident
from app.repositories.base import BaseRepository


class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session: Session) -> None:
        super().__init__(Incident, session)

    def find_duplicate_incident(
        self,
        occurrence_date: datetime,
        location_city: str,
        location_street: str,
        tolerance_hours: int = 24,
    ) -> Incident | None:
        """Find an existing incident matching the same street, city, and occurrence time window."""
        window_start = occurrence_date - timedelta(hours=tolerance_hours)
        window_end = occurrence_date + timedelta(hours=tolerance_hours)

        stmt = select(Incident).where(
            Incident.location_city.ilike(location_city.strip()),
            Incident.location_street.ilike(location_street.strip()),
            Incident.occurrence_date >= window_start,
            Incident.occurrence_date <= window_end,
        )
        return self.session.scalars(stmt).first()

    def list_by_type(self, incident_type: IncidentType) -> list[Incident]:
        """Fetch incidents filtered by incident type."""
        stmt = select(Incident).where(Incident.incident_type == incident_type)
        return list(self.session.scalars(stmt).all())

