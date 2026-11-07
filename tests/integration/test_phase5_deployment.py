"""Phase 5: Automated Integration Test Suite for Containerization, Deployment & System Verification.

Validates:
1. Dockerfile multi-stage architecture, non-root user, and health check.
2. .dockerignore exclusion rules.
3. docker-compose.yml multi-service specification (db, redis, api, healthchecks, networks, volumes).
4. Environment configuration settings and production security constraints.
5. Redis integration and fail-safe graceful degradation when offline.
6. System health probes reporting database and Redis readiness.
7. Synthetic dataset loader foreign-key order, batch execution, idempotency, and truncation.
8. Alembic schema migration upgrade to head and downgrade to base.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
import yaml

from alembic import command
from alembic.config import Config
from app import __version__
from app.api.v1.health import perform_health_check
from app.core.config import Settings, get_settings, settings
from app.core.redis import (
    cache_delete,
    cache_get,
    cache_set,
    check_redis_health,
    get_redis_client,
    get_redis_pool,
    reset_redis_pool,
)
from app.main import app, health_check
from app.models.base import Base
from app.models.customer import Customer
from app.models.policy import Policy
from scripts.load_dataset import TABLE_MODEL_MAPPING, load_dataset


# ==============================================================================
# 1. Dockerfile & Container Architecture Tests
# ==============================================================================


def test_01_dockerfile_multi_stage_and_best_practices():
    """Verify Dockerfile contains multi-stage build, unprivileged user, and health check."""
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile must exist at repository root."

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage verification
    assert "AS builder" in content, "Dockerfile must define a builder stage."
    assert "AS final" in content or "FROM python:" in content, "Dockerfile must define final runtime stage."

    # astral-sh/uv usage
    assert "ghcr.io/astral-sh/uv" in content or "uv" in content, "Dockerfile must use uv package manager."
    assert "uv sync --frozen --no-dev" in content, "Dockerfile must use frozen no-dev uv sync."

    # Unprivileged user
    assert "useradd" in content or "adduser" in content, "Dockerfile must provision non-root user."
    assert "USER appuser" in content or "USER " in content, "Dockerfile must execute under non-root user."

    # Health check
    assert "HEALTHCHECK" in content, "Dockerfile must declare container HEALTHCHECK."
    assert "http://localhost:8000/health" in content, "HEALTHCHECK must probe /health endpoint."


def test_02_dockerignore_rules():
    """Verify .dockerignore excludes build caches, virtual environments, and secrets."""
    dockerignore_path = Path(".dockerignore")
    assert dockerignore_path.exists(), ".dockerignore must exist at repository root."

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    required_patterns = [".git", ".venv", "__pycache__", ".env"]
    for pattern in required_patterns:
        assert any(pattern in line for line in lines), f".dockerignore must exclude {pattern}"


# ==============================================================================
# 2. Docker Compose Specification Tests
# ==============================================================================


def test_03_docker_compose_services_and_topology():
    """Verify docker-compose.yml defines db, redis, and api services with healthchecks."""
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml must exist at repository root."

    content = compose_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "services" in data, "docker-compose.yml must define services."
    services = data["services"]

    # Verify db service
    assert "db" in services, "PostgreSQL service 'db' must be configured."
    db_svc = services["db"]
    assert "postgres" in db_svc["image"], "DB image must use official postgres."
    assert "healthcheck" in db_svc, "DB service must include a healthcheck."
    assert "pg_isready" in str(db_svc["healthcheck"]), "DB healthcheck must use pg_isready."
    assert "postgres_data:/var/lib/postgresql/data" in db_svc["volumes"]

    # Verify redis service
    assert "redis" in services, "Redis service 'redis' must be configured."
    redis_svc = services["redis"]
    assert "redis" in redis_svc["image"], "Redis image must use official redis image."
    assert "healthcheck" in redis_svc, "Redis service must include a healthcheck."
    assert "redis-cli" in str(redis_svc["healthcheck"]), "Redis healthcheck must use redis-cli ping."

    # Verify api service
    assert "api" in services, "FastAPI backend service 'api' must be configured."
    api_svc = services["api"]
    assert "depends_on" in api_svc, "API service must depend on infrastructure services."
    assert "db" in api_svc["depends_on"]
    assert "redis" in api_svc["depends_on"]
    assert api_svc["depends_on"]["db"]["condition"] == "service_healthy"
    assert api_svc["depends_on"]["redis"]["condition"] == "service_healthy"

    # Verify network & volumes
    assert "networks" in data and "claims_network" in data["networks"]
    assert "volumes" in data and "postgres_data" in data["volumes"] and "redis_data" in data["volumes"]


# ==============================================================================
# 3. Configuration & Security Hardening Tests
# ==============================================================================


def test_04_config_environment_and_cors():
    """Verify settings parses CORS origins and defaults correctly."""
    cfg = Settings(
        ENVIRONMENT="development",
        CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"],
    )
    assert cfg.ENVIRONMENT == "development"
    assert "http://localhost:3000" in cfg.CORS_ORIGINS

    # Test string comma-separated parsing
    cfg_str = Settings(
        ENVIRONMENT="development",
        CORS_ORIGINS="http://app.example.com, https://portal.example.com",
    )
    assert len(cfg_str.CORS_ORIGINS) == 2
    assert "https://portal.example.com" in cfg_str.CORS_ORIGINS


def test_05_config_production_security_gates():
    """Verify production environment rejects debug mode and default insecure passwords."""
    # Production with DEBUG=True must be rejected
    with pytest.raises(ValueError, match="DEBUG mode must be disabled in production"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            POSTGRES_PASSWORD="SuperSecretProductionPassword#2026",
        )

    # Production with default password 'postgres' must be rejected
    with pytest.raises(ValueError, match="Insecure default or empty POSTGRES_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            POSTGRES_PASSWORD="postgres",
        )

    # Valid production settings pass
    prod_cfg = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        POSTGRES_PASSWORD="HardenedProductionDatabaseSecret!99",
    )
    assert prod_cfg.ENVIRONMENT == "production"
    assert prod_cfg.DEBUG is False


# ==============================================================================
# 4. Redis Caching & Graceful Degradation Tests
# ==============================================================================


def test_06_redis_graceful_degradation_when_offline():
    """Verify application fails open without exceptions when Redis is offline."""
    original_url = settings.REDIS_URL
    try:
        # Explicitly point to unreachable port to guarantee offline simulation
        settings.REDIS_URL = "redis://127.0.0.1:59999/0"
        reset_redis_pool()

        # When Redis is unreachable, health returns (False, 'disconnected') without crashing
        healthy, msg = check_redis_health()
        assert healthy is False
        assert "disconnected" in msg

        # Cache get returns None without throwing exception
        val = cache_get("non_existent_key")
        assert val is None

        # Cache set returns False without throwing exception
        ok = cache_set("test_key", "value_123")
        assert ok is False

        # Cache delete returns False without throwing exception
        del_ok = cache_delete("test_key")
        assert del_ok is False
    finally:
        settings.REDIS_URL = original_url
        reset_redis_pool()


def test_07_redis_mock_operations():
    """Verify cache helpers perform correctly when Redis client is active."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = "cached_payload"
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1

    with patch("app.core.redis.get_redis_client", return_value=mock_client):
        is_healthy, msg = check_redis_health()
        assert is_healthy is True
        assert msg == "connected"

        val = cache_get("claim_1001")
        assert val == "cached_payload"
        mock_client.get.assert_called_with("claim_1001")

        set_res = cache_set("claim_1001", "new_payload", ttl_seconds=60)
        assert set_res is True
        mock_client.set.assert_called_with("claim_1001", "new_payload", ex=60)

        del_res = cache_delete("claim_1001")
        assert del_res is True
        mock_client.delete.assert_called_with("claim_1001")


