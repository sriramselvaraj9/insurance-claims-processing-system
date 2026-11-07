"""Health and system probe endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import SessionDep
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["System"])


def perform_health_check(db: Session) -> tuple[HealthResponse, int]:
    """Perform live probe on database connectivity and runtime status."""
    db_ok = False
    try:
        db.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False

    resp = HealthResponse(
        service=settings.PROJECT_NAME,
        version=__version__,
        status="healthy" if db_ok else "unhealthy",
        database="connected" if db_ok else "disconnected",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )
    http_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return resp, http_code


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API v1 health and database readiness probe",
)
def api_v1_health(db: SessionDep, response: Response) -> HealthResponse:
    """Check API v1 service and underlying database connectivity."""
    health_data, status_code = perform_health_check(db)
    response.status_code = status_code
    return health_data
