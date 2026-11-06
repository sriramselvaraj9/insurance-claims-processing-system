"""Unit tests for business, financial, document, eligibility, and fraud rules."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.enums import (
    ClaimType,
    CoverageType,
    DocumentType,
    ExceptionSeverity,
    PolicyStatus,
    RejectionCode,
    VerificationStatus,
)
from app.rules.document_rules import (
    MANDATORY_DOCUMENTS_BY_CLAIM_TYPE,
    check_document_completeness,
    get_mandatory_documents,
)
from app.rules.eligibility_rules import evaluate_eligibility
from app.rules.financial_rules import (
    compute_allowable_loss,
    compute_expense_reserve,
    compute_indemnity_reserve,
    compute_settlement,
    compute_total_reserve,
    quantize_money,
)
from app.rules.fraud_rules import assess_fraud_risk


class TestFinancialRules:
    def test_quantize_money(self):
        assert quantize_money(Decimal("100.456")) == Decimal("100.46")
        assert quantize_money(Decimal("100.454")) == Decimal("100.45")
        assert quantize_money(Decimal("100.455")) == Decimal("100.46")

    def test_compute_allowable_loss(self):
        limit = Decimal("50000.00")
        assert compute_allowable_loss(Decimal("30000.00"), limit) == Decimal("30000.00")
        assert compute_allowable_loss(Decimal("75000.00"), limit) == Decimal("50000.00")
        assert compute_allowable_loss(Decimal("-500.00"), limit) == Decimal("0.00")

    def test_compute_reserves(self):
        loss = Decimal("10000.00")
        limit = Decimal("50000.00")
        deductible = Decimal("1000.00")

        indemnity = compute_indemnity_reserve(loss, limit, deductible)
        assert indemnity == Decimal("9000.00")

        expense = compute_expense_reserve(indemnity, Decimal("0.1200"))
        assert expense == Decimal("1080.00")

        total = compute_total_reserve(loss, limit, deductible, Decimal("0.1200"))
        assert total.allowable_loss == Decimal("10000.00")
        assert total.indemnity_reserve == Decimal("9000.00")
        assert total.expense_reserve == Decimal("1080.00")
        assert total.total_reserve == Decimal("10080.00")

    def test_compute_settlement_standard(self):
        claimed = Decimal("8000.00")
        limit = Decimal("25000.00")
        deductible = Decimal("500.00")
        copay = Decimal("0.00")

        settlement = compute_settlement(claimed, limit, deductible, copay)
        assert settlement.allowable_loss == Decimal("8000.00")
        assert settlement.deductible_applied == Decimal("500.00")
        assert settlement.copay_applied == Decimal("0.00")
        assert settlement.net_settlement_amount == Decimal("7500.00")

    def test_compute_settlement_with_copay_and_limit_cap(self):
        claimed = Decimal("40000.00")
        limit = Decimal("30000.00")
        deductible = Decimal("1000.00")
        copay = Decimal("20.00")  # 20% copay

        settlement = compute_settlement(claimed, limit, deductible, copay)
        # Allowable = min(40000, 30000) = 30000
        # Subject to copay = 30000 - 1000 = 29000
        # Copay = 29000 * 0.20 = 5800.00
        # Net = 29000 - 5800 = 23200.00
        assert settlement.allowable_loss == Decimal("30000.00")
        assert settlement.deductible_applied == Decimal("1000.00")
        assert settlement.copay_applied == Decimal("5800.00")
        assert settlement.net_settlement_amount == Decimal("23200.00")

    def test_compute_settlement_loss_below_deductible(self):
        claimed = Decimal("400.00")
        limit = Decimal("10000.00")
        deductible = Decimal("500.00")

        settlement = compute_settlement(claimed, limit, deductible)
        assert settlement.allowable_loss == Decimal("400.00")
        assert settlement.deductible_applied == Decimal("400.00")
        assert settlement.net_settlement_amount == Decimal("0.00")


class TestDocumentRules:
    def test_all_five_claim_types_defined(self):
        expected_types = [
            ClaimType.COLLISION,
            ClaimType.PROPERTY_DAMAGE,
            ClaimType.MEDICAL,
            ClaimType.TRAVEL_LOSS,
            ClaimType.LIABILITY,
        ]
        for ct in expected_types:
            assert ct in MANDATORY_DOCUMENTS_BY_CLAIM_TYPE
            docs = get_mandatory_documents(ct)
            assert len(docs) >= 2

    def test_check_document_completeness_success(self):
        provided = [
            (DocumentType.POLICE_REPORT, VerificationStatus.VERIFIED),
            (DocumentType.REPAIR_ESTIMATE, VerificationStatus.VERIFIED),
            (DocumentType.DAMAGE_PHOTO, VerificationStatus.VERIFIED),
        ]
        res = check_document_completeness(ClaimType.COLLISION, provided)
        assert res.is_complete is True
        assert len(res.missing_document_types) == 0
        assert len(res.unverified_document_types) == 0

    def test_check_document_completeness_missing_doc(self):
        provided = [
            (DocumentType.POLICE_REPORT, VerificationStatus.VERIFIED),
        ]
        res = check_document_completeness(ClaimType.COLLISION, provided)
        assert res.is_complete is False
        assert DocumentType.REPAIR_ESTIMATE in res.missing_document_types
        assert DocumentType.DAMAGE_PHOTO in res.missing_document_types

    def test_check_document_completeness_unverified_doc(self):
        provided = [
            (DocumentType.POLICE_REPORT, VerificationStatus.VERIFIED),
            (DocumentType.REPAIR_ESTIMATE, VerificationStatus.PENDING),
            (DocumentType.DAMAGE_PHOTO, VerificationStatus.VERIFIED),
        ]
        res = check_document_completeness(ClaimType.COLLISION, provided)
        assert res.is_complete is False
        assert DocumentType.REPAIR_ESTIMATE in res.unverified_document_types


class TestEligibilityRules:
    @pytest.fixture
    def base_context(self):
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        return {
            "policy_status": PolicyStatus.ACTIVE,
            "policy_effective_date": date(2026, 1, 1),
            "policy_expiration_date": date(2026, 12, 31),
            "policy_cancellation_date": None,
            "incident_date": now - timedelta(days=5),
            "reported_date": now,
            "claim_type": ClaimType.COLLISION,
            "available_coverages": [(CoverageType.COLLISION, True, None)],
            "provided_documents": [
                (DocumentType.POLICE_REPORT, VerificationStatus.VERIFIED),
                (DocumentType.REPAIR_ESTIMATE, VerificationStatus.VERIFIED),
                (DocumentType.DAMAGE_PHOTO, VerificationStatus.VERIFIED),
            ],
            "is_duplicate_claim": False,
            "is_duplicate_incident": False,
        }

    def test_clean_claim_is_eligible(self, base_context):
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is True
        assert decision.policy_active_check is True
        assert decision.incident_covered_check is True
        assert decision.timely_filing_check is True
        assert decision.exclusions_check is True
        assert decision.documentation_complete_check is True
        assert decision.fraud_check_passed is True
        assert decision.rejection_code is None

    def test_neg_01_incident_before_policy_start(self, base_context):
        base_context["incident_date"] = datetime(2025, 12, 1, tzinfo=timezone.utc)
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.policy_active_check is False
        assert decision.rejection_code == RejectionCode.EXPIRED_POLICY

    def test_neg_01_incident_after_policy_cancellation(self, base_context):
        base_context["policy_status"] = PolicyStatus.CANCELLED
        base_context["policy_cancellation_date"] = date(2026, 3, 1)
        base_context["incident_date"] = datetime(2026, 4, 1, tzinfo=timezone.utc)
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.policy_active_check is False
        assert decision.rejection_code == RejectionCode.EXPIRED_POLICY

    def test_neg_02_uncovered_peril(self, base_context):
        # Claim is COLLISION, but policy only has MEDICAL_PAYMENTS
        base_context["available_coverages"] = [(CoverageType.MEDICAL_PAYMENTS, True, None)]
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.incident_covered_check is False
        assert decision.rejection_code == RejectionCode.UNCOVERED_PERIL

    def test_neg_02_policy_exclusion(self, base_context):
        # Policy explicitly excludes COLLISION
        base_context["available_coverages"] = [
            (CoverageType.COLLISION, True, ["COLLISION", "RACING"])
        ]
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.exclusions_check is False
        assert decision.rejection_code == RejectionCode.POLICY_EXCLUSION

    def test_neg_03_untimely_filing(self, base_context):
        # Filed 60 days after incident (> 30 days statutory window)
        base_context["incident_date"] = base_context["reported_date"] - timedelta(days=60)
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.timely_filing_check is False
        assert decision.rejection_code == RejectionCode.UNTIMELY_FILING

    def test_neg_04_missing_mandatory_documents(self, base_context):
        # Only 1 of 3 mandatory documents provided
        base_context["provided_documents"] = [
            (DocumentType.POLICE_REPORT, VerificationStatus.VERIFIED),
        ]
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.documentation_complete_check is False
        assert decision.rejection_code == RejectionCode.MISSING_MANDATORY_DOCUMENTS

    def test_neg_06_duplicate_claim(self, base_context):
        base_context["is_duplicate_claim"] = True
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.fraud_check_passed is False
        assert decision.rejection_code == RejectionCode.DUPLICATE_CLAIM

    def test_neg_06_duplicate_incident(self, base_context):
        base_context["is_duplicate_incident"] = True
        decision = evaluate_eligibility(**base_context)
        assert decision.is_eligible is False
        assert decision.fraud_check_passed is False
        assert decision.rejection_code == RejectionCode.SUSPECTED_FRAUD


class TestFraudRules:
    def test_clean_submission(self):
        assessment = assess_fraud_risk(
            policy_status=PolicyStatus.ACTIVE,
            claimed_amount=Decimal("5000.00"),
            coverage_limit=Decimal("50000.00"),
        )
        assert assessment.is_fraudulent_or_quarantined is False
        assert assessment.severity == ExceptionSeverity.LOW

    def test_excessive_amount_and_duplicate(self):
        assessment = assess_fraud_risk(
            policy_status=PolicyStatus.ACTIVE,
            claimed_amount=Decimal("150000.00"),  # > 200% of 50k
            coverage_limit=Decimal("50000.00"),
            is_duplicate_claim=True,
        )
        assert assessment.is_fraudulent_or_quarantined is True
        assert assessment.severity == ExceptionSeverity.CRITICAL
        assert assessment.rejection_code == RejectionCode.DUPLICATE_CLAIM
