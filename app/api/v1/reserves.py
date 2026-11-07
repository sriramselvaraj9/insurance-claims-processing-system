"""Preliminary reserve calculation and revision history endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.repositories.claim_repository import ClaimRepository
from app.repositories.reserve_repository import ReserveRepository
from app.schemas.reserve_schemas import ReserveResponse

router = APIRouter(tags=["Reserves"])


@router.get(
    "/claims/{claim_id}/reserves",
    response_model=list[ReserveResponse],
    summary="Retrieve all reserve calculations and revisions for a claim",
)
def get_claim_reserves(
    claim_id: str,
    db: SessionDep,
) -> list[ReserveResponse]:
    """Retrieve chronological preliminary reserve calculation history for a claim."""
    claim_repo = ClaimRepository(db)
    claim = claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )
    reserve_repo = ReserveRepository(db)
    reserves = reserve_repo.list_by_claim(claim_id)
    return [ReserveResponse.model_validate(r) for r in reserves]


@router.get(
    "/reserves/{reserve_id}",
    response_model=ReserveResponse,
    summary="Retrieve reserve calculation details by ID",
)
def get_reserve(
    reserve_id: str,
    db: SessionDep,
) -> ReserveResponse:
    """Fetch preliminary reserve calculation record by ID."""
    reserve_repo = ReserveRepository(db)
    reserve = reserve_repo.get_by_id(reserve_id)
    if not reserve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserve '{reserve_id}' not found",
        )
    return ReserveResponse.model_validate(reserve)
