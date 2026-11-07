"""Redis client manager and graceful degradation caching utilities."""

import logging
from typing import Any
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def get_redis_pool() -> redis.ConnectionPool | None:
    """Retrieve or initialize singleton Redis connection pool."""
    global _pool
    if not settings.REDIS_ENABLED or not settings.REDIS_URL:
        return None

    if _pool is None:
        try:
            _pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True,
                max_connections=20,
            )
        except Exception as exc:
            logger.warning("Failed to initialize Redis connection pool: %s", exc)
            return None
    return _pool


def get_redis_client() -> redis.Redis | None:
    """Get an active Redis client, or None if Redis is disabled/unreachable."""
    pool = get_redis_pool()
    if pool is None:
        return None
    try:
        return redis.Redis(connection_pool=pool)
    except Exception as exc:
        logger.warning("Unable to instantiate Redis client: %s", exc)
        return None


def check_redis_health() -> tuple[bool, str]:
    """Probe Redis server connectivity with fail-safe error handling.

    Returns:
        tuple[bool, str]: (is_healthy, status_message)
    """
    if not settings.REDIS_ENABLED:
        return True, "disabled"

    client = get_redis_client()
    if client is None:
        return False, "disconnected"

    try:
        pong = client.ping()
        if pong:
            return True, "connected"
        return False, "unexpected_ping_response"
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        logger.debug("Redis health probe connection error: %s", exc)
        return False, "disconnected"
    except Exception as exc:
        logger.warning("Redis health probe error: %s", exc)
        return False, f"error: {str(exc)}"


def cache_get(key: str) -> str | None:
    """Safely fetch cached value. Fails open (returns None) if Redis is down."""
    try:
        client = get_redis_client()
        if client:
            return client.get(key)
    except Exception as exc:
        logger.debug("Redis cache_get failed for key '%s': %s", key, exc)
    return None


def cache_set(key: str, value: str, ttl_seconds: int | None = None) -> bool:
    """Safely set cached value. Fails open (returns False) if Redis is down."""
    try:
        client = get_redis_client()
        if client:
            ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS
            client.set(key, value, ex=ttl)
            return True
    except Exception as exc:
        logger.debug("Redis cache_set failed for key '%s': %s", key, exc)
    return False


def cache_delete(key: str) -> bool:
    """Safely delete key from cache. Fails open (returns False) if Redis is down."""
    try:
        client = get_redis_client()
        if client:
            client.delete(key)
            return True
    except Exception as exc:
        logger.debug("Redis cache_delete failed for key '%s': %s", key, exc)
    return False


def reset_redis_pool() -> None:
    """Reset the connection pool (primarily for testing and environment shifts)."""
    global _pool
    if _pool:
        try:
            _pool.disconnect()
        except Exception:
            pass
    _pool = None
