"""Generator for deterministic synthetic Assessment records."""

from datetime import timedelta
import random

from app.core.id_generator import IdGenerator
from app.models.assessment import Assessment
from app.models.claim import Claim
from app.models.coverage import Coverage
from app.models.document import Document
from app.models.incident import Incident
from app.models.policy import Policy
from app.rules.eligibility_rules import evaluate_eligibility
from scripts.generators.anomaly_injector import AnomalyInjectionPlan


def generate_assessments(
    claims: list[Claim],
    policies: list[Policy],
    coverages: list[Coverage],
    incidents: list[Incident],
    documents: list[Document],
    anomaly_plan: AnomalyInjectionPlan,
    seed: int,
) -> list[Assessment]:
    """Generate deterministically evaluated Assessment records for each claim using the rule engine."""
    rng = random.Random(seed + 600)
    assessments: list[Assessment] = []

    policies_by_id = {p.id: p for p in policies}
    incidents_by_id = {inc.id: inc for inc in incidents}
    
    coverages_by_policy: dict[str, list[Coverage]] = {}
    for cov in coverages:
        coverages_by_policy.setdefault(cov.policy_id, []).append(cov)

    docs_by_claim: dict[str, list[Document]] = {}
    for doc in documents:
        docs_by_claim.setdefault(doc.claim_id, []).append(doc)

    for claim in claims:
        policy = policies_by_id[claim.policy_id]
        incident = incidents_by_id[claim.incident_id]
        pol_coverages = coverages_by_policy.get(policy.id, [])
        claim_docs = docs_by_claim.get(claim.id, [])

        # Format coverages for eligibility engine: Sequence of (CoverageType, is_active, exclusions)
        cov_tuples = [
            (c.coverage_type, c.is_active, c.exclusions)
            for c in pol_coverages
        ]

        # Format documents for eligibility engine: Sequence of (DocumentType, VerificationStatus)
        doc_tuples = [
            (d.document_type, d.verification_status)
            for d in claim_docs
        ]

        is_dup_claim = claim.id in anomaly_plan.duplicate_claim_ids
        is_dup_incident = claim.id in anomaly_plan.duplicate_incident_claim_ids

        # Evaluate eligibility via rule engine
        decision = evaluate_eligibility(
            policy_status=policy.status,
            policy_effective_date=policy.effective_date,
            policy_expiration_date=policy.expiration_date,
            policy_cancellation_date=policy.cancellation_date,
            incident_date=incident.occurrence_date,
            reported_date=claim.reported_date,
            claim_type=claim.claim_type,
            available_coverages=cov_tuples,
            provided_documents=doc_tuples,
            is_duplicate_claim=is_dup_claim,
            is_duplicate_incident=is_dup_incident,
        )

        assessed_at = claim.reported_date + timedelta(hours=rng.randint(2, 8))
        asm_id = IdGenerator.assessment_id(claim.id, 1)

        assessment = Assessment(
            id=asm_id,
            claim_id=claim.id,
            is_eligible=decision.is_eligible,
            policy_active_check=decision.policy_active_check,
            incident_covered_check=decision.incident_covered_check,
            timely_filing_check=decision.timely_filing_check,
            exclusions_check=decision.exclusions_check,
            documentation_complete_check=decision.documentation_complete_check,
            fraud_check_passed=decision.fraud_check_passed,
            decision_reasons=decision.decision_reasons,
            rejection_code=decision.rejection_code.value if decision.rejection_code else None,
            assessed_at=assessed_at,
            assessed_by="RULE_ENGINE_V1",
            created_at=assessed_at,
        )
        assessments.append(assessment)

    return assessments
