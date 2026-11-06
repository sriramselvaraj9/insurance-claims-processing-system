"""Automated data quality, referential integrity, and business rule validation script."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import pandas as pd

from scripts.export_data import compute_file_sha256


class DataValidator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.csv_dir = data_dir / "csv"
        self.json_dir = data_dir / "json"
        self.gt_dir = data_dir / "ground_truth"
        self.manifest_file = data_dir / "manifests" / "source_manifest.json"
        
        self.tables: dict[str, pd.DataFrame] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.metrics: dict[str, any] = {}

    def load_data(self):
        """Load all CSV datasets into memory for validation."""
        required_tables = [
            "customers",
            "policies",
            "coverages",
            "incidents",
            "adjusters",
            "claims",
            "claim_items",
            "documents",
            "assessments",
            "reserves",
            "settlements",
            "adjuster_assignments",
            "document_requests",
            "settlement_payments",
            "claim_status_history",
            "audit_events",
        ]
        for tbl in required_tables:
            path = self.csv_dir / f"{tbl}.csv"
            if not path.exists():
                self.errors.append(f"Missing required CSV file: {path}")
            else:
                self.tables[tbl] = pd.read_csv(path, dtype=str)

    def validate_pk_uniqueness(self):
        """Ensure all primary keys are unique and non-null."""
        pk_map = {
            "customers": "id",
            "policies": "id",
            "coverages": "id",
            "incidents": "id",
            "adjusters": "id",
            "claims": "id",
            "claim_items": "id",
            "documents": "id",
            "assessments": "id",
            "reserves": "id",
            "settlements": "id",
            "adjuster_assignments": "id",
            "document_requests": "id",
            "settlement_payments": "id",
            "claim_status_history": "id",
            "audit_events": "id",
        }
        for tbl, pk_col in pk_map.items():
            if tbl not in self.tables:
                continue
            df = self.tables[tbl]
            if pk_col not in df.columns:
                self.errors.append(f"Table '{tbl}' missing primary key column '{pk_col}'")
                continue
            null_count = df[pk_col].isnull().sum()
            if null_count > 0:
                self.errors.append(f"Table '{tbl}' has {null_count} null PK values")
            dup_count = df[pk_col].duplicated().sum()
            if dup_count > 0:
                self.errors.append(f"Table '{tbl}' has {dup_count} duplicate PK values")

    def validate_referential_integrity(self):
        """Validate foreign key relationships across all tables."""
        t = self.tables
        if not t:
            return

        cust_ids = set(t["customers"]["id"])
        pol_ids = set(t["policies"]["id"])
        cov_ids = set(t["coverages"]["id"])
        inc_ids = set(t["incidents"]["id"])
        adj_ids = set(t["adjusters"]["id"])
        claim_ids = set(t["claims"]["id"])
        settle_ids = set(t["settlements"]["id"])

        # 1. Policies -> Customers
        for _, row in t["policies"].iterrows():
            if row["customer_id"] not in cust_ids:
                self.errors.append(f"Policy '{row['id']}' references nonexistent customer '{row['customer_id']}'")

        # 2. Coverages -> Policies
        for _, row in t["coverages"].iterrows():
            if row["policy_id"] not in pol_ids:
                self.errors.append(f"Coverage '{row['id']}' references nonexistent policy '{row['policy_id']}'")

        # 3. Claims -> Policies, Customers, Incidents, Adjusters
        policy_owner_map = dict(zip(t["policies"]["id"], t["policies"]["customer_id"]))
        for _, row in t["claims"].iterrows():
            cid = row["id"]
            if row["policy_id"] not in pol_ids:
                self.errors.append(f"Claim '{cid}' references nonexistent policy '{row['policy_id']}'")
            if row["customer_id"] not in cust_ids:
                self.errors.append(f"Claim '{cid}' references nonexistent customer '{row['customer_id']}'")
            if row["incident_id"] not in inc_ids:
                self.errors.append(f"Claim '{cid}' references nonexistent incident '{row['incident_id']}'")
            if pd.notnull(row.get("assigned_adjuster_id")) and row["assigned_adjuster_id"] not in adj_ids:
                self.errors.append(f"Claim '{cid}' references nonexistent adjuster '{row['assigned_adjuster_id']}'")

            # CRITICAL RELATIONAL INVARIANT: Claim customer == Policy customer
            expected_owner = policy_owner_map.get(row["policy_id"])
            if expected_owner and row["customer_id"] != expected_owner:
                self.errors.append(
                    f"Relational Mismatch: Claim '{cid}' customer '{row['customer_id']}' does not match policy owner '{expected_owner}'"
                )

        # 4. ClaimItems -> Claims & Coverages
        for _, row in t["claim_items"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"ClaimItem '{row['id']}' references nonexistent claim '{row['claim_id']}'")
            if pd.notnull(row.get("coverage_id")) and row["coverage_id"] not in cov_ids:
                self.errors.append(f"ClaimItem '{row['id']}' references nonexistent coverage '{row['coverage_id']}'")

        # 5. Documents -> Claims
        for _, row in t["documents"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"Document '{row['id']}' references nonexistent claim '{row['claim_id']}'")

        # 6. Assessments -> Claims
        for _, row in t["assessments"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"Assessment '{row['id']}' references nonexistent claim '{row['claim_id']}'")

        # 7. Reserves -> Claims
        for _, row in t["reserves"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"Reserve '{row['id']}' references nonexistent claim '{row['claim_id']}'")

        # 8. Settlements -> Claims
        for _, row in t["settlements"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"Settlement '{row['id']}' references nonexistent claim '{row['claim_id']}'")

        # 9. SettlementPayments -> Settlements
        for _, row in t["settlement_payments"].iterrows():
            if row["settlement_id"] not in settle_ids:
                self.errors.append(f"SettlementPayment '{row['id']}' references nonexistent settlement '{row['settlement_id']}'")

        # 10. AdjusterAssignments -> Claims & Adjusters
        for _, row in t["adjuster_assignments"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"Assignment '{row['id']}' references nonexistent claim '{row['claim_id']}'")
            if row["adjuster_id"] not in adj_ids:
                self.errors.append(f"Assignment '{row['id']}' references nonexistent adjuster '{row['adjuster_id']}'")

        # 11. DocumentRequests -> Claims
        for _, row in t["document_requests"].iterrows():
            if row["claim_id"] not in claim_ids:
                self.errors.append(f"DocumentRequest '{row['id']}' references nonexistent claim '{row['claim_id']}'")

    def validate_financial_consistency(self):
        """Validate monetary calculations, item summations, and reserve formulas."""
        t = self.tables
        if "claims" not in t or "claim_items" not in t:
            return

        # Check: Claim items total == Claim claimed_amount
        item_sums: dict[str, Decimal] = {}
        for _, row in t["claim_items"].iterrows():
            cid = row["claim_id"]
            tot = Decimal(str(row["total_amount"]))
            item_sums[cid] = item_sums.get(cid, Decimal("0.00")) + tot

        for _, row in t["claims"].iterrows():
            cid = row["id"]
            claimed = Decimal(str(row["claimed_amount"]))
            sum_items = item_sums.get(cid, Decimal("0.00"))
            if abs(claimed - sum_items) > Decimal("0.01"):
                self.errors.append(
                    f"Financial Mismatch: Claim '{cid}' claimed_amount (${claimed}) != sum of line items (${sum_items})"
                )

        # Check: Reserves total_reserve == indemnity + expense
        for _, row in t["reserves"].iterrows():
            rid = row["id"]
            ind = Decimal(str(row["estimated_indemnity_reserve"]))
            exp = Decimal(str(row["estimated_expense_reserve"]))
            tot = Decimal(str(row["total_reserve"]))
            if abs((ind + exp) - tot) > Decimal("0.01"):
                self.errors.append(
                    f"Reserve Math Error: Reserve '{rid}' total (${tot}) != indemnity (${ind}) + expense (${exp})"
                )

    def validate_ground_truth(self):
        """Validate ground truth dataset presence, isolation, and validity."""
        gt_csv = self.gt_dir / "ground_truth.csv"
        gt_json = self.gt_dir / "ground_truth.json"

        if not gt_csv.exists() or not gt_json.exists():
            self.errors.append("Ground truth files missing from data/synthetic/ground_truth/")
            return

        df_gt = pd.read_csv(gt_csv)
        required_cols = [
            "entity_id",
            "issue_type",
            "expected_decision",
            "expected_anomaly_label",
            "reason",
            "severity",
            "relevant_rule_id",
        ]
        for col in required_cols:
            if col not in df_gt.columns:
                self.errors.append(f"Ground truth dataset missing required column '{col}'")

        # Verify ground truth isolation: normal exports must NOT contain ground truth columns
        for tbl, df in self.tables.items():
            for forbidden_col in ["expected_anomaly_label", "expected_decision", "relevant_rule_id"]:
                if forbidden_col in df.columns:
                    self.errors.append(
                        f"Data Leakage: Table '{tbl}' contains ground truth column '{forbidden_col}'"
                    )

        # Verify that all referenced entity_ids exist in the datasets
        all_ids = set()
        for df in self.tables.values():
            if "id" in df.columns:
                all_ids.update(df["id"].dropna())

        for _, row in df_gt.iterrows():
            ent_id = row["entity_id"]
            if ent_id not in all_ids:
                self.errors.append(f"Ground truth references nonexistent entity_id '{ent_id}'")

        self.metrics["ground_truth_records_count"] = len(df_gt)
        self.metrics["ground_truth_issue_types"] = df_gt["issue_type"].value_counts().to_dict()

    def validate_manifest(self):
        """Verify source_manifest.json against files on disk."""
        if not self.manifest_file.exists():
            self.errors.append("Manifest file missing: source_manifest.json")
            return

        with open(self.manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for rel_path, file_meta in manifest.get("files", {}).items():
            full_path = self.data_dir / rel_path
            if not full_path.exists():
                self.errors.append(f"Manifest references missing file on disk: {rel_path}")
                continue
            actual_hash = compute_file_sha256(full_path)
            if actual_hash != file_meta["sha256"]:
                self.errors.append(
                    f"Checksum Mismatch for '{rel_path}': expected {file_meta['sha256']}, got {actual_hash}"
                )

    def run_all_validations(self) -> dict:
        """Execute complete validation suite and generate reports."""
        self.load_data()
        self.validate_pk_uniqueness()
        self.validate_referential_integrity()
        self.validate_financial_consistency()
        self.validate_ground_truth()
        self.validate_manifest()

        is_valid = len(self.errors) == 0
        total_records = sum(len(df) for df in self.tables.values())

        report_data = {
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "PASSED" if is_valid else "FAILED",
            "total_tables_checked": len(self.tables),
            "total_records_checked": total_records,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }

        # Export validation reports
        val_dir = self.data_dir / "validation"
        val_dir.mkdir(parents=True, exist_ok=True)

        json_report_file = val_dir / "validation_report.json"
        with open(json_report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        md_report_file = val_dir / "validation_report.md"
        with open(md_report_file, "w", encoding="utf-8") as f:
            f.write("# Synthetic Data Quality Validation Report\n\n")
            f.write(f"- **Status**: `{'PASSED' if is_valid else 'FAILED'}`\n")
            f.write(f"- **Validated At**: `{report_data['validation_timestamp']}`\n")
            f.write(f"- **Total Tables Checked**: `{report_data['total_tables_checked']}`\n")
            f.write(f"- **Total Records Checked**: `{report_data['total_records_checked']:,}`\n")
            f.write(f"- **Error Count**: `{report_data['error_count']}`\n\n")

            f.write("## Table Record Counts\n\n")
            f.write("| Table Name | Record Count |\n")
            f.write("| :--- | :--- |\n")
            for tbl, df in self.tables.items():
                f.write(f"| `{tbl}` | {len(df):,} |\n")

            f.write("\n## Ground Truth Anomaly Breakdown\n\n")
            f.write("| Anomaly Issue Type | Count |\n")
            f.write("| :--- | :--- |\n")
            for issue, count in self.metrics.get("ground_truth_issue_types", {}).items():
                f.write(f"| `{issue}` | {count} |\n")

            if self.errors:
                f.write("\n## Validation Errors\n\n")
                for err in self.errors:
                    f.write(f"- ❌ {err}\n")

        print(f"\nValidation Summary: {'PASSED' if is_valid else 'FAILED'}")
        print(f"Total Tables: {len(self.tables)} | Total Rows: {total_records:,} | Errors: {len(self.errors)}")
        if self.errors:
            for err in self.errors[:10]:
                print(f"  ❌ {err}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")

        return report_data


def main():
    parser = argparse.ArgumentParser(description="Synthetic Insurance Claims Data Validator")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/synthetic",
        help="Root path containing synthetic data exports (default: data/synthetic)",
    )
    args = parser.parse_args()

    validator = DataValidator(Path(args.data_dir))
    report = validator.run_all_validations()

    if report["status"] != "PASSED":
        sys.exit(1)


if __name__ == "__main__":
    main()
