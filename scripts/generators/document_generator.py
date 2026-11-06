"""Generator for realistic synthetic Document records."""

from datetime import datetime, timedelta
import hashlib
import random

from app.core.id_generator import IdGenerator
from app.models.claim import Claim
from app.models.document import Document
from app.models.enums import DocumentType, VerificationStatus
from app.rules.document_rules import get_mandatory_documents


def generate_documents_for_claim(
    claim: Claim,
    is_missing_document_anomaly: bool = False,
    seed: int = 20261022,
) -> tuple[list[Document], DocumentType | None]:
    """Generate documents for a claim.

    If is_missing_document_anomaly is True, intentionally omit the last mandatory document
    and return the omitted DocumentType so a DocumentRequest can be created for it.
    """
    claim_seq = int(claim.id.split("-")[-1]) if "-" in claim.id else 0
    rng = random.Random(seed + claim_seq * 37)
    docs: list[Document] = []
    omitted_type: DocumentType | None = None

    mandatory_types = get_mandatory_documents(claim.claim_type)

    if is_missing_document_anomaly:
        # Intentionally omit the last mandatory document
        omitted_type = mandatory_types[-1]
        active_types = mandatory_types[:-1]
    else:
        active_types = mandatory_types

    file_ext_map = {
        DocumentType.POLICE_REPORT: ("police_report.pdf", "application/pdf"),
        DocumentType.REPAIR_ESTIMATE: ("repair_estimate.pdf", "application/pdf"),
        DocumentType.MEDICAL_BILL: ("medical_itemized_bill.pdf", "application/pdf"),
        DocumentType.PROOF_OF_LOSS: ("notarized_proof_of_loss.pdf", "application/pdf"),
        DocumentType.DAMAGE_PHOTO: ("loss_damage_evidence.jpg", "image/jpeg"),
        DocumentType.OTHER: ("supporting_documentation.pdf", "application/pdf"),
    }

    for seq, doc_type in enumerate(active_types, start=1):
        doc_id = IdGenerator.document_id(claim.id, seq)
        ext_name, mime_type = file_ext_map.get(doc_type, ("document.pdf", "application/pdf"))
        file_name = f"{claim.id}_{doc_type.value.lower()}_{ext_name}"
        file_path = f"s3://insurance-claims-vault/{claim.id}/{file_name}"
        file_size = rng.randint(45000, 2500000)

        # Deterministic SHA-256 checksum
        raw_hash_seed = f"{doc_id}:{file_name}:{file_size}".encode("utf-8")
        checksum = hashlib.sha256(raw_hash_seed).hexdigest()

        submission_date = claim.reported_date + timedelta(minutes=rng.randint(5, 60))
        
        # If missing doc anomaly, status is PENDING or REJECTED for unverified docs
        if is_missing_document_anomaly and seq == 1:
            status = VerificationStatus.PENDING
            verified_at = None
            verified_by = None
        else:
            status = VerificationStatus.VERIFIED
            verified_at = submission_date + timedelta(hours=1, minutes=rng.randint(5, 30))
            verified_by = "SYSTEM_DOC_VALIDATOR"

        doc = Document(
            id=doc_id,
            claim_id=claim.id,
            document_type=doc_type,
            file_name=file_name,
            file_type=mime_type,
            file_path=file_path,
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            submission_date=submission_date,
            verification_status=status,
            verified_at=verified_at,
            verified_by=verified_by,
            rejection_reason=None,
            created_at=submission_date,
        )
        docs.append(doc)

    return docs, omitted_type


def generate_documents(
    claims: list[Claim],
    missing_doc_claim_ids: set[str],
    seed: int,
) -> tuple[list[Document], dict[str, DocumentType]]:
    """Generate documents for all claims, tracking omitted document types for missing-doc claims."""
    all_docs: list[Document] = []
    missing_docs_map: dict[str, DocumentType] = {}

    for claim in claims:
        is_missing = claim.id in missing_doc_claim_ids
        docs, omitted = generate_documents_for_claim(
            claim,
            is_missing_document_anomaly=is_missing,
            seed=seed,
        )
        all_docs.extend(docs)
        if omitted:
            missing_docs_map[claim.id] = omitted

    return all_docs, missing_docs_map
