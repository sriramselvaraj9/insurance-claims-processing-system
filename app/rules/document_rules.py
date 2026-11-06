"""Document completeness rules and claim type document matrices.

Defines the five standard claim types and their mandatory evidentiary document requirements.
"""

from dataclasses import dataclass
from typing import Sequence

from app.models.enums import ClaimType, DocumentType, VerificationStatus


MANDATORY_DOCUMENTS_BY_CLAIM_TYPE: dict[ClaimType, list[DocumentType]] = {
    ClaimType.COLLISION: [
        DocumentType.POLICE_REPORT,
        DocumentType.REPAIR_ESTIMATE,
        DocumentType.DAMAGE_PHOTO,
    ],
    ClaimType.PROPERTY_DAMAGE: [
        DocumentType.REPAIR_ESTIMATE,
        DocumentType.PROOF_OF_LOSS,
        DocumentType.DAMAGE_PHOTO,
    ],
    ClaimType.MEDICAL: [
        DocumentType.MEDICAL_BILL,
        DocumentType.PROOF_OF_LOSS,
    ],
    ClaimType.TRAVEL_LOSS: [
        DocumentType.PROOF_OF_LOSS,
        DocumentType.OTHER,
    ],
    ClaimType.LIABILITY: [
        DocumentType.POLICE_REPORT,
        DocumentType.REPAIR_ESTIMATE,
    ],
}


@dataclass(frozen=True)
class DocumentCheckResult:
    is_complete: bool
    missing_document_types: list[DocumentType]
    unverified_document_types: list[DocumentType]
    reasons: list[str]


def get_mandatory_documents(claim_type: ClaimType) -> list[DocumentType]:
    """Retrieve the list of mandatory document types for a given claim type."""
    return MANDATORY_DOCUMENTS_BY_CLAIM_TYPE.get(
        claim_type, [DocumentType.PROOF_OF_LOSS]
    )


def check_document_completeness(
    claim_type: ClaimType,
    provided_documents: Sequence[tuple[DocumentType, VerificationStatus]],
) -> DocumentCheckResult:
    """Verify whether all mandatory documents are provided AND verified.

    provided_documents: Sequence of (document_type, verification_status) tuples.
    """
    mandatory = get_mandatory_documents(claim_type)
    provided_types = {doc_type for doc_type, _ in provided_documents}
    verified_types = {
        doc_type
        for doc_type, status in provided_documents
        if status == VerificationStatus.VERIFIED
    }

    missing: list[DocumentType] = [dt for dt in mandatory if dt not in provided_types]
    unverified: list[DocumentType] = [
        dt for dt in mandatory if dt in provided_types and dt not in verified_types
    ]

    reasons: list[str] = []
    if missing:
        missing_names = ", ".join(m.value for m in missing)
        reasons.append(f"Missing mandatory documents: {missing_names}")
    if unverified:
        unverified_names = ", ".join(u.value for u in unverified)
        reasons.append(f"Unverified mandatory documents: {unverified_names}")

    is_complete = len(missing) == 0 and len(unverified) == 0
    return DocumentCheckResult(
        is_complete=is_complete,
        missing_document_types=missing,
        unverified_document_types=unverified,
        reasons=reasons,
    )
