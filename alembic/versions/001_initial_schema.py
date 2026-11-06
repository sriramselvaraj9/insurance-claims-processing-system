"""001_initial_schema: Complete schema for 11 core entities and supporting tables.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-06 22:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("kyc_status", sa.String(length=30), nullable=False),
        sa.Column("risk_profile", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_id", "customers", ["id"])
    op.create_index("ix_customers_email", "customers", ["email"], unique=True)

    # 2. policies table
    op.create_table(
        "policies",
        sa.Column("id", sa.String(length=60), nullable=False),
        sa.Column("customer_id", sa.String(length=50), nullable=False),
        sa.Column("policy_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("cancellation_date", sa.Date(), nullable=True),
        sa.Column("total_premium", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deductible", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.CheckConstraint("expiration_date > effective_date", name="ck_policy_dates"),
        sa.CheckConstraint("total_premium >= 0", name="ck_policy_premium_positive"),
        sa.CheckConstraint("deductible >= 0", name="ck_policy_deductible_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_id", "policies", ["id"])
    op.create_index("ix_policies_customer_id", "policies", ["customer_id"])
    op.create_index("ix_policies_status", "policies", ["status"])

    # 3. coverages table
    op.create_table(
        "coverages",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("policy_id", sa.String(length=60), nullable=False),
        sa.Column("coverage_type", sa.String(length=50), nullable=False),
        sa.Column("coverage_limit", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deductible", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("copay_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("exclusions", sa.JSON(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.CheckConstraint("coverage_limit > 0", name="ck_coverage_limit_positive"),
        sa.CheckConstraint("deductible >= 0", name="ck_coverage_deductible_positive"),
        sa.CheckConstraint("copay_percentage >= 0 AND copay_percentage <= 100", name="ck_coverage_copay_range"),
        sa.CheckConstraint("expiration_date >= effective_date", name="ck_coverage_period_valid"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coverages_id", "coverages", ["id"])
    op.create_index("ix_coverages_policy_id", "coverages", ["policy_id"])

    # 4. incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("incident_type", sa.String(length=50), nullable=False),
        sa.Column("occurrence_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_street", sa.String(length=255), nullable=False),
        sa.Column("location_city", sa.String(length=100), nullable=False),
        sa.Column("location_state", sa.String(length=50), nullable=False),
        sa.Column("location_zip", sa.String(length=20), nullable=False),
        sa.Column("police_report_filed", sa.Boolean(), nullable=False),
        sa.Column("police_report_number", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_id", "incidents", ["id"])
    op.create_index("ix_incidents_occurrence_date", "incidents", ["occurrence_date"])
    op.create_index("ix_incidents_city", "incidents", ["location_city"])
    op.create_index("ix_incidents_state", "incidents", ["location_state"])
    op.create_index("ix_incidents_dedup", "incidents", ["occurrence_date", "location_city", "location_street"])

    # 5. adjusters table
    op.create_table(
        "adjusters",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("employee_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("specialization", sa.String(length=50), nullable=False),
        sa.Column("active_claims_count", sa.Integer(), nullable=False),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("active_claims_count >= 0", name="ck_adjuster_active_claims_positive"),
        sa.CheckConstraint("max_capacity > 0", name="ck_adjuster_capacity_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_adjusters_id", "adjusters", ["id"])
    op.create_index("ix_adjusters_employee_id", "adjusters", ["employee_id"], unique=True)
    op.create_index("ix_adjusters_email", "adjusters", ["email"], unique=True)
    op.create_index("ix_adjusters_specialization", "adjusters", ["specialization"])

    # 6. claims table
    op.create_table(
        "claims",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=50), nullable=False),
        sa.Column("policy_id", sa.String(length=60), nullable=False),
        sa.Column("incident_id", sa.String(length=50), nullable=False),
        sa.Column("claim_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reported_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("estimated_loss", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_adjuster_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["assigned_adjuster_id"], ["adjusters.id"]),
        sa.CheckConstraint("claimed_amount >= 0", name="ck_claim_claimed_amount_positive"),
        sa.CheckConstraint("estimated_loss >= 0", name="ck_claim_estimated_loss_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_id", "claims", ["id"])
    op.create_index("ix_claims_customer_id", "claims", ["customer_id"])
    op.create_index("ix_claims_policy_id", "claims", ["policy_id"])
    op.create_index("ix_claims_incident_id", "claims", ["incident_id"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_index("ix_claims_reported_date", "claims", ["reported_date"])

    # 7. claim_items table
    op.create_table(
        "claim_items",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("coverage_id", sa.String(length=80), nullable=True),
        sa.Column("item_description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["coverage_id"], ["coverages.id"]),
        sa.CheckConstraint("quantity >= 1", name="ck_claim_item_quantity_positive"),
        sa.CheckConstraint("unit_amount >= 0", name="ck_claim_item_unit_amount_positive"),
        sa.CheckConstraint("total_amount >= 0", name="ck_claim_item_total_amount_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_items_id", "claim_items", ["id"])
    op.create_index("ix_claim_items_claim_id", "claim_items", ["claim_id"])

    # 8. documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("submission_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(length=100), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_document_filesize_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_documents_claim_id", "documents", ["claim_id"])
    op.create_index("ix_documents_checksum", "documents", ["checksum_sha256"])

    # 9. document_requests table
    op.create_table(
        "document_requests",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("fulfilled_document_id", sa.String(length=70), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["fulfilled_document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_requests_id", "document_requests", ["id"])
    op.create_index("ix_document_requests_claim_id", "document_requests", ["claim_id"])

    # 10. adjuster_assignments table
    op.create_table(
        "adjuster_assignments",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("adjuster_id", sa.String(length=50), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_reason", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["adjuster_id"], ["adjusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_adjuster_assignments_id", "adjuster_assignments", ["id"])
    op.create_index("ix_adjuster_assignments_claim_id", "adjuster_assignments", ["claim_id"])
    op.create_index("ix_adjuster_assignments_adjuster_id", "adjuster_assignments", ["adjuster_id"])

    # 11. assessments table
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("is_eligible", sa.Boolean(), nullable=False),
        sa.Column("policy_active_check", sa.Boolean(), nullable=False),
        sa.Column("incident_covered_check", sa.Boolean(), nullable=False),
        sa.Column("timely_filing_check", sa.Boolean(), nullable=False),
        sa.Column("exclusions_check", sa.Boolean(), nullable=False),
        sa.Column("documentation_complete_check", sa.Boolean(), nullable=False),
        sa.Column("fraud_check_passed", sa.Boolean(), nullable=False),
        sa.Column("decision_reasons", sa.JSON(), nullable=False),
        sa.Column("rejection_code", sa.String(length=50), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assessed_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_id", "assessments", ["id"])
    op.create_index("ix_assessments_claim_id", "assessments", ["claim_id"])

    # 12. reserves table
    op.create_table(
        "reserves",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("estimated_indemnity_reserve", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("estimated_expense_reserve", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_reserve", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("expense_ratio", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("calculation_method", sa.String(length=50), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("calculated_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.CheckConstraint("estimated_indemnity_reserve >= 0", name="ck_reserve_indemnity_positive"),
        sa.CheckConstraint("estimated_expense_reserve >= 0", name="ck_reserve_expense_positive"),
        sa.CheckConstraint("total_reserve >= 0", name="ck_reserve_total_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reserves_id", "reserves", ["id"])
    op.create_index("ix_reserves_claim_id", "reserves", ["claim_id"])

    # 13. settlements table
    op.create_table(
        "settlements",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("recommended_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("deductible_applied", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("copay_applied", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("net_settlement_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_by", sa.String(length=100), nullable=True),
        sa.Column("payment_reference", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.CheckConstraint("recommended_amount >= 0", name="ck_settlement_recommended_positive"),
        sa.CheckConstraint("deductible_applied >= 0", name="ck_settlement_deductible_positive"),
        sa.CheckConstraint("copay_applied >= 0", name="ck_settlement_copay_positive"),
        sa.CheckConstraint("net_settlement_amount >= 0", name="ck_settlement_net_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_settlements_id", "settlements", ["id"])
    op.create_index("ix_settlements_claim_id", "settlements", ["claim_id"])

    # 14. settlement_payments table
    op.create_table(
        "settlement_payments",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("settlement_id", sa.String(length=70), nullable=False),
        sa.Column("payment_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("payment_reference", sa.String(length=100), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["settlement_id"], ["settlements.id"]),
        sa.CheckConstraint("payment_amount > 0", name="ck_payment_amount_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_settlement_payments_id", "settlement_payments", ["id"])
    op.create_index("ix_settlement_payments_settlement_id", "settlement_payments", ["settlement_id"])
    op.create_index("ix_settlement_payments_reference", "settlement_payments", ["payment_reference"], unique=True)

    # 15. claim_status_history table
    op.create_table(
        "claim_status_history",
        sa.Column("id", sa.String(length=70), nullable=False),
        sa.Column("claim_id", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("transition_reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_status_history_id", "claim_status_history", ["id"])
    op.create_index("ix_claim_status_history_claim_id", "claim_status_history", ["claim_id"])

    # 16. audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("state_before", sa.JSON(), nullable=True),
        sa.Column("state_after", sa.JSON(), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_id", "audit_events", ["id"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("claim_status_history")
    op.drop_table("settlement_payments")
    op.drop_table("settlements")
    op.drop_table("reserves")
    op.drop_table("assessments")
    op.drop_table("adjuster_assignments")
    op.drop_table("document_requests")
    op.drop_table("documents")
    op.drop_table("claim_items")
    op.drop_table("claims")
    op.drop_table("adjusters")
    op.drop_table("incidents")
    op.drop_table("coverages")
    op.drop_table("policies")
    op.drop_table("customers")