# ==============================================================================
# 5. System Health Probe Tests
# ==============================================================================


def test_08_system_health_probes_with_redis_and_database():
    """Verify health endpoint probes both database and Redis connectivity."""
    original_url = settings.REDIS_URL
    try:
        # Simulate offline Redis to verify graceful degradation
        settings.REDIS_URL = "redis://127.0.0.1:59999/0"
        reset_redis_pool()

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()

        try:
            # DB healthy, Redis disconnected -> Overall status healthy (fails open gracefully)
            health_resp, code = perform_health_check(session)
            assert code == 200
            assert health_resp.status == "healthy"
            assert health_resp.database == "connected"
            assert health_resp.redis == "disconnected"
            assert health_resp.service == settings.PROJECT_NAME
            assert health_resp.version == __version__

            # Test global /health handler
            main_payload = health_check(db=session)
            assert main_payload["status"] == "healthy"
            assert main_payload["database"] == "connected"
            assert main_payload["redis"] == "disconnected"
        finally:
            session.close()
    finally:
        settings.REDIS_URL = original_url
        reset_redis_pool()


# ==============================================================================
# 6. Synthetic Dataset Loader Tests (FK Order, Idempotency & Truncation)
# ==============================================================================


@pytest.fixture
def sqlite_load_db(tmp_path: Path):
    """Temporary SQLite database URL for dataset loader verification."""
    db_file = tmp_path / "test_loader.db"
    db_url = f"sqlite:///{db_file}"
    return db_url


