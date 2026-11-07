"""Eligibility assessment inquiry endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.repositories.assessment_repository import AssessmentRepository
from app.schemas.assessment_schemas import AssessmentResponse

router = APIRouter(prefix="/assessments", tags=["Assessments"])


@router.get(
    "/{assessment_id}",
    response_model=AssessmentResponse,
    summary="Retrieve single eligibility assessment details by ID",
)
def get_assessment(
    assessment_id: str,
    db: SessionDep,
) -> AssessmentResponse:
    """Fetch eligibility assessment by ID."""
    repo = AssessmentRepository(db)
    assessment = repo.get_by_id(assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{assessment_id}' not found",
        )
    return AssessmentResponse.model_validate(assessment)
