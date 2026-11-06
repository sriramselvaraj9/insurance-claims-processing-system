"""Eligibility assessment service orchestrating decision precedence and persisting assessment history."""

from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal

from app.core.id_generator import IdGenerator
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.enums import (
    ActorType,
    AssessmentOutcome,
    AuditAction,
    RejectionCode,
)
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.audit_repository import AuditRepository
from app.rules.coverage_rules import evaluate_coverage_rules
from app.rules.document_rules import check_document_completeness
from app.rules.duplicate_rules import evaluate_duplicate_rules
from app.rules.eligibility_rules import EligibilityDecision, evaluate_eligibility
from app.rules.fraud_rules import evaluate_fraud_indicators
from app.rules.policy_rules import evaluate_policy_rules
from app.rules.rule_base import RuleResult
from app.services.coverage_service import CoverageValidationResult
from app.services.document_service import DocumentVerificationResult
from app.services.duplicate_detection_service import DuplicateDetectionResult
from app.services.policy_validation_service import PolicyValidationResult


@dataclass(frozen=True)
class EligibilityServiceResult:
    outcome: AssessmentOutcome
    is_eligible: bool
    assessment: Assessment
    rejection_code: str | None
    decision_reasons: list[str]
    rule_results: list[RuleResult]


class EligibilityService:
    def __init__(
        self,
        assessment_repo: AssessmentRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.assessment_repo = assessment_repo
        self.audit_repo = audit_repo

    def assess_claim_eligibility(
        self,
        claim: Claim,
        policy_result: PolicyValidationResult,
        coverage_result: CoverageValidationResult,
        document_result: DocumentVerificationResult,
        duplicate_result: DuplicateDetectionResult,
        fraud_flags: list[str],
        actor_id: str = "ELIGIBILITY_RULE_ENGINE",
    ) -> EligibilityServiceResult:
        """Apply strict decision precedence across all evaluation facets, persist assessment and audit."""
        decision_reasons: list[str] = []
        rule_results: list[RuleResult] = []
        rule_results.extend(policy_result.rule_results)
        rule_results.extend(coverage_result.rule_results)
        rule_results.extend(document_result.rule_results)
        rule_results.extend(duplicate_result.rule_results)

        outcome: AssessmentOutcome
        is_eligible: bool = False
        rejection_code: str | None = None

        # Check breakdown booleans for Assessment model
        policy_active_check = policy_result.is_valid
        incident_covered_check = coverage_result.is_covered
        # Exclusions check from coverage rule COVERAGE_003
        cov_003 = next((r for r in coverage_result.rule_results if r.rule_id == "COVERAGE_003"), None)
        exclusions_check = cov_003.passed if cov_003 else True
        # Timely filing check
        fraud_003 = next((r for r in rule_results if r.rule_id == "FRAUD_003"), None)
        timely_filing_check = fraud_003.passed if fraud_003 else True
        # Documentation check
        documentation_complete_check = document_result.is_complete
        # Fraud & Duplicate check
        fraud_check_passed = not duplicate_result.has_duplicates and len(fraud_flags) == 0

        # --- Decision Precedence Evaluation ---
        # 1. Policy invalid at incident date / ownership mismatch
        if not policy_result.is_valid:
            outcome = AssessmentOutcome.INELIGIBLE
            rejection_code = (
                RejectionCode.EXPIRED_POLICY.value
                if any("commencement" in f.lower() or "expiration" in f.lower() or "cancelled" in f.lower() for f in policy_result.failure_reasons)
                else RejectionCode.SUSPENDED_POLICY.value
            )
            decision_reasons.extend(policy_result.failure_reasons)

        # 2. No applicable coverage or peril uncovered
        elif not coverage_result.is_covered:
            outcome = AssessmentOutcome.INELIGIBLE
            cov_001 = next((r for r in coverage_result.rule_results if r.rule_id == "COVERAGE_001"), None)
            if cov_001 and not cov_001.passed:
                rejection_code = RejectionCode.UNCOVERED_PERIL.value
            elif not exclusions_check:
                rejection_code = RejectionCode.POLICY_EXCLUSION.value
            else:
                rejection_code = RejectionCode.UNCOVERED_PERIL.value
            decision_reasons.extend(coverage_result.failure_reasons)

        # 3. Timely filing exceeded (> 30 days)
        elif not timely_filing_check:
            outcome = AssessmentOutcome.INELIGIBLE
            rejection_code = RejectionCode.UNTIMELY_FILING.value
            decision_reasons.append(fraud_003.reason if fraud_003 else "Statutory notice window exceeded")

        # 4. Duplicate claims or suspected fraud -> MANUAL_REVIEW
        elif duplicate_result.has_duplicates:
            outcome = AssessmentOutcome.MANUAL_REVIEW
            dup_001 = next((r for r in duplicate_result.rule_results if r.rule_id == "DUPLICATE_001"), None)
            rejection_code = (
                RejectionCode.DUPLICATE_CLAIM.value
                if dup_001 and not dup_001.passed
                else RejectionCode.SUSPECTED_FRAUD.value
            )
            decision_reasons.extend(duplicate_result.failure_reasons)

        elif len(fraud_flags) > 0:
            outcome = AssessmentOutcome.MANUAL_REVIEW
            rejection_code = RejectionCode.SUSPECTED_FRAUD.value
            decision_reasons.extend(fraud_flags)

        # 5. Missing mandatory evidence -> PENDING_DOCUMENTS
        elif not document_result.is_complete:
            outcome = AssessmentOutcome.PENDING_DOCUMENTS
            rejection_code = RejectionCode.MISSING_MANDATORY_DOCUMENTS.value
            decision_reasons.extend(document_result.reasons)

        # 6. All requirements met -> ELIGIBLE
        else:
            outcome = AssessmentOutcome.ELIGIBLE
            is_eligible = True
            rejection_code = None
            decision_reasons.append("All statutory, policy coverage, and documentation verification requirements satisfied")

        # Create Assessment record (append-only history)
        existing_assessments = self.assessment_repo.get_by_claim_id(claim.id)
        seq = len(existing_assessments) + 1
        asm_id = IdGenerator.assessment_id(claim.id, seq)
        now = datetime.now(timezone.utc)

        assessment = Assessment(
            id=asm_id,
            claim_id=claim.id,
            is_eligible=is_eligible,
            policy_active_check=policy_active_check,
            incident_covered_check=incident_covered_check,
            timely_filing_check=timely_filing_check,
            exclusions_check=exclusions_check,
            documentation_complete_check=documentation_complete_check,
            fraud_check_passed=fraud_check_passed,
            decision_reasons=decision_reasons,
            rejection_code=rejection_code,
            assessed_at=now,
            assessed_by=actor_id,
            created_at=now,
        )
        self.assessment_repo.create(assessment)

        # Record ASSESSMENT_COMPLETED audit event
        audit_event = AuditEvent(
            id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
            entity_type="Assessment",
            entity_id=asm_id,
            action=AuditAction.ASSESSMENT_COMPLETED,
            state_before=None,
            state_after={"outcome": outcome.value, "is_eligible": is_eligible},
            actor_type=ActorType.SYSTEM_RULE,
            actor_id=actor_id,
            timestamp=now,
            metadata_={
                "claim_id": claim.id,
                "rejection_code": rejection_code,
                "assessment_sequence": seq,
            },
        )
        self.audit_repo.create(audit_event)

        # If MANUAL_REVIEW, record specific alert event
        if outcome == AssessmentOutcome.MANUAL_REVIEW:
            mr_audit = AuditEvent(
                id=IdGenerator.audit_event_id(self.audit_repo.count() + 1),
                entity_type="Claim",
                entity_id=claim.id,
                action=AuditAction.MANUAL_REVIEW_REQUIRED,
                state_before=None,
                state_after={"outcome": outcome.value},
                actor_type=ActorType.SYSTEM_RULE,
                actor_id=actor_id,
                timestamp=now,
                metadata_={"reasons": decision_reasons},
            )
            self.audit_repo.create(mr_audit)

        return EligibilityServiceResult(
            outcome=outcome,
            is_eligible=is_eligible,
            assessment=assessment,
            rejection_code=rejection_code,
            decision_reasons=decision_reasons,
            rule_results=rule_results,
        )
