from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import DocumentRequestStatus, DocumentType

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id: Mapped[str] = mapped_column(String(70), primary_key=True, index=True)
    claim_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("claims.id"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=50), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[DocumentRequestStatus] = mapped_column(
        Enum(DocumentRequestStatus, native_enum=False, length=30),
        default=DocumentRequestStatus.OPEN,
        nullable=False,
    )
    fulfilled_document_id: Mapped[str | None] = mapped_column(
        String(70), ForeignKey("documents.id"), nullable=True, index=True
    )

    # Relationships
    fulfilled_document: Mapped["Document | None"] = relationship(
        "Document", back_populates="document_requests"
    )

