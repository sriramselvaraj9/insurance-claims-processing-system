"""Policy and coverage inquiry endpoints."""

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep
from app.models.enums import PolicyStatus, PolicyType
from app.repositories.coverage_repository import CoverageRepository
from app.repositories.policy_repository import PolicyRepository
from app.schemas.common import PaginatedResponse
from app.schemas.policy_schemas import CoverageResponse, PolicyResponse

router = APIRouter(prefix="/policies", tags=["Policies"])


@router.get(
    "",
    response_model=PaginatedResponse[PolicyResponse],
    summary="List policies with database-level pagination and filtering",
)
def list_policies(
    db: SessionDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    customer_id: Annotated[str | None, Query(description="Filter by customer ID")] = None,
    status: Annotated[PolicyStatus | None, Query(description="Filter by policy status")] = None,
    policy_type: Annotated[PolicyType | None, Query(description="Filter by policy type")] = None,
) -> PaginatedResponse[PolicyResponse]:
    """Retrieve policies with database-level pagination and filtering."""
    repo = PolicyRepository(db)
    skip = (page - 1) * page_size
    items, total = repo.list_paginated(
        skip=skip,
        limit=page_size,
        customer_id=customer_id,
        status=status,
        policy_type=policy_type,
    )
    return PaginatedResponse.create(
        items=[PolicyResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Retrieve policy details including coverages by policy ID",
)
def get_policy(
    policy_id: str,
    db: SessionDep,
) -> PolicyResponse:
    """Fetch policy details with eagerly loaded coverages."""
    repo = PolicyRepository(db)
    policy = repo.get_with_coverages(policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found",
        )
    return PolicyResponse.model_validate(policy)


@router.get(
    "/{policy_id}/coverages",
    response_model=list[CoverageResponse],
    summary="List all coverages attached to a specific policy",
)
def list_policy_coverages(
    policy_id: str,
    db: SessionDep,
) -> list[CoverageResponse]:
    """Retrieve all coverage terms attached to a policy."""
    policy_repo = PolicyRepository(db)
    policy = policy_repo.get_by_id(policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found",
        )
    coverage_repo = CoverageRepository(db)
    coverages = coverage_repo.list_by_policy(policy_id)
    return [CoverageResponse.model_validate(c) for c in coverages]
