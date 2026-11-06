from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.enums import DocumentType, VerificationStatus
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: Session) -> None:
        super().__init__(Document, session)

    def list_by_claim(self, claim_id: str) -> list[Document]:
        """Fetch all evidentiary documents linked to a claim."""
        stmt = select(Document).where(Document.claim_id == claim_id).order_by(Document.submission_date.desc())
        return list(self.session.scalars(stmt).all())

    get_by_claim_id = list_by_claim

    def get_by_checksum(self, checksum_sha256: str) -> Document | None:
        """Find a document matching an exact SHA-256 cryptographic digest."""
        stmt = select(Document).where(Document.checksum_sha256 == checksum_sha256)
        return self.session.scalars(stmt).first()

    def list_verified_by_type(self, claim_id: str, document_type: DocumentType) -> list[Document]:
        """Fetch verified documents of a specific type for a claim."""
        stmt = select(Document).where(
            Document.claim_id == claim_id,
            Document.document_type == document_type,
            Document.verification_status == VerificationStatus.VERIFIED,
        )
        return list(self.session.scalars(stmt).all())

