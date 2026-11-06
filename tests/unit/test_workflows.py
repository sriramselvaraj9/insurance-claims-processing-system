"""Unit tests for claim lifecycle workflows and state machine transitions."""

import pytest

from app.models.enums import ClaimStatus
from app.workflows.claim_lifecycle import can_transition_claim, validate_claim_transition
from app.workflows.exceptions import InvalidStateTransitionError


class TestClaimLifecycleFSM:
    def test_valid_transitions(self):
        # SUBMITTED -> UNDER_REVIEW -> ELIGIBLE -> ADJUSTER_ASSIGNED -> RESERVE_CALCULATED -> SETTLEMENT_RECOMMENDED -> APPROVED -> SETTLED -> CLOSED
        assert can_transition_claim(ClaimStatus.SUBMITTED, ClaimStatus.UNDER_REVIEW) is True
        assert can_transition_claim(ClaimStatus.UNDER_REVIEW, ClaimStatus.ELIGIBLE) is True
        assert can_transition_claim(ClaimStatus.ELIGIBLE, ClaimStatus.ADJUSTER_ASSIGNED) is True
        assert can_transition_claim(ClaimStatus.ADJUSTER_ASSIGNED, ClaimStatus.RESERVE_CALCULATED) is True
        assert can_transition_claim(ClaimStatus.RESERVE_CALCULATED, ClaimStatus.SETTLEMENT_RECOMMENDED) is True
        assert can_transition_claim(ClaimStatus.SETTLEMENT_RECOMMENDED, ClaimStatus.APPROVED) is True
        assert can_transition_claim(ClaimStatus.APPROVED, ClaimStatus.SETTLED) is True
        assert can_transition_claim(ClaimStatus.SETTLED, ClaimStatus.CLOSED) is True

    def test_invalid_transitions(self):
        # Cannot jump from SUBMITTED directly to SETTLED
        assert can_transition_claim(ClaimStatus.SUBMITTED, ClaimStatus.SETTLED) is False
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_claim_transition(ClaimStatus.SUBMITTED, ClaimStatus.SETTLED)
        assert exc_info.value.current_status == ClaimStatus.SUBMITTED.value
        assert exc_info.value.target_status == ClaimStatus.SETTLED.value

        # Cannot transition out of terminal CLOSED state
        assert can_transition_claim(ClaimStatus.CLOSED, ClaimStatus.SUBMITTED) is False
        assert can_transition_claim(ClaimStatus.CLOSED, ClaimStatus.UNDER_REVIEW) is False
        with pytest.raises(InvalidStateTransitionError):
            validate_claim_transition(ClaimStatus.CLOSED, ClaimStatus.UNDER_REVIEW)

    def test_info_requested_cycle(self):
        assert can_transition_claim(ClaimStatus.SUBMITTED, ClaimStatus.INFO_REQUESTED) is True
        assert can_transition_claim(ClaimStatus.INFO_REQUESTED, ClaimStatus.UNDER_REVIEW) is True

    def test_flagged_quarantine(self):
        assert can_transition_claim(ClaimStatus.UNDER_REVIEW, ClaimStatus.FLAGGED) is True
        assert can_transition_claim(ClaimStatus.FLAGGED, ClaimStatus.UNDER_REVIEW) is True
        assert can_transition_claim(ClaimStatus.FLAGGED, ClaimStatus.REJECTED) is True
