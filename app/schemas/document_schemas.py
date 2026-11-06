"""Pydantic schemas for document operations and requests."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentRequestStatus, DocumentType, VerificationStatus


class DocumentCreateRequest(BaseModel):
    document_type: DocumentType
    file_name: str = Field(..., min_length=3, max_length=255)
    file_type: str = Field(..., min_length=3, max_length=100)
    file_path: str = Field(..., min_length=3, max_length=500)
    file_size_bytes: int = Field(..., gt=0)
    checksum_sha256: str = Field(..., min_length=64, max_length=64)


class DocumentVerifyRequest(BaseModel):
    verification_status: VerificationStatus
    verified_by: str = Field(..., min_length=2, max_length=100)
    rejection_reason: str | None = None


class DocumentResponse(BaseModel):
    id: str
    claim_id: str
    document_type: DocumentType
    file_name: str
    file_type: str
    file_path: str
    file_size_bytes: int
    checksum_sha256: str
    submission_date: datetime
    verification_status: VerificationStatus
    verified_at: datetime | None
    verified_by: str | None
    rejection_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class DocumentRequestResponse(BaseModel):
    id: str
    claim_id: str
    document_type: DocumentType
    requested_at: datetime
    status: DocumentRequestStatus
    fulfilled_document_id: str | None

    model_config = ConfigDict(from_attributes=True)
