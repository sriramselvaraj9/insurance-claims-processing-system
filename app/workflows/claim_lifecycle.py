"""Claim lifecycle Finite State Machine."""

from app.models.enums import ClaimStatus
from app.workflows.exceptions import InvalidStateTransitionError

# Legal state transitions dictionary
VALID_CLAIM_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.SUBMITTED: {
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.INFO_REQUESTED,
        ClaimStatus.FLAGGED,
        ClaimStatus.REJECTED,
    },
    ClaimStatus.INFO_REQUESTED: {
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.REJECTED,
        ClaimStatus.CLOSED,
    },
    ClaimStatus.UNDER_REVIEW: {
        ClaimStatus.ELIGIBLE,
        ClaimStatus.INELIGIBLE,
        ClaimStatus.INFO_REQUESTED,
        ClaimStatus.FLAGGED,
        ClaimStatus.REJECTED,
    },
    ClaimStatus.INELIGIBLE: {
        ClaimStatus.REJECTED,
        ClaimStatus.UNDER_REVIEW,  # Reopened upon supplementary evidence
    },
    ClaimStatus.ELIGIBLE: {
        ClaimStatus.ADJUSTER_ASSIGNED,
        ClaimStatus.RESERVE_CALCULATED,
        ClaimStatus.UNDER_REVIEW,
    },
    ClaimStatus.ADJUSTER_ASSIGNED: {
        ClaimStatus.RESERVE_CALCULATED,
        ClaimStatus.SETTLEMENT_RECOMMENDED,
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.FLAGGED,
    },
    ClaimStatus.RESERVE_CALCULATED: {
        ClaimStatus.SETTLEMENT_RECOMMENDED,
        ClaimStatus.UNDER_REVIEW,
    },
    ClaimStatus.SETTLEMENT_RECOMMENDED: {
        ClaimStatus.APPROVED,
        ClaimStatus.REJECTED,
        ClaimStatus.UNDER_REVIEW,
    },
    ClaimStatus.APPROVED: {
        ClaimStatus.SETTLED,
        ClaimStatus.REJECTED,
    },
    ClaimStatus.SETTLED: {
        ClaimStatus.CLOSED,
    },
    ClaimStatus.FLAGGED: {
        ClaimStatus.UNDER_REVIEW,  # Quarantined claims triaged by SIU
        ClaimStatus.REJECTED,
    },
    ClaimStatus.REJECTED: {
        ClaimStatus.CLOSED,
    },
    ClaimStatus.CLOSED: set(),  # Terminal state
}


def can_transition_claim(current_status: ClaimStatus, target_status: ClaimStatus) -> bool:
    """Return True if the transition from current_status to target_status is valid."""
    allowed = VALID_CLAIM_TRANSITIONS.get(current_status, set())
    return target_status in allowed


def validate_claim_transition(
    current_status: ClaimStatus, target_status: ClaimStatus
) -> None:
    """Validate claim transition, raising InvalidStateTransitionError if illegal."""
    if not can_transition_claim(current_status, target_status):
        raise InvalidStateTransitionError(
            current_status=current_status.value,
            target_status=target_status.value,
            entity_name="Claim",
            reason=f"Transition from {current_status.value} to {target_status.value} is not permitted by lifecycle rules",
        )

