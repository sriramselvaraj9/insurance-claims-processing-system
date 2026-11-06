"""Generator for supporting records: AdjusterAssignments, DocumentRequests, StatusHistories, and AuditEvents."""

from datetime import timedelta
import random

from app.core.id_generator import IdGenerator
from app.models.adjuster import Adjuster
from app.models.adjuster_assignment import AdjusterAssignment
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.claim_status_history import ClaimStatusHistory
from app.models.document_request import DocumentRequest
from app.models.enums import (
    ActorType,
    AdjusterSpecialization,
    AuditAction,
    ClaimStatus,
    ClaimType,
    DocumentRequestStatus,
    DocumentType,
)


CLAIM_TO_SPECIALIZATION = {
    ClaimType.COLLISION: AdjusterSpecialization.AUTO,
    ClaimType.PROPERTY_DAMAGE: AdjusterSpecialization.PROPERTY,
    ClaimType.MEDICAL: AdjusterSpecialization.HEALTH,
    ClaimType.TRAVEL_LOSS: AdjusterSpecialization.TRAVEL,
    ClaimType.LIABILITY: AdjusterSpecialization.COMMERCIAL,
}


def generate_supporting_records(
    claims: list[Claim],
    adjusters: list[Adjuster],
    missing_docs_map: dict[str, DocumentType],
    seed: int,
    base_year: int = 2026,
) -> tuple[
    list[AdjusterAssignment],
    list[DocumentRequest],
    list[ClaimStatusHistory],
    list[AuditEvent],
]:
    """Generate all supporting tracking and audit records with strict referential consistency."""
    rng = random.Random(seed + 900)
    assignments: list[AdjusterAssignment] = []
    doc_requests: list[DocumentRequest] = []
    status_histories: list[ClaimStatusHistory] = []
    audit_events: list[AuditEvent] = []

    # Index adjusters by specialization
    adjusters_by_spec: dict[AdjusterSpecialization, list[Adjuster]] = {}
    for adj in adjusters:
        adjusters_by_spec.setdefault(adj.specialization, []).append(adj)

    audit_seq = 1

    for claim in claims:
        # 1. Adjuster Assignment
        required_spec = CLAIM_TO_SPECIALIZATION.get(claim.claim_type, AdjusterSpecialization.GENERAL)
        matching_adjs = adjusters_by_spec.get(required_spec, adjusters)
        selected_adj = matching_adjs[rng.randint(0, len(matching_adjs) - 1)]

        # Link adjuster to claim
        claim.assigned_adjuster_id = selected_adj.id
        selected_adj.active_claims_count += 1

        assign_id = IdGenerator.adjuster_assignment_id(claim.id, 1)
        assign_time = claim.reported_date + timedelta(hours=rng.randint(1, 4))
        assignment = AdjusterAssignment(
            id=assign_id,
            claim_id=claim.id,
            adjuster_id=selected_adj.id,
            assigned_at=assign_time,
            unassigned_at=None,
            assignment_reason=f"Automated specialized intake assignment to {selected_adj.name} ({required_spec.value})",
            is_active=True,
        )
        assignments.append(assignment)

        # 2. Document Request (for missing-document claims)
        if claim.id in missing_docs_map:
            missing_type = missing_docs_map[claim.id]
            req_id = IdGenerator.document_request_id(claim.id, 1)
            req_time = claim.reported_date + timedelta(hours=2)
            doc_req = DocumentRequest(
                id=req_id,
                claim_id=claim.id,
                document_type=missing_type,
                requested_at=req_time,
                status=DocumentRequestStatus.OPEN,
                fulfilled_document_id=None,
            )
            doc_requests.append(doc_req)

        # 3. Status History progression
        # Start: SUBMITTED
        csh_1 = ClaimStatusHistory(
            id=IdGenerator.claim_status_history_id(claim.id, 1),
            claim_id=claim.id,
            previous_status=None,
            new_status=ClaimStatus.SUBMITTED.value,
            transition_reason="Initial digital claim submission received.",
            changed_by="CUSTOMER_PORTAL",
            timestamp=claim.reported_date,
        )
        status_histories.append(csh_1)

        # Progression to UNDER_REVIEW
        csh_2 = ClaimStatusHistory(
            id=IdGenerator.claim_status_history_id(claim.id, 2),
            claim_id=claim.id,
            previous_status=ClaimStatus.SUBMITTED.value,
            new_status=ClaimStatus.UNDER_REVIEW.value,
            transition_reason="Assigned to claims triage and automated eligibility evaluation.",
            changed_by="SYSTEM_WORKFLOW",
            timestamp=claim.reported_date + timedelta(hours=1),
        )
        status_histories.append(csh_2)

        # Final transition if status evolved beyond UNDER_REVIEW
        if claim.status != ClaimStatus.UNDER_REVIEW and claim.status != ClaimStatus.SUBMITTED:
            csh_3 = ClaimStatusHistory(
                id=IdGenerator.claim_status_history_id(claim.id, 3),
                claim_id=claim.id,
                previous_status=ClaimStatus.UNDER_REVIEW.value,
                new_status=claim.status.value,
                transition_reason=f"Claim advanced to final state {claim.status.value}.",
                changed_by=selected_adj.name,
                timestamp=claim.updated_at,
            )
            status_histories.append(csh_3)

        # 4. Audit Events
        aud_1 = AuditEvent(
            id=IdGenerator.audit_event_id(audit_seq, year=base_year),
            entity_type="Claim",
            entity_id=claim.id,
            action=AuditAction.CREATE,
            state_before=None,
            state_after={"status": ClaimStatus.SUBMITTED.value, "claimed_amount": str(claim.claimed_amount)},
            actor_type=ActorType.API_SERVICE,
            actor_id="CLAIM_INTAKE_GATEWAY",
            timestamp=claim.reported_date,
            metadata_={"ip_address": "192.168.1.100", "source": "REST_API"},
        )
        audit_events.append(aud_1)
        audit_seq += 1

        aud_2 = AuditEvent(
            id=IdGenerator.audit_event_id(audit_seq, year=base_year),
            entity_type="Claim",
            entity_id=claim.id,
            action=AuditAction.STATE_TRANSITION,
            state_before={"status": ClaimStatus.UNDER_REVIEW.value},
            state_after={"status": claim.status.value},
            actor_type=ActorType.USER_ADJUSTER,
            actor_id=selected_adj.employee_id,
            timestamp=claim.updated_at,
            metadata_={"adjuster_id": selected_adj.id},
        )
        audit_events.append(aud_2)
        audit_seq += 1

    return assignments, doc_requests, status_histories, audit_events
