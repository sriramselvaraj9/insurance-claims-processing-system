"""Immutable audit trail and regulatory compliance event log endpoints."""

from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.models.enums import AuditAction
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit_schemas import AuditEventResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/audit-events", tags=["Audit"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditEventResponse],
    summary="List immutable system-wide audit events with pagination and filtering",
)
def list_audit_events(
    db: SessionDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    entity_type: Annotated[str | None, Query(description="Filter by entity type (e.g. CLAIM, POLICY)")] = None,
    entity_id: Annotated[str | None, Query(description="Filter by entity ID")] = None,
    action: Annotated[AuditAction | None, Query(description="Filter by specific audit action")] = None,
    start_date: Annotated[datetime | None, Query(description="Filter events after timestamp")] = None,
    end_date: Annotated[datetime | None, Query(description="Filter events before timestamp")] = None,
) -> PaginatedResponse[AuditEventResponse]:
    """Retrieve immutable chronological audit records for regulatory and dispute compliance."""
    repo = AuditRepository(db)
    skip = (page - 1) * page_size
    items, total = repo.list_paginated(
        skip=skip,
        limit=page_size,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
    )
    return PaginatedResponse.create(
        items=[AuditEventResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )
