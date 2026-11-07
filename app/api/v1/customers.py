"""Customer management and inquiry endpoints."""

import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep
from app.repositories.customer_repository import CustomerRepository
from app.schemas.common import PaginatedResponse
from app.schemas.customer_schemas import CustomerResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List and filter customers with pagination",
)
def list_customers(
    db: SessionDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    kyc_status: Annotated[str | None, Query(description="Filter by KYC status (e.g. PENDING, VERIFIED)")] = None,
    risk_profile: Annotated[str | None, Query(description="Filter by risk profile (LOW, MEDIUM, HIGH)")] = None,
    search: Annotated[str | None, Query(description="Search by name or email")] = None,
) -> PaginatedResponse[CustomerResponse]:
    """Retrieve customers with database-level filtering and pagination."""
    repo = CustomerRepository(db)
    skip = (page - 1) * page_size
    items, total = repo.list_paginated(
        skip=skip,
        limit=page_size,
        kyc_status=kyc_status,
        risk_profile=risk_profile,
        search=search,
    )
    return PaginatedResponse.create(
        items=[CustomerResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve customer profile by ID",
)
def get_customer(
    customer_id: str,
    db: SessionDep,
) -> CustomerResponse:
    """Fetch customer profile by unique customer ID."""
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )
    return CustomerResponse.model_validate(customer)
