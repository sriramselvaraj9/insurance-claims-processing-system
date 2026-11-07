"""Synthetic dataset loader for PostgreSQL and relational databases.

Loads generated synthetic datasets (CSV or JSON) into target relational databases
respecting strict foreign-key dependency order, handling idempotency and conflicts,
and providing comprehensive audit statistics.
"""

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

# Ensure repository root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.adjuster import Adjuster
from app.models.adjuster_assignment import AdjusterAssignment
from app.models.assessment import Assessment
from app.models.audit_event import AuditEvent
from app.models.base import Base
from app.models.claim import Claim
from app.models.claim_item import ClaimItem
from app.models.claim_status_history import ClaimStatusHistory
from app.models.coverage import Coverage
from app.models.customer import Customer
from app.models.document import Document
from app.models.document_request import DocumentRequest
from app.models.incident import Incident
from app.models.policy import Policy
from app.models.reserve import Reserve
from app.models.settlement import Settlement
from app.models.settlement_payment import SettlementPayment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("load_dataset")

# Ordered by strict foreign key dependency hierarchy (Level 1 -> Level 5)
TABLE_MODEL_MAPPING = [
    ("customers", Customer),
    ("adjusters", Adjuster),
    ("incidents", Incident),
    ("policies", Policy),
    ("coverages", Coverage),
    ("claims", Claim),
    ("claim_items", ClaimItem),
    ("documents", Document),
    ("document_requests", DocumentRequest),
    ("assessments", Assessment),
    ("reserves", Reserve),
    ("settlements", Settlement),
    ("settlement_payments", SettlementPayment),
    ("adjuster_assignments", AdjusterAssignment),
    ("audit_events", AuditEvent),
    ("claim_status_history", ClaimStatusHistory),
]


def cast_column_value(val: Any, col: Any) -> Any:
    """Cast string or raw values from CSV/JSON into Python types matching SQLAlchemy columns."""
    if pd.isna(val) or val is None or val == "" or val == "None" or val == "null":
        return None

    ptype = getattr(col.type, "python_type", None)
    if ptype is not None:
        try:
            if issubclass(ptype, Enum):
                return ptype(str(val))
        except TypeError:
            pass

        if ptype is date:
            if isinstance(val, (datetime, date)):
                return val if isinstance(val, date) else val.date()
            return date.fromisoformat(str(val)[:10])

        if ptype is datetime:
            if isinstance(val, datetime):
                return val
            # Handle ISO format with or without timezone
            clean_str = str(val).replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str)

        if ptype is Decimal:
            return Decimal(str(val))

        if ptype is bool:
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ("true", "1", "t", "yes")

        if ptype is int:
            return int(float(val))

        if ptype is str:
            return str(val)

    if "JSON" in type(col.type).__name__:
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    return val


