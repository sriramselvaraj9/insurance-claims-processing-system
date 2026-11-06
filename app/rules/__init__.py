"""Business rules engine modules."""

from app.rules.coverage_rules import (
    CLAIM_TO_COVERAGE_TYPES,
    evaluate_coverage_rules,
)
from app.rules.document_rules import (
    MANDATORY_DOCUMENTS_BY_CLAIM_TYPE,
    DocumentCheckResult,
    check_document_completeness,
    get_mandatory_documents,
)
from app.rules.duplicate_rules import evaluate_duplicate_rules
from app.rules.eligibility_rules import (
    EligibilityDecision,
    evaluate_eligibility,
)
from app.rules.financial_rules import (
    ReserveBreakdown,
    SettlementBreakdown,
    compute_allowable_loss,
    compute_expense_reserve,
    compute_indemnity_reserve,
    compute_settlement,
    compute_total_reserve,
    quantize_money,
)
from app.rules.fraud_rules import (
    FraudAssessment,
    FraudIndicator,
    assess_fraud_risk,
    evaluate_fraud_indicators,
)
from app.rules.policy_rules import evaluate_policy_rules
from app.rules.rule_base import RuleResult

__all__ = [
    "RuleResult",
    "evaluate_policy_rules",
    "CLAIM_TO_COVERAGE_TYPES",
    "evaluate_coverage_rules",
    "MANDATORY_DOCUMENTS_BY_CLAIM_TYPE",
    "DocumentCheckResult",
    "check_document_completeness",
    "get_mandatory_documents",
    "evaluate_duplicate_rules",
    "FraudIndicator",
    "FraudAssessment",
    "evaluate_fraud_indicators",
    "assess_fraud_risk",
    "EligibilityDecision",
    "evaluate_eligibility",
    "quantize_money",
    "compute_allowable_loss",
    "compute_indemnity_reserve",
    "compute_expense_reserve",
    "compute_total_reserve",
    "compute_settlement",
    "ReserveBreakdown",
    "SettlementBreakdown",
]
