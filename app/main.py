from contextlib import asynccontextmanager
from typing import Any
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import SessionDep
from app.api.v1 import api_router
from app.api.v1.health import perform_health_check
from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks (e.g. logging startup metadata)
    yield
    # Shutdown cleanup tasks


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description=(
        "Production-grade, end-to-end insurance claims processing and evaluation engine "
        "designed for YottaFlex AI recruitment assessment. Supports intake, document "
        "verification, policy validation, eligibility evaluation, adjuster assignment, "
        "preliminary reserves, settlements, exception handling, audit trails, and synthetic benchmarks."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS middleware for open/extensible frontends or test tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get(
    "/health",
    tags=["System"],
    summary="Global health and database connectivity probe",
)
def health_check(
    db: Session = Depends(get_db),
    response: Response = Response(),
) -> dict[str, Any]:
    """Basic health check and system status probe testing live database connectivity."""
    status_str = "healthy"
    database_status = "healthy"
    if isinstance(db, Session):
        health_data, status_code = perform_health_check(db)
        if response:
            response.status_code = status_code
        status_str = health_data.status
        database_status = health_data.database
    return {
        "status": status_str,
        "database": database_status,
        "service": settings.PROJECT_NAME,
        "version": __version__,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Root endpoint redirecting users to the interactive OpenAPI docs."""
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": f"{settings.API_V1_STR}/docs",
        "health_url": "/health",
    }
