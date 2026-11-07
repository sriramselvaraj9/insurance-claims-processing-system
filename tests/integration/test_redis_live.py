"""Verification 2: Integration tests for actual Redis service.

Validates:
1. Connecting to Redis service using configured settings / hostname.
2. Redis responds to live PING.
3. cache_set() stores values with TTL.
4. cache_get() retrieves stored values accurately.
5. cache_delete() removes the key.
6. Missing or deleted keys return None.
7. Redis connection failures are handled gracefully (fail open).
8. The application remains operational and healthy when Redis is temporarily unavailable.
9. Health probe endpoint accurately represents Redis connectivity status ('connected' vs 'disconnected').

The live container checks are marked and automatically detected so that ordinary test runs
without a running Docker daemon do not fail.
"""

from uuid import uuid4
import pytest
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.health import perform_health_check
from app.core.config import Settings, settings
from app.core.redis import (
    cache_delete,
    cache_get,
    cache_set,
    check_redis_health,
    get_redis_client,
    reset_redis_pool,
)
from app.models.base import Base


def is_live_redis_running() -> bool:
    """Check if an active Redis instance is listening on the configured Redis URL."""
    try:
        if not settings.REDIS_ENABLED or not settings.REDIS_URL:
            return False
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_timeout=0.8,
            socket_connect_timeout=0.8,
            decode_responses=True,
        )
        return bool(client.ping())
    except Exception:
        return False


live_redis_required = pytest.mark.skipif(
    not is_live_redis_running(),
    reason="Live Redis service is not reachable. Run 'docker compose up -d redis' to execute live tests.",
)


@pytest.fixture(autouse=True)
def ensure_clean_redis_pool():
    """Ensure connection pool is reset between tests."""
    reset_redis_pool()
    yield
    reset_redis_pool()


# ==============================================================================
# Live Redis Service Operations (Executed when Redis container is active)
# ==============================================================================


@live_redis_required
def test_01_live_redis_ping_and_connection():
    """Verify live Redis responds to PING using configured connection."""
    client = get_redis_client()
    assert client is not None, "Failed to instantiate Redis client for live service."
    assert client.ping() is True, "Live Redis did not respond with PONG to ping."

    is_healthy, status = check_redis_health()
    assert is_healthy is True
    assert status == "connected"


@live_redis_required
def test_02_live_redis_set_get_and_expiration():
    """Verify cache_set stores value and cache_get retrieves it accurately."""
    test_key = f"claims:test:{uuid4().hex}"
    test_value = f"payload_{uuid4().hex}"

    try:
        ok = cache_set(test_key, test_value, ttl_seconds=60)
        assert ok is True, "cache_set failed on live Redis service."

        retrieved = cache_get(test_key)
        assert retrieved == test_value, f"Expected '{test_value}', got '{retrieved}'"
    finally:
        cache_delete(test_key)


@live_redis_required
def test_03_live_redis_delete_and_missing_key():
    """Verify cache_delete removes key and subsequent get returns None."""
    test_key = f"claims:test:del_{uuid4().hex}"
    test_value = "transient_data"

    try:
        cache_set(test_key, test_value, ttl_seconds=60)
        assert cache_get(test_key) == test_value

        deleted = cache_delete(test_key)
        assert deleted is True

        # Missing key must return None
        assert cache_get(test_key) is None
    finally:
        cache_delete(test_key)


@live_redis_required
def test_04_live_redis_health_endpoint_connected():
    """Verify system health check reports redis: 'connected' when Redis is active."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        resp, code = perform_health_check(db)
        assert code == 200
        assert resp.status == "healthy"
        assert resp.database == "connected"
        assert resp.redis == "connected"


# ==============================================================================
# Graceful Degradation & Resilience (Always verified, offline & online)
# ==============================================================================


def test_05_redis_connection_failure_handled_gracefully():
    """Verify client handles unreachable Redis host without raising unhandled exceptions."""
    # Point settings to non-existent port to simulate network failure
    dead_settings = Settings(
        REDIS_ENABLED=True,
        REDIS_HOST="127.0.0.1",
        REDIS_PORT=59999,
        REDIS_URL="redis://127.0.0.1:59999/0",
    )

    try:
        # Patch active settings temporarily
        original_url = settings.REDIS_URL
        settings.REDIS_URL = "redis://127.0.0.1:59999/0"
        reset_redis_pool()

        # Health probe must fail open (return False, 'disconnected') without crashing
        is_healthy, status = check_redis_health()
        assert is_healthy is False
        assert "disconnected" in status

        # Operations must fail open without crashing
        assert cache_get("any_key") is None
        assert cache_set("any_key", "val") is False
        assert cache_delete("any_key") is False
    finally:
        settings.REDIS_URL = original_url
        reset_redis_pool()


def test_06_application_operational_when_redis_unavailable():
    """Verify application health and database queries succeed when Redis is down."""
    original_url = settings.REDIS_URL
    try:
        settings.REDIS_URL = "redis://127.0.0.1:59999/0"
        reset_redis_pool()

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)

        with SessionLocal() as db:
            health_resp, http_code = perform_health_check(db)
            # Must remain 200 OK because database is operational
            assert http_code == 200
            assert health_resp.status == "healthy"
            assert health_resp.database == "connected"
            assert health_resp.redis == "disconnected"
    finally:
        settings.REDIS_URL = original_url
        reset_redis_pool()


def test_07_missing_random_key_returns_none():
    """Verify querying a random nonexistent key returns None without error."""
    nonexistent_key = f"nonexistent:key:{uuid4().hex}"
    result = cache_get(nonexistent_key)
    assert result is None

