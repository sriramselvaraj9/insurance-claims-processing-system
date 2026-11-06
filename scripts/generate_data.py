"""CLI entrypoint for synthetic data generation and ground truth compilation."""

import argparse
from pathlib import Path
import sys

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


def run_pipeline(scale: str = "full", seed: int = 20261022, output_dir: Path | None = None) -> dict:
    """Execute the end-to-end deterministic data generation pipeline."""
    target_dir = output_dir or Path("data/synthetic")
    config = get_generation_config(scale=scale, seed=seed)

    print(f"=== Synthetic Data Generation Engine ===")
    print(f"Scale: {scale.upper()} | Seed: {seed} | Output: {target_dir}")
    print(f"Target Policies: {config.num_policies} | Target Claims: {config.num_claims}")

    # 1. Base entities
    print("Generating Customers...")
    customers = generate_customers(config.num_customers, seed=config.seed)

    print(f"Generating Policies ({config.num_policies})...")
    policies = generate_policies(config.num_policies, customers=customers, seed=config.seed)

    print("Generating Coverages...")
    coverages = generate_coverages(policies=policies, seed=config.seed)

    print("Generating Adjusters...")
    adjusters = generate_adjusters(config.num_adjusters, seed=config.seed)

    print("Generating Incidents...")
    incidents = generate_incidents(config.num_claims, seed=config.seed)

    # 2. Claims
    print(f"Generating Claims ({config.num_claims})...")
    claims = generate_claims(
        count=config.num_claims,
        policies=policies,
        incidents=incidents,
        seed=config.seed,
    )

    # 3. Anomaly Injection & Ground Truth
    print("Injecting Anomaly Scenarios & Establishing Isolated Ground Truth...")
    anomaly_plan = plan_and_inject_anomalies(
        config=config,
        claims=claims,
        policies=policies,
        coverages=coverages,
        incidents=incidents,
        seed=config.seed,
    )

    # 4. Claim Line Items
    print("Generating Claim Items (Strict Sum Matching)...")
    claim_items = generate_claim_items(claims=claims, coverages=coverages, seed=config.seed)

    # 5. Documents
    print("Generating Documents & Emitting Document Requests...")
    documents, missing_docs_map = generate_documents(
        claims=claims,
        missing_doc_claim_ids=anomaly_plan.missing_doc_claim_ids,
        seed=config.seed,
    )

    # 6. Assessments
    print("Evaluating Eligibility & Generating Assessments...")
    assessments = generate_assessments(
        claims=claims,
        policies=policies,
        coverages=coverages,
        incidents=incidents,
        documents=documents,
        anomaly_plan=anomaly_plan,
        seed=config.seed,
    )

    # 7. Reserves
    print("Calculating Preliminary Reserves (12% Expense Ratio)...")
    reserves = generate_reserves(
        claims=claims,
        policies=policies,
        coverages=coverages,
        seed=config.seed,
    )

    # 8. Settlements & Payments
    print("Calculating Settlements & Generating Disbursements...")
    settlements, payments = generate_settlements_and_payments(
        claims=claims,
        policies=policies,
        coverages=coverages,
        assessments=assessments,
        anomaly_plan=anomaly_plan,
        seed=config.seed,
    )

    # 9. Supporting Records
    print("Generating Adjuster Assignments, Status Histories, and Audit Events...")
    assignments, doc_requests, status_histories, audit_events = generate_supporting_records(
        claims=claims,
        adjusters=adjusters,
        missing_docs_map=missing_docs_map,
        seed=config.seed,
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
        "document_requests": doc_requests,
        "settlement_payments": payments,
        "claim_status_history": status_histories,
        "audit_events": audit_events,
    }

    # 10. Export Datasets
    print("Exporting Datasets to CSV, JSON, SQL, and Isolated Ground Truth...")
    manifest = export_all_datasets(
        output_dir=target_dir,
        scale=scale,
        seed=seed,
        dataset_map=dataset_map,
        ground_truth_records=anomaly_plan.ground_truth_records,
    )

    print("\nGeneration Complete!")
    print(f"Total Tables Exported: {manifest['total_tables']}")
    print(f"Total Rows Exported: {manifest['total_records']}")
    print(f"Ground Truth Anomalies Logged: {manifest['ground_truth_anomalies_count']}")
    for tbl, count in manifest["table_record_counts"].items():
        print(f"  - {tbl:<25}: {count:>6} records")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Deterministic Insurance Claims Data Generator")
    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="full",
        help="Scale preset ('starter' for unit tests, 'full' for exact 2,000 policies and 1,000 claims)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20261022,
        help="Random seed for deterministic reproducibility (default: 20261022)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/synthetic",
        help="Output root directory for data exports (default: data/synthetic)",
    )

    args = parser.parse_args()
    run_pipeline(scale=args.scale, seed=args.seed, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
