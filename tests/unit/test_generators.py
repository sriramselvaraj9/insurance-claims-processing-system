"""Unit tests for synthetic data generation engine, anomaly injection, and reproducibility."""

from decimal import Decimal
from pathlib import Path
import tempfile

import pytest

from app.models.enums import ClaimType, PolicyType
from scripts.export_data import export_all_datasets
from scripts.generation_config import get_generation_config
from scripts.generators.adjuster_generator import generate_adjusters
from scripts.generators.anomaly_injector import plan_and_inject_anomalies
from scripts.generators.assessment_generator import generate_assessments
from scripts.generators.claim_generator import generate_claims
from scripts.generators.claim_item_generator import generate_claim_items
from scripts.generators.coverage_generator import generate_coverages
from scripts.generators.customer_generator import generate_customers
from scripts.generators.document_generator import generate_documents
from scripts.generators.incident_generator import generate_incidents
from scripts.generators.policy_generator import generate_policies
from scripts.generators.reserve_generator import generate_reserves
from scripts.generators.settlement_generator import generate_settlements_and_payments
from scripts.generators.supporting_generator import generate_supporting_records
from scripts.validate_data import DataValidator


class TestDataGenerators:
    @pytest.fixture
    def starter_config(self):
        return get_generation_config(scale="starter", seed=20261022)

    def test_customer_generator(self, starter_config):
        customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
        assert len(customers) == starter_config.num_customers
        emails = {c.email for c in customers}
        assert len(emails) == len(customers)
        for c in customers:
            assert c.id.startswith("CUST-")
            assert c.first_name and c.last_name
            assert c.date_of_birth

    def test_policy_generator(self, starter_config):
        customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
        policies = generate_policies(starter_config.num_policies, customers=customers, seed=starter_config.seed)
        assert len(policies) == starter_config.num_policies
        cust_ids = {c.id for c in customers}
        for p in policies:
            assert p.customer_id in cust_ids
            assert p.expiration_date > p.effective_date
            assert p.total_premium >= Decimal("0.00")
            assert p.deductible >= Decimal("0.00")

    def test_claim_generator_relational_invariant(self, starter_config):
        customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
        policies = generate_policies(starter_config.num_policies, customers=customers, seed=starter_config.seed)
        incidents = generate_incidents(starter_config.num_claims, seed=starter_config.seed)
        claims = generate_claims(
            count=starter_config.num_claims,
            policies=policies,
            incidents=incidents,
            seed=starter_config.seed,
        )
        assert len(claims) == starter_config.num_claims

        policy_map = {p.id: p for p in policies}
        claim_types = {c.claim_type for c in claims}
        assert len(claim_types) == 5  # All 5 types generated

        for c in claims:
            parent_policy = policy_map[c.policy_id]
            # Crucial invariant: Claim customer matches Policy customer
            assert c.customer_id == parent_policy.customer_id
            assert c.claimed_amount > Decimal("0.00")
            assert c.estimated_loss >= Decimal("0.00")

    def test_claim_items_sum_strictly_matches_claimed_amount(self, starter_config):
        customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
        policies = generate_policies(starter_config.num_policies, customers=customers, seed=starter_config.seed)
        coverages = generate_coverages(policies=policies, seed=starter_config.seed)
        incidents = generate_incidents(starter_config.num_claims, seed=starter_config.seed)
        claims = generate_claims(
            count=starter_config.num_claims,
            policies=policies,
            incidents=incidents,
            seed=starter_config.seed,
        )
        claim_items = generate_claim_items(claims=claims, coverages=coverages, seed=starter_config.seed)

        items_by_claim = {}
        for itm in claim_items:
            items_by_claim.setdefault(itm.claim_id, []).append(itm)

        for c in claims:
            items = items_by_claim[c.id]
            assert len(items) >= 1
            item_total_sum = sum(itm.total_amount for itm in items)
            assert item_total_sum == c.claimed_amount

    def test_anomaly_injection_and_ground_truth(self, starter_config):
        customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
        policies = generate_policies(starter_config.num_policies, customers=customers, seed=starter_config.seed)
        coverages = generate_coverages(policies=policies, seed=starter_config.seed)
        incidents = generate_incidents(starter_config.num_claims, seed=starter_config.seed)
        claims = generate_claims(
            count=starter_config.num_claims,
            policies=policies,
            incidents=incidents,
            seed=starter_config.seed,
        )
        plan = plan_and_inject_anomalies(
            config=starter_config,
            claims=claims,
            policies=policies,
            coverages=coverages,
            incidents=incidents,
            seed=starter_config.seed,
        )

        assert len(plan.ground_truth_records) > 0
        issue_types = {gt.issue_type for gt in plan.ground_truth_records}
        assert "DATE_BEFORE_POLICY_START" in issue_types
        assert "POLICY_CANCELLED_BEFORE_INCIDENT" in issue_types
        assert "SETTLEMENT_EXCEEDS_COVERAGE_LIMIT" in issue_types
        assert "MISSING_MANDATORY_DOCUMENT" in issue_types
        assert "CLAIM_PAID_TWICE" in issue_types

    def test_end_to_end_starter_export_and_validation(self, starter_config):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            customers = generate_customers(starter_config.num_customers, seed=starter_config.seed)
            policies = generate_policies(starter_config.num_policies, customers=customers, seed=starter_config.seed)
            coverages = generate_coverages(policies=policies, seed=starter_config.seed)
            adjusters = generate_adjusters(starter_config.num_adjusters, seed=starter_config.seed)
            incidents = generate_incidents(starter_config.num_claims, seed=starter_config.seed)
            claims = generate_claims(
                count=starter_config.num_claims,
                policies=policies,
                incidents=incidents,
                seed=starter_config.seed,
            )
            plan = plan_and_inject_anomalies(
                config=starter_config,
                claims=claims,
                policies=policies,
                coverages=coverages,
                incidents=incidents,
                seed=starter_config.seed,
            )
            claim_items = generate_claim_items(claims=claims, coverages=coverages, seed=starter_config.seed)
            documents, missing_map = generate_documents(
                claims=claims,
                missing_doc_claim_ids=plan.missing_doc_claim_ids,
                seed=starter_config.seed,
            )
            assessments = generate_assessments(
                claims=claims,
                policies=policies,
                coverages=coverages,
                incidents=incidents,
                documents=documents,
                anomaly_plan=plan,
                seed=starter_config.seed,
            )
            reserves = generate_reserves(
                claims=claims,
                policies=policies,
                coverages=coverages,
                seed=starter_config.seed,
            )
            settlements, payments = generate_settlements_and_payments(
                claims=claims,
                policies=policies,
                coverages=coverages,
                assessments=assessments,
                anomaly_plan=plan,
                seed=starter_config.seed,
            )
            assignments, doc_reqs, histories, audits = generate_supporting_records(
                claims=claims,
                adjusters=adjusters,
                missing_docs_map=missing_map,
                seed=starter_config.seed,
            )

            dataset_map = {
                "customers": customers,
                "policies": policies,
                "coverages": coverages,
                "incidents": incidents,
                "adjusters": adjusters,
                "claims": claims,
                "claim_items": claim_items,
                "documents": documents,
                "assessments": assessments,
                "reserves": reserves,
                "settlements": settlements,
                "adjuster_assignments": assignments,
                "document_requests": doc_reqs,
                "settlement_payments": payments,
                "claim_status_history": histories,
                "audit_events": audits,
            }

            export_all_datasets(
                output_dir=tmp_path,
                scale="starter",
                seed=starter_config.seed,
                dataset_map=dataset_map,
                ground_truth_records=plan.ground_truth_records,
            )

            validator = DataValidator(tmp_path)
            report = validator.run_all_validations()

            assert report["status"] == "PASSED"
            assert report["error_count"] == 0
            assert report["total_tables_checked"] == 16

