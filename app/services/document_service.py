"""Document management and verification service.

Identifies mandatory documents by claim type, checks verification status,
emits DocumentRequests for missing evidence, and maintains audit trails.
"""

from datetime import datetime, timezone
from dataclasses import dataclass

from app.core.id_generator import IdGenerator
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.document import Document
from app.models.document_request import DocumentRequest
from app.models.enums import (
    ActorType,
    AuditAction,
    DocumentRequestStatus,
    DocumentType,
    VerificationStatus,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_request_repository import DocumentRequestRepository
from app.rules.document_rules import check_document_completeness, get_mandatory_documents
from app.rules.rule_base import RuleResult
from app.schemas.document_schemas import DocumentCreateRequest


@dataclass(frozen=True)
class DocumentVerificationResult:
    is_complete: bool
    mandatory_document_types: list[DocumentType]
    missing_document_types: list[DocumentType]
    unverified_document_types: list[DocumentType]
    created_document_requests: list[DocumentRequest]
    rule_results: list[RuleResult]
    reasons: list[str]


class DocumentService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        doc_req_repo: DocumentRequestRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.doc_repo = doc_repo
        self.doc_req_repo = doc_req_repo
        self.audit_repo = audit_repo

    def verify_claim_documents(
        self,
        claim: Claim,
        actor_id: str = "DOCUMENT_VERIFICATION_ENGINE",
    ) -> DocumentVerificationResult:
        """Verify all mandatory documents, emitting DocumentRequests for missing evidence."""
        existing_docs = self.doc_repo.get_by_claim_id(claim.id)
        doc_tuples = [(d.document_type, d.verification_status) for d in existing_docs]

        check_result = check_document_completeness(claim.claim_type, doc_tuples)
        mandatory = get_mandatory_documents(claim.claim_type)

        created_requests: list[DocumentRequest] = []
        now = datetime.now(timezone.utc)

        # Emit DocumentRequest for any missing mandatory document if not already requested
        existing_requests = self.doc_req_repo.get_open_by_claim_id(claim.id)
        existing_req_types = {r.document_type for r in existing_requests}

        for missing_type in check_result.missing_document_types:
            if missing_type not in existing_req_types:
                seq = self.doc_req_repo.count() + 1
                req_id = IdGenerator.document_request_id(claim.id, seq)
                doc_req = DocumentRequest(
                    id=req_id,
                    claim_id=claim.id,
                    document_type=missing_type,
                    requested_at=now,
                    status=DocumentRequestStatus.OPEN,
                    fulfilled_document_id=None,
                )
                self.doc_req_repo.create(doc_req)
                created_requests.append(doc_req)

                # Record DOCUMENT_REQUESTED audit event
                audit_req = AuditEvent(
                    id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
                    entity_type="DocumentRequest",
                    entity_id=req_id,
                    action=AuditAction.DOCUMENT_REQUESTED,
                    state_before=None,
                    state_after={"status": DocumentRequestStatus.OPEN.value, "document_type": missing_type.value},
                    actor_type=ActorType.SYSTEM_RULE,
                    actor_id=actor_id,
                    timestamp=now,
                    metadata_={"claim_id": claim.id, "missing_document_type": missing_type.value},
                )
                self.audit_repo.create(audit_req)

        # Record overall DOCUMENT_VERIFIED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Claim",
            entity_id=claim.id,
            action=AuditAction.DOCUMENT_VERIFIED,
            state_before=None,
            state_after={
                "is_complete": check_result.is_complete,
                "missing_count": len(check_result.missing_document_types),
                "unverified_count": len(check_result.unverified_document_types),
            },
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "missing": [m.value for m in check_result.missing_document_types],
                "unverified": [u.value for u in check_result.unverified_document_types],
            },
        )
        self.audit_repo.create(audit_event)

        return DocumentVerificationResult(
            is_complete=check_result.is_complete,
            mandatory_document_types=mandatory,
            missing_document_types=check_result.missing_document_types,
            unverified_document_types=check_result.unverified_document_types,
            created_document_requests=created_requests,
            rule_results=check_result.rule_results,
            reasons=check_result.reasons,
        )

    def attach_document(
        self,
        claim_id: str,
        payload: DocumentCreateRequest,
        actor_id: str = "CUSTOMER_PORTAL",
    ) -> Document:
        """Attach a new evidentiary document to a claim, fulfilling open requests if matched."""
        seq = self.doc_repo.count() + 1
        doc_id = IdGenerator.document_id(claim_id, seq)
        now = datetime.now(timezone.utc)

        doc = Document(
            id=doc_id,
            claim_id=claim_id,
            document_type=payload.document_type,
            file_name=payload.file_name,
            file_type=payload.file_type,
            file_path=payload.file_path,
            file_size_bytes=payload.file_size_bytes,
            checksum_sha256=payload.checksum_sha256,
            submission_date=now,
            verification_status=VerificationStatus.PENDING,
            verified_at=None,
            verified_by=None,
            rejection_reason=None,
            created_at=now,
        )
        self.doc_repo.create(doc)

        # Fulfill matching open DocumentRequest
        open_requests = self.doc_req_repo.get_open_by_claim_id(claim_id)
        for req in open_requests:
            if req.document_type == payload.document_type:
                req.status = DocumentRequestStatus.FULFILLED
                req.fulfilled_document_id = doc_id
                self.doc_req_repo.update(req)
                break

        return doc

    def verify_document(
        self,
        document_id: str,
        status: VerificationStatus,
        verified_by: str,
        rejection_reason: str | None = None,
    ) -> Document:
        """Update verification status of an existing document."""
        doc = self.doc_repo.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Document '{document_id}' not found")

        doc.verification_status = status
        doc.verified_by = verified_by
        doc.verified_at = datetime.now(timezone.utc)
        doc.rejection_reason = rejection_reason
        return self.doc_repo.update(doc)
