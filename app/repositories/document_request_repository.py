from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_request import DocumentRequest
from app.models.enums import DocumentRequestStatus
from app.repositories.base import BaseRepository


class DocumentRequestRepository(BaseRepository[DocumentRequest]):
    def __init__(self, session: Session) -> None:
        super().__init__(DocumentRequest, session)

    def list_open_by_claim(self, claim_id: str) -> list[DocumentRequest]:
        """Fetch all unfulfilled/open document requests for a claim (NEG-04)."""
        stmt = select(DocumentRequest).where(
            DocumentRequest.claim_id == claim_id,
            DocumentRequest.status == DocumentRequestStatus.OPEN,
        )
        return list(self.session.scalars(stmt).all())

    def fulfill_request(self, request_id: str, document_id: str) -> DocumentRequest | None:
        """Mark an open document request as fulfilled with the uploaded document."""
        req = self.get_by_id(request_id)
        if req:
            req.status = DocumentRequestStatus.FULFILLED
            req.fulfilled_document_id = document_id
            self.session.flush()
        return req
