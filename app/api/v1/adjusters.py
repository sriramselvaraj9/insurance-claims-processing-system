"""Adjuster directory, profile, and claim assignment audit endpoints."""

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.models.enums import AdjusterSpecialization, AdjusterStatus
from app.repositories.adjuster_assignment_repository import AdjusterAssignmentRepository
from app.repositories.adjuster_repository import AdjusterRepository
from app.repositories.claim_repository import ClaimRepository
from app.schemas.adjuster_schemas import AdjusterAssignmentResponse, AdjusterResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["Adjusters"])


@router.get(
    "/adjusters",
    response_model=PaginatedResponse[AdjusterResponse],
    summary="List adjusters with database-level pagination and filtering",
)
def list_adjusters(
    db: SessionDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    specialization: Annotated[AdjusterSpecialization | None, Query(description="Filter by specialization")] = None,
    status: Annotated[AdjusterStatus | None, Query(description="Filter by adjuster status")] = None,
) -> PaginatedResponse[AdjusterResponse]:
    """Retrieve adjusters with database-level pagination and filtering."""
    repo = AdjusterRepository(db)
    skip = (page - 1) * page_size
    items, total = repo.list_paginated(
        skip=skip,
        limit=page_size,
        specialization=specialization,
        status=status,
    )
    return PaginatedResponse.create(
        items=[AdjusterResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/adjusters/{adjuster_id}",
    response_model=AdjusterResponse,
    summary="Retrieve adjuster profile and capacity details",
)
def get_adjuster(
    adjuster_id: str,
    db: SessionDep,
) -> AdjusterResponse:
    """Fetch adjuster profile by ID."""
    repo = AdjusterRepository(db)
    adjuster = repo.get_by_id(adjuster_id)
    if not adjuster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adjuster '{adjuster_id}' not found",
        )
    return AdjusterResponse.model_validate(adjuster)


@router.get(
    "/claims/{claim_id}/adjustments",
    response_model=list[AdjusterAssignmentResponse],
    summary="Retrieve adjuster assignment history for a claim",
)
def get_claim_adjuster_assignments(
    claim_id: str,
    db: SessionDep,
) -> list[AdjusterAssignmentResponse]:
    """Fetch all chronological adjuster assignments and reassignments for a claim."""
    claim_repo = ClaimRepository(db)
    claim = claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )
    assignment_repo = AdjusterAssignmentRepository(db)
    assignments = assignment_repo.list_by_claim(claim_id)
    return [AdjusterAssignmentResponse.model_validate(a) for a in assignments]
