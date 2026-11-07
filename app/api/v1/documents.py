"""Document submission, verification, and missing evidence request endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, get_document_service
from app.core.database import get_db
from app.repositories.claim_repository import ClaimRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_request_repository import DocumentRequestRepository
from app.schemas.document_schemas import (
    DocumentCreateRequest,
    DocumentRequestCreate,
    DocumentRequestResponse,
    DocumentResponse,
    DocumentVerifyRequest,
)
from app.services.document_service import DocumentService

router = APIRouter(tags=["Documents"])


@router.post(
    "/claims/{claim_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or attach evidentiary document to claim",
)
def attach_document(
    claim_id: str,
    payload: DocumentCreateRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Session | None = Depends(get_db),
) -> DocumentResponse:
    """Attach evidentiary document and fulfill matching open DocumentRequests."""
    if isinstance(db, Session):
        claim_repo = ClaimRepository(db)
        if not claim_repo.get_by_id(claim_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim '{claim_id}' not found",
            )
    doc = service.attach_document(claim_id=claim_id, payload=payload)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/claims/{claim_id}/documents",
    response_model=list[DocumentResponse],
    summary="List all documents submitted for a claim",
)
def list_claim_documents(
    claim_id: str,
    db: SessionDep,
) -> list[DocumentResponse]:
    """Retrieve all evidentiary files attached to a claim."""
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )
    repo = DocumentRepository(db)
    docs = repo.get_by_claim_id(claim_id)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.post(
    "/documents/{document_id}/verify",
    response_model=DocumentResponse,
    summary="Verify or reject a submitted document",
)
@router.patch(
    "/documents/{document_id}/verification",
    response_model=DocumentResponse,
    summary="Update document verification status (PATCH)",
)
def verify_document(
    document_id: str,
    payload: DocumentVerifyRequest,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    """Update document verification status."""
    try:
        doc = service.verify_document(
            document_id=document_id,
            status=payload.verification_status,
            verified_by=payload.verified_by,
            rejection_reason=payload.rejection_reason,
        )
        return DocumentResponse.model_validate(doc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/claims/{claim_id}/document-requests",
    response_model=list[DocumentRequestResponse],
    summary="List missing document requests for a claim",
)
def list_document_requests(
    claim_id: str,
    db: SessionDep,
) -> list[DocumentRequestResponse]:
    """Retrieve open and fulfilled document requests."""
    claim_repo = ClaimRepository(db)
    if not claim_repo.get_by_id(claim_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' not found",
        )
    repo = DocumentRequestRepository(db)
    requests = repo.get_by_claim_id(claim_id)
    return [DocumentRequestResponse.model_validate(r) for r in requests]


@router.post(
    "/claims/{claim_id}/document-requests",
    response_model=DocumentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new formal missing document request for a claim",
)
def create_document_request(
    claim_id: str,
    payload: DocumentRequestCreate,
    service: Annotated[DocumentService, Depends(get_document_service)],
    db: Session | None = Depends(get_db),
) -> DocumentRequestResponse:
    """Manually initiate a formal document request for a claim."""
    if isinstance(db, Session):
        claim_repo = ClaimRepository(db)
        if not claim_repo.get_by_id(claim_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim '{claim_id}' not found",
            )
    doc_req = service.create_document_request(
        claim_id=claim_id,
        document_type=payload.document_type,
    )
    return DocumentRequestResponse.model_validate(doc_req)
