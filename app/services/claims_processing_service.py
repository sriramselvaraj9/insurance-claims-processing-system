"""Central claims processing workflow orchestrator coordinating all domain services."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.id_generator import IdGenerator
from app.models.claim import Claim
from app.models.claim_status_history import ClaimStatusHistory
from app.models.enums import (
    AssessmentOutcome,
    ClaimStatus,
)
from app.repositories.claim_repository import ClaimRepository
from app.repositories.claim_status_history_repository import ClaimStatusHistoryRepository
from app.repositories.incident_repository import IncidentRepository
from app.repositories.policy_repository import PolicyRepository
from app.services.adjuster_service import AdjusterService
from app.services.coverage_service import CoverageService
from app.services.document_service import DocumentService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.eligibility_service import EligibilityService
from app.services.exceptions import ClaimNotFoundError, PolicyNotFoundError
from app.services.fraud_service import FraudService
from app.services.policy_validation_service import PolicyValidationService
from app.services.reserve_service import ReserveService
from app.services.settlement_service import SettlementService


@dataclass(frozen=True)
class ClaimsProcessingResult:
    claim_id: str
    status: ClaimStatus
    outcome: AssessmentOutcome
    is_eligible: bool
    assessment_id: str
    rejection_code: str | None
    decision_reasons: list[str]
    assigned_adjuster_id: str | None
    reserve_id: str | None
    total_reserve: Decimal | None
    settlement_id: str | None
    net_settlement_amount: Decimal | None
    missing_document_types: list[str]
    rule_results: list[dict[str, Any]]
    fraud_indicators: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        res["outcome"] = self.outcome.value
        res["total_reserve"] = str(self.total_reserve) if self.total_reserve is not None else None
        res["net_settlement_amount"] = str(self.net_settlement_amount) if self.net_settlement_amount is not None else None
        return res


class ClaimsProcessingService:
    def __init__(
        self,
        claim_repo: ClaimRepository,
        policy_repo: PolicyRepository,
        incident_repo: IncidentRepository,
        csh_repo: ClaimStatusHistoryRepository,
        policy_validation_service: PolicyValidationService,
        coverage_service: CoverageService,
        document_service: DocumentService,
        duplicate_service: DuplicateDetectionService,
        fraud_service: FraudService,
        eligibility_service: EligibilityService,
        adjuster_service: AdjusterService,
        reserve_service: ReserveService,
        settlement_service: SettlementService,
    ) -> None:
        self.claim_repo = claim_repo
        self.policy_repo = policy_repo
        self.incident_repo = incident_repo
        self.csh_repo = csh_repo
        self.policy_validation_service = policy_validation_service
        self.coverage_service = coverage_service
        self.document_service = document_service
        self.duplicate_service = duplicate_service
        self.fraud_service = fraud_service
        self.eligibility_service = eligibility_service
        self.adjuster_service = adjuster_service
        self.reserve_service = reserve_service
        self.settlement_service = settlement_service

    def process_claim(
        self,
        claim_id: str,
        actor_id: str = "CLAIMS_PROCESSING_ORCHESTRATOR",
    ) -> ClaimsProcessingResult:
        """Execute the end-to-end multi-stage claims processing workflow."""
        # 1. Load the Claim
        claim = self.claim_repo.get_by_id(claim_id)
        if not claim:
            raise ClaimNotFoundError(claim_id)

        policy = self.policy_repo.get_by_id(claim.policy_id)
        if not policy:
            raise PolicyNotFoundError(claim.policy_id)

        incident = self.incident_repo.get_by_id(claim.incident_id)

        # Transition claim status to UNDER_REVIEW
        initial_status = claim.status
        self._record_status_transition(
            claim=claim,
            new_status=ClaimStatus.UNDER_REVIEW,
            reason="Automated multi-stage assessment started.",
            changed_by=actor_id,
        )

        # 2. Validate Policy
        policy_result = self.policy_validation_service.validate_policy(
            claim=claim,
            incident=incident,
            actor_id=actor_id,
        )

        # 3. Validate Coverage
        coverage_result = self.coverage_service.validate_coverage(
            claim=claim,
            incident=incident,
            actor_id=actor_id,
        )

        # 4. Verify Documents & Emit Requests
        doc_result = self.document_service.verify_claim_documents(
            claim=claim,
            actor_id=actor_id,
        )

        # 5. Detect Duplicates
        duplicate_result = self.duplicate_service.check_duplicates(
            claim=claim,
            incident=incident,
        )

        # 6. Evaluate Fraud Indicators
        fraud_assessment = self.fraud_service.evaluate_claim_fraud(
            claim=claim,
            policy=policy,
            coverage_limit=coverage_result.coverage_limit,
            is_duplicate_claim=any(r.rule_id == "DUPLICATE_001" and not r.passed for r in duplicate_result.rule_results),
            is_duplicate_incident=any(r.rule_id == "DUPLICATE_002" and not r.passed for r in duplicate_result.rule_results),
            incident=incident,
        )

        # 7. Assess Eligibility
        eligibility_result = self.eligibility_service.assess_claim_eligibility(
            claim=claim,
            policy_result=policy_result,
            coverage_result=coverage_result,
            document_result=doc_result,
            duplicate_result=duplicate_result,
            fraud_flags=fraud_assessment.flags,
            actor_id=actor_id,
        )

        assigned_adj_id: str | None = None
        reserve_id: str | None = None
        total_reserve: Decimal | None = None
        settlement_id: str | None = None
        net_settlement_amount: Decimal | None = None

        outcome = eligibility_result.outcome

        # 8. Act upon Eligibility Outcome
        if outcome == AssessmentOutcome.INELIGIBLE:
            self._record_status_transition(
                claim=claim,
                new_status=ClaimStatus.REJECTED,
                reason=f"Claim assessed as INELIGIBLE. Rejection: {eligibility_result.rejection_code}",
                changed_by=actor_id,
            )

        elif outcome == AssessmentOutcome.PENDING_DOCUMENTS:
            self._record_status_transition(
                claim=claim,
                new_status=ClaimStatus.INFO_REQUESTED,
                reason="Mandatory evidentiary documents required; information requests dispatched.",
                changed_by=actor_id,
            )

        elif outcome == AssessmentOutcome.MANUAL_REVIEW:
            self._record_status_transition(
                claim=claim,
                new_status=ClaimStatus.FLAGGED,
                reason="Flagged for Special Investigation Unit (SIU) / manual claims review.",
                changed_by=actor_id,
            )
            # Assign an adjuster for manual review investigation
            try:
                assignment = self.adjuster_service.assign_adjuster(
                    claim=claim,
                    reason="Assigned for Special Investigation / manual review triage",
                    actor_id=actor_id,
                )
                assigned_adj_id = assignment.adjuster_id
            except Exception:
                pass

        elif outcome == AssessmentOutcome.ELIGIBLE:
            # Step A: Update to ELIGIBLE
            self._record_status_transition(
                claim=claim,
                new_status=ClaimStatus.ELIGIBLE,
                reason="All eligibility rules verified successfully.",
                changed_by=actor_id,
            )

            # Step B: Assign specialized Adjuster
            try:
                assignment = self.adjuster_service.assign_adjuster(
                    claim=claim,
                    reason="Primary claims handling assignment",
                    actor_id=actor_id,
                )
                assigned_adj_id = assignment.adjuster_id
                self._record_status_transition(
                    claim=claim,
                    new_status=ClaimStatus.ADJUSTER_ASSIGNED,
                    reason=f"Assigned to adjuster '{assigned_adj_id}'.",
                    changed_by=actor_id,
                )
            except Exception:
                pass

            # Step C: Calculate Preliminary Reserve
            reserve = self.reserve_service.calculate_claim_reserve(
                claim=claim,
                coverage=coverage_result.applicable_coverage,
                actor_id=actor_id,
            )
            reserve_id = reserve.id
            total_reserve = reserve.total_reserve

            self._record_status_transition(
                claim=claim,
                new_status=ClaimStatus.RESERVE_CALCULATED,
                reason=f"Preliminary reserve established at ${total_reserve}.",
                changed_by=actor_id,
            )

            # Step D: Recommend Settlement
            if coverage_result.applicable_coverage:
                try:
                    settlement = self.settlement_service.recommend_settlement(
                        claim=claim,
                        coverage=coverage_result.applicable_coverage,
                        actor_id=actor_id,
                    )
                    settlement_id = settlement.id
                    net_settlement_amount = settlement.net_settlement_amount

                    self._record_status_transition(
                        claim=claim,
                        new_status=ClaimStatus.SETTLEMENT_RECOMMENDED,
                        reason=f"Settlement recommendation formulated for ${net_settlement_amount}.",
                        changed_by=actor_id,
                    )
                except Exception:
                    pass

        return ClaimsProcessingResult(
            claim_id=claim.id,
            status=claim.status,
            outcome=outcome,
            is_eligible=eligibility_result.is_eligible,
            assessment_id=eligibility_result.assessment.id,
            rejection_code=eligibility_result.rejection_code,
            decision_reasons=eligibility_result.decision_reasons,
            assigned_adjuster_id=assigned_adj_id,
            reserve_id=reserve_id,
            total_reserve=total_reserve,
            settlement_id=settlement_id,
            net_settlement_amount=net_settlement_amount,
            missing_document_types=[m.value for m in doc_result.missing_document_types],
            rule_results=[r.to_dict() for r in eligibility_result.rule_results],
            fraud_indicators=[i.to_dict() for i in fraud_assessment.indicators],
        )

    def reassess_claim(
        self,
        claim_id: str,
        actor_id: str = "CLAIMS_REASSESSMENT_ENGINE",
    ) -> ClaimsProcessingResult:
        """Re-evaluate claim after document uploads or supplementary evidence without overwriting history."""
        return self.process_claim(claim_id=claim_id, actor_id=actor_id)

    def _record_status_transition(
        self,
        claim: Claim,
        new_status: ClaimStatus,
        reason: str,
        changed_by: str,
    ) -> None:
        """Update claim status and log append-only history record."""
        prev_status = claim.status
        if prev_status == new_status:
            return

        claim.status = new_status
        claim.updated_at = datetime.now(timezone.utc)
        self.claim_repo.update(claim)

        seq = len(self.csh_repo.get_by_claim_id(claim.id)) + 1
        csh_id = IdGenerator.claim_status_history_id(claim.id, seq)
        csh = ClaimStatusHistory(
            id=csh_id,
            claim_id=claim.id,
            previous_status=prev_status.value if prev_status else None,
            new_status=new_status.value,
            transition_reason=reason,
            changed_by=changed_by,
            timestamp=claim.updated_at,
        )
        self.csh_repo.create(csh)
