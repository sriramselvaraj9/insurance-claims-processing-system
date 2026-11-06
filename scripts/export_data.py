"""Export engine for synthetic data, ground truth, manifests, and SQL seed scripts."""

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any
import pandas as pd

from app.models.base import Base
from scripts.generators.anomaly_injector import GroundTruthRecord


def entity_to_dict(entity: Base) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance into a JSON/CSV serializable dictionary."""
    result: dict[str, Any] = {}
    for prop in entity.__mapper__.column_attrs:
        python_attr = prop.key
        sql_col_name = prop.columns[0].name
        val = getattr(entity, python_attr)
        if isinstance(val, (datetime, date)):
            result[sql_col_name] = val.isoformat()
        elif isinstance(val, Decimal):
            result[sql_col_name] = str(val)
        elif hasattr(val, "value"):  # Enum
            result[sql_col_name] = val.value
        elif isinstance(val, (list, dict)):
            result[sql_col_name] = json.dumps(val)
        else:
            result[sql_col_name] = val
    return result


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def format_sql_value(val: Any) -> str:
    """Format a python value into a valid PostgreSQL SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    if hasattr(val, "value"):  # Enum
        escaped = str(val.value).replace("'", "''")
        return f"'{escaped}'"
    if isinstance(val, (dict, list)):
        escaped = json.dumps(val).replace("'", "''")
        return f"'{escaped}'"
    
    escaped_str = str(val).replace("'", "''")
    return f"'{escaped_str}'"


def generate_sql_insert(table_name: str, entity: Base) -> str:
    """Generate a single PostgreSQL INSERT statement for an entity."""
    columns = []
    values = []
    for prop in entity.__mapper__.column_attrs:
        columns.append(prop.columns[0].name)
        values.append(format_sql_value(getattr(entity, prop.key)))
    cols_str = ", ".join(columns)
    vals_str = ", ".join(values)
    return f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str});"


def export_all_datasets(
    output_dir: Path,
    scale: str,
    seed: int,
    dataset_map: dict[str, list[Base]],
    ground_truth_records: list[GroundTruthRecord],
) -> dict[str, Any]:
    """Export all tables to CSV, JSON, and SQL seed scripts, plus isolated ground truth and manifest."""
    csv_dir = output_dir / "csv"
    json_dir = output_dir / "json"
    sql_dir = output_dir / "sql"
    gt_dir = output_dir / "ground_truth"
    manifest_dir = output_dir / "manifests"

    for d in [csv_dir, json_dir, sql_dir, gt_dir, manifest_dir]:
        d.mkdir(parents=True, exist_ok=True)

    file_manifest: dict[str, Any] = {}
    total_records = 0

    # 1. Export CSV and JSON for all domain tables
    for table_name, entities in dataset_map.items():
        records = [entity_to_dict(e) for e in entities]
        total_records += len(records)

        # CSV
        csv_file = csv_dir / f"{table_name}.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_file, index=False)
        csv_hash = compute_file_sha256(csv_file)
        file_manifest[f"csv/{table_name}.csv"] = {
            "records": len(records),
            "sha256": csv_hash,
            "size_bytes": csv_file.stat().st_size,
        }

        # JSON
        json_file = json_dir / f"{table_name}.json"
        # Parse JSON string fields back to objects for clean JSON output
        parsed_records = []
        for r in records:
            clean_r = dict(r)
            for k, v in clean_r.items():
                if isinstance(v, str) and (v.startswith("[") or v.startswith("{")):
                    try:
                        clean_r[k] = json.loads(v)
                    except json.JSONDecodeError:
                        pass
            parsed_records.append(clean_r)

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(parsed_records, f, indent=2)
        json_hash = compute_file_sha256(json_file)
        file_manifest[f"json/{table_name}.json"] = {
            "records": len(records),
            "sha256": json_hash,
            "size_bytes": json_file.stat().st_size,
        }

    # 2. Export SQL Seed Script in strict foreign key order
    sql_seed_file = sql_dir / "seed_data.sql"
    fk_order = [
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

    with open(sql_seed_file, "w", encoding="utf-8") as f:
        f.write("-- ==========================================================================\n")
        f.write(f"-- PostgreSQL Seed Data Script\n")
        f.write(f"-- Scale: {scale} | Seed: {seed}\n")
        f.write("-- Foreign Key Insertion Order: Customers -> Policies -> Coverages -> ...\n")
        f.write("-- ==========================================================================\n\n")
        f.write("BEGIN;\n\n")

        for table_name in fk_order:
            entities = dataset_map.get(table_name, [])
            if entities:
                f.write(f"-- Table: {table_name} ({len(entities)} rows)\n")
                for entity in entities:
                    insert_stmt = generate_sql_insert(table_name, entity)
                    f.write(f"{insert_stmt}\n")
                f.write("\n")

        f.write("COMMIT;\n")

    sql_hash = compute_file_sha256(sql_seed_file)
    file_manifest["sql/seed_data.sql"] = {
        "records": total_records,
        "sha256": sql_hash,
        "size_bytes": sql_seed_file.stat().st_size,
    }

    # 3. Export Isolated Ground Truth (CSV and JSON)
    gt_dicts = [r.to_dict() for r in ground_truth_records]
    gt_csv_file = gt_dir / "ground_truth.csv"
    gt_df = pd.DataFrame(gt_dicts)
    gt_df.to_csv(gt_csv_file, index=False)
    gt_csv_hash = compute_file_sha256(gt_csv_file)
    file_manifest["ground_truth/ground_truth.csv"] = {
        "records": len(gt_dicts),
        "sha256": gt_csv_hash,
        "size_bytes": gt_csv_file.stat().st_size,
    }

    gt_json_file = gt_dir / "ground_truth.json"
    with open(gt_json_file, "w", encoding="utf-8") as f:
        json.dump(gt_dicts, f, indent=2)
    gt_json_hash = compute_file_sha256(gt_json_file)
    file_manifest["ground_truth/ground_truth.json"] = {
        "records": len(gt_dicts),
        "sha256": gt_json_hash,
        "size_bytes": gt_json_file.stat().st_size,
    }

    # 4. Export Source Manifest
    manifest_data = {
        "manifest_version": "1.0.0",
        "scale": scale,
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_tables": len(dataset_map),
        "total_records": total_records,
        "ground_truth_anomalies_count": len(gt_dicts),
        "table_record_counts": {k: len(v) for k, v in dataset_map.items()},
        "files": file_manifest,
    }

    manifest_file = manifest_dir / "source_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_data
