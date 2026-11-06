"""Document submission, verification, and missing evidence request endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import SessionDep, get_document_service
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_request_repository import DocumentRequestRepository
from app.schemas.document_schemas import (
    DocumentCreateRequest,
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
) -> DocumentResponse:
    """Attach evidentiary document and fulfill matching open DocumentRequests."""
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
    repo = DocumentRepository(db)
    docs = repo.get_by_claim_id(claim_id)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.post(
    "/documents/{document_id}/verify",
    response_model=DocumentResponse,
    summary="Verify or reject a submitted document",
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
    repo = DocumentRequestRepository(db)
    requests = repo.get_by_claim_id(claim_id)
    return [DocumentRequestResponse.model_validate(r) for r in requests]
