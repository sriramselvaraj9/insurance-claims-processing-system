from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path):
    """Verify that Alembic initial migration can be applied and rolled back on a fresh database."""
    test_db_path = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{test_db_path.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Apply upgrade to head
    command.upgrade(alembic_cfg, "head")

    # 2. Inspect created tables
    engine = create_engine(db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    required_tables = {
        "customers",
        "policies",
        "coverages",
        "incidents",
        "adjusters",
        "claims",
        "claim_items",
        "documents",
        "document_requests",
        "adjuster_assignments",
        "assessments",
        "reserves",
        "settlements",
        "settlement_payments",
        "claim_status_history",
        "audit_events",
    }
    assert required_tables.issubset(table_names), f"Missing tables: {required_tables - table_names}"
    engine.dispose()

    # 3. Test downgrade to base
    command.downgrade(alembic_cfg, "base")

    # 4. Inspect that all domain tables were dropped
    engine = create_engine(db_url)
    inspector = inspect(engine)
    remaining_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert len(remaining_tables) == 0, f"Tables not dropped during downgrade: {remaining_tables}"
    engine.dispose()