def load_dataset(
    db_url: str | None = None,
    data_dir: Path | str = "data/synthetic/csv",
    format_type: str = "csv",
    truncate: bool = False,
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Load dataset into target database with FK dependency ordering and conflict handling.

    Returns:
        dict[str, Any]: Execution summary containing table-by-table counts and timings.
    """
    data_path = Path(data_dir)
    target_db_url = db_url or settings.DATABASE_URL

    logger.info("Connecting to target database: %s", target_db_url)
    engine = create_engine(target_db_url, echo=False)
    # Ensure tables exist (especially helpful for fresh testing DBs)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    summary: dict[str, dict[str, Any]] = {}
    total_start = time.perf_counter()

    with SessionLocal() as session:
        # Step 1: Optional table truncation in reverse FK order
        if truncate:
            logger.info("Truncating tables in reverse foreign key order...")
            for table_name, model in reversed(TABLE_MODEL_MAPPING):
                try:
                    deleted = session.execute(model.__table__.delete()).rowcount
                    logger.info("Truncated table '%s': deleted %d rows", table_name, deleted)
                except Exception as exc:
                    logger.warning("Error truncating table '%s': %s", table_name, exc)
            session.commit()

        # Step 2: Load tables in forward FK order
        for table_name, model in TABLE_MODEL_MAPPING:
            t0 = time.perf_counter()
            file_name = f"{table_name}.{format_type}"
            file_path = data_path / file_name

            if not file_path.exists():
                logger.warning("Dataset file not found: %s. Skipping.", file_path)
                summary[table_name] = {
                    "total": 0,
                    "inserted": 0,
                    "skipped": 0,
                    "failed": 0,
                    "status": "FILE_NOT_FOUND",
                    "duration_sec": 0.0,
                }
                continue

            # Read source records
            if format_type == "csv":
                df = pd.read_csv(file_path, dtype=object)
                records = df.to_dict(orient="records")
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    records = json.load(f)

            total_records = len(records)
            inserted_count = 0
            skipped_count = 0
            failed_count = 0

            # Idempotency check: query existing primary keys
            existing_ids: set[str] = set()
            try:
                existing_ids = set(session.scalars(select(model.id)).all())
            except Exception as exc:
                logger.debug("Could not query existing IDs for %s: %s", table_name, exc)

            # Filter records not yet in DB
            to_insert_records = []
            for r in records:
                rec_id = str(r.get("id"))
                if rec_id in existing_ids:
                    skipped_count += 1
                else:
                    to_insert_records.append(r)

            # Cast and prepare batch payloads
            table_cols = {col.name: col for col in model.__table__.columns}
            batch_payloads = []
            for r in to_insert_records:
                try:
                    clean_row = {}
                    for col_name, col in table_cols.items():
                        if col_name in r:
                            clean_row[col_name] = cast_column_value(r[col_name], col)
                    batch_payloads.append(clean_row)
                except Exception as exc:
                    logger.error("Error parsing row in %s (ID %s): %s", table_name, r.get("id"), exc)
                    failed_count += 1

            # Batch execution
            for i in range(0, len(batch_payloads), batch_size):
                chunk = batch_payloads[i : i + batch_size]
                try:
                    session.execute(model.__table__.insert(), chunk)
                    inserted_count += len(chunk)
                except Exception as batch_exc:
                    logger.warning(
                        "Batch insert failed for %s chunk [%d:%d]: %s. Retrying row-by-row.",
                        table_name,
                        i,
                        i + len(chunk),
                        batch_exc,
                    )
                    session.rollback()
                    # Fallback to single-row insertion to isolate failures
                    for row in chunk:
                        try:
                            session.execute(model.__table__.insert().values(**row))
                            inserted_count += 1
                        except Exception as row_exc:
                            logger.error(
                                "Failed inserting %s ID %s: %s",
                                table_name,
                                row.get("id"),
                                row_exc,
                            )
                            failed_count += 1

            if not dry_run:
                session.commit()
            else:
                session.rollback()

            elapsed = round(time.perf_counter() - t0, 3)
            logger.info(
                "Table '%s': Total=%d, Inserted=%d, Skipped=%d, Failed=%d (%0.2fs)",
                table_name,
                total_records,
                inserted_count,
                skipped_count,
                failed_count,
                elapsed,
            )

            summary[table_name] = {
                "total": total_records,
                "inserted": inserted_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "status": "SUCCESS" if failed_count == 0 else "PARTIAL_FAILURE",
                "duration_sec": elapsed,
            }

    total_time = round(time.perf_counter() - total_start, 3)
    grand_total = sum(s["total"] for s in summary.values())
    grand_inserted = sum(s["inserted"] for s in summary.values())
    grand_skipped = sum(s["skipped"] for s in summary.values())
    grand_failed = sum(s["failed"] for s in summary.values())

    result = {
        "status": "SUCCESS" if grand_failed == 0 else "FAILURE",
        "dry_run": dry_run,
        "format": format_type,
        "data_dir": str(data_path),
        "total_records": grand_total,
        "total_inserted": grand_inserted,
        "total_skipped": grand_skipped,
        "total_failed": grand_failed,
        "total_duration_sec": total_time,
        "tables": summary,
    }
    return result


def print_summary_table(result: dict[str, Any]) -> None:
    """Print an aligned ASCII summary report of dataset loading."""
    print("\n" + "=" * 80)
    print(" " * 22 + "SYNTHETIC DATASET LOADER SUMMARY REPORT")
    print("=" * 80)
    print(f"Status:       {result['status']}")
    print(f"Data Dir:     {result['data_dir']} ({result['format'].upper()})")
    print(f"Dry Run:      {result['dry_run']}")
    print(f"Total Time:   {result['total_duration_sec']}s")
    print("-" * 80)
    print(f"{'Table Name':<24} | {'Total':>7} | {'Inserted':>8} | {'Skipped':>7} | {'Failed':>6} | {'Time (s)':>8}")
    print("-" * 80)
    for tbl, stats in result["tables"].items():
        print(
            f"{tbl:<24} | {stats['total']:>7} | {stats['inserted']:>8} | "
            f"{stats['skipped']:>7} | {stats['failed']:>6} | {stats['duration_sec']:>8.2f}"
        )
    print("=" * 80)
    print(
        f"{'TOTALS':<24} | {result['total_records']:>7} | "
        f"{result['total_inserted']:>8} | {result['total_skipped']:>7} | "
        f"{result['total_failed']:>6} | {result['total_duration_sec']:>8.2f}"
    )
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load synthetic datasets into PostgreSQL/relational database."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/synthetic/csv",
        help="Path to folder containing CSV or JSON files (default: data/synthetic/csv)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Input file format to load (default: csv)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Target database URL (defaults to DATABASE_URL in settings)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate tables before inserting (reverse FK order)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate loading without committing transactions",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch insert chunk size (default: 500)",
    )
    args = parser.parse_args()

    result = load_dataset(
        db_url=args.db_url,
        data_dir=args.data_dir,
        format_type=args.format,
        truncate=args.truncate,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )
    print_summary_table(result)

    if result["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