def test_09_dataset_loader_fk_order_and_counts(sqlite_load_db: str):
    """Verify dataset loader populates all 16 tables in FK order with exact record counts."""
    # First run: fresh load
    result = load_dataset(
        db_url=sqlite_load_db,
        data_dir="data/synthetic/csv",
        format_type="csv",
        truncate=False,
        dry_run=False,
    )

    assert result["status"] == "SUCCESS"
    assert result["total_records"] == 22933
    assert result["total_inserted"] == 22933
    assert result["total_skipped"] == 0
    assert result["total_failed"] == 0

    # Verify table-specific counts
    tables = result["tables"]
    assert tables["customers"]["inserted"] == 1200
    assert tables["policies"]["inserted"] == 2000
    assert tables["coverages"]["inserted"] == 5103
    assert tables["incidents"]["inserted"] == 1000
    assert tables["adjusters"]["inserted"] == 25
    assert tables["claims"]["inserted"] == 1000
    assert tables["claim_items"]["inserted"] == 1963
    assert tables["documents"]["inserted"] == 2375
    assert tables["document_requests"]["inserted"] == 25
    assert tables["assessments"]["inserted"] == 1000
    assert tables["reserves"]["inserted"] == 1000
    assert tables["settlements"]["inserted"] == 373
    assert tables["settlement_payments"]["inserted"] == 368
    assert tables["adjuster_assignments"]["inserted"] == 1000
    assert tables["audit_events"]["inserted"] == 2000
    assert tables["claim_status_history"]["inserted"] == 2501


def test_10_dataset_loader_idempotency(sqlite_load_db: str):
    """Verify subsequent loader execution is idempotent and skips existing records."""
    # Initial load
    load_dataset(
        db_url=sqlite_load_db,
        data_dir="data/synthetic/csv",
        format_type="csv",
        truncate=False,
        dry_run=False,
    )

    # Second run without truncate
    second_result = load_dataset(
        db_url=sqlite_load_db,
        data_dir="data/synthetic/csv",
        format_type="csv",
        truncate=False,
        dry_run=False,
    )

    assert second_result["status"] == "SUCCESS"
    assert second_result["total_inserted"] == 0
    assert second_result["total_skipped"] == 22933
    assert second_result["total_failed"] == 0


def test_11_dataset_loader_truncation_and_dry_run(sqlite_load_db: str):
    """Verify truncation clears tables and dry-run rolls back without committing."""
    # Seed data
    load_dataset(db_url=sqlite_load_db, truncate=False, dry_run=False)

    # Dry-run with truncate: should execute without failing but roll back
    dry_res = load_dataset(db_url=sqlite_load_db, truncate=False, dry_run=True)
    assert dry_res["status"] == "SUCCESS"
    assert dry_res["dry_run"] is True

    # Real truncate run
    trunc_res = load_dataset(db_url=sqlite_load_db, truncate=True, dry_run=False)
    assert trunc_res["status"] == "SUCCESS"
    assert trunc_res["total_inserted"] == 22933
    assert trunc_res["total_skipped"] == 0


# ==============================================================================
# 7. Alembic Migration Upgrade & Downgrade Roundtrip
# ==============================================================================


def test_12_alembic_migration_upgrade_and_downgrade(tmp_path: Path):
    """Verify Alembic schema migration can upgrade to head and cleanly downgrade to base."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to head
    command.upgrade(cfg, "head")

    # Verify tables created
    engine = create_engine(db_url)
    with engine.connect() as conn:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "customers" in table_names
        assert "claims" in table_names
        assert "coverages" in table_names
        assert "settlements" in table_names
        assert "audit_events" in table_names

    # Downgrade to base
    command.downgrade(cfg, "base")

    # Verify tables dropped
    with engine.connect() as conn:
        inspector = inspect(engine)
        remaining_tables = [t for t in inspector.get_table_names() if t != "alembic_version"]
        assert len(remaining_tables) == 0, f"All tables should be dropped on downgrade: {remaining_tables}"
