"""Adjuster assignment engine with specialization matching and workload capacity controls."""

from datetime import datetime, timezone

from app.core.id_generator import IdGenerator
from app.models.adjuster import Adjuster
from app.models.adjuster_assignment import AdjusterAssignment
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.enums import (
    ActorType,
    AdjusterSpecialization,
    AuditAction,
    ClaimType,
)
from app.repositories.adjuster_assignment_repository import AdjusterAssignmentRepository
from app.repositories.adjuster_repository import AdjusterRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.claim_repository import ClaimRepository
from app.services.exceptions import NoEligibleAdjusterError

CLAIM_TO_SPECIALIZATION = {
    ClaimType.COLLISION: AdjusterSpecialization.AUTO,
    ClaimType.COMPREHENSIVE: AdjusterSpecialization.AUTO,
    ClaimType.PROPERTY_DAMAGE: AdjusterSpecialization.PROPERTY,
    ClaimType.WATER_DAMAGE: AdjusterSpecialization.PROPERTY,
    ClaimType.FIRE: AdjusterSpecialization.PROPERTY,
    ClaimType.THEFT: AdjusterSpecialization.PROPERTY,
    ClaimType.MEDICAL: AdjusterSpecialization.HEALTH,
    ClaimType.BODILY_INJURY: AdjusterSpecialization.HEALTH,
    ClaimType.TRAVEL_LOSS: AdjusterSpecialization.TRAVEL,
    ClaimType.LIABILITY: AdjusterSpecialization.COMMERCIAL,
}


class AdjusterService:
    def __init__(
        self,
        adjuster_repo: AdjusterRepository,
        assignment_repo: AdjusterAssignmentRepository,
        claim_repo: ClaimRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.adjuster_repo = adjuster_repo
        self.assignment_repo = assignment_repo
        self.claim_repo = claim_repo
        self.audit_repo = audit_repo

    def assign_adjuster(
        self,
        claim: Claim,
        reason: str = "Automated specialized claims triage assignment",
        actor_id: str = "ADJUSTER_ROUTING_SERVICE",
    ) -> AdjusterAssignment:
        """Find the least-loaded eligible adjuster matching claim type specialization and assign them."""
        target_spec = CLAIM_TO_SPECIALIZATION.get(claim.claim_type, AdjusterSpecialization.GENERAL)

        # 1. Look for available adjusters with exact specialization
        eligible_adjusters = self.adjuster_repo.find_available_by_specialization(target_spec)

        # 2. Fallback to GENERAL specialization if no specialized adjuster has capacity
        if not eligible_adjusters and target_spec != AdjusterSpecialization.GENERAL:
            eligible_adjusters = self.adjuster_repo.find_available_by_specialization(AdjusterSpecialization.GENERAL)

        # 3. Fallback to least loaded active adjuster of any specialization
        if not eligible_adjusters:
            all_active = self.adjuster_repo.get_all_active()
            eligible_adjusters = [a for a in all_active if a.has_capacity]

        if not eligible_adjusters:
            raise NoEligibleAdjusterError(
                specialization=target_spec.value,
                reason="All active adjusters are currently at maximum caseload capacity",
            )

        # Prefer least-loaded adjuster (tie-broken deterministically by employee_id)
        selected_adjuster = min(
            eligible_adjusters,
            key=lambda a: (a.active_claims_count, a.employee_id),
        )

        # Deactivate previous active assignment for this claim if reassignment
        current_active = self.assignment_repo.get_active_by_claim_id(claim.id)
        if current_active:
            current_active.is_active = False
            current_active.unassigned_at = datetime.now(timezone.utc)
            self.assignment_repo.update(current_active)

            # Decrement previous adjuster's active claims count
            prev_adj = self.adjuster_repo.get_by_id(current_active.adjuster_id)
            if prev_adj and prev_adj.active_claims_count > 0:
                prev_adj.active_claims_count -= 1
                self.adjuster_repo.update(prev_adj)

        # Create new assignment
        now = datetime.now(timezone.utc)
        existing_assignments = self.assignment_repo.get_history_by_claim_id(claim.id)
        seq = len(existing_assignments) + 1
        assignment_id = IdGenerator.adjuster_assignment_id(claim.id, seq)

        assignment = AdjusterAssignment(
            id=assignment_id,
            claim_id=claim.id,
            adjuster_id=selected_adjuster.id,
            assigned_at=now,
            unassigned_at=None,
            assignment_reason=f"{reason} (Specialization: {selected_adjuster.specialization.value}, Caseload: {selected_adjuster.active_claims_count}/{selected_adjuster.max_capacity})",
            is_active=True,
        )
        self.assignment_repo.create(assignment)

        # Increment assigned adjuster's active claims count transactionally
        selected_adjuster.active_claims_count += 1
        self.adjuster_repo.update(selected_adjuster)

        # Update claim's assigned_adjuster_id
        claim.assigned_adjuster_id = selected_adjuster.id
        self.claim_repo.update(claim)

        # Record ADJUSTER_ASSIGNED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Claim",
            entity_id=claim.id,
            action=AuditAction.ADJUSTER_ASSIGNED,
            state_before=None,
            state_after={"assigned_adjuster_id": selected_adjuster.id},
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "adjuster_id": selected_adjuster.id,
                "adjuster_name": selected_adjuster.name,
                "specialization": selected_adjuster.specialization.value,
                "active_caseload": selected_adjuster.active_claims_count,
            },
        )
        self.audit_repo.create(audit_event)

        return assignment
