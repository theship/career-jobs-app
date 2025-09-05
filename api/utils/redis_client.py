"""
Centralized Redis connection manager
REQUIRED for security features - no fallbacks
"""

import logging
import sys
from typing import Optional

import redis
from redis import ConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError

from api.utils.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool (shared across all Redis clients)
_connection_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def get_connection_pool() -> ConnectionPool:
    """
    Get or create the Redis connection pool

    Returns:
        ConnectionPool instance

    Raises:
        SystemExit: If Redis is not available (REQUIRED dependency)
    """
    global _connection_pool

    if _connection_pool is None:
        settings = get_settings()

        # Create connection pool with sensible defaults
        _connection_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            decode_responses=True,
            health_check_interval=30,
        )

        # Test the connection immediately
        test_client = Redis(connection_pool=_connection_pool)
        try:
            test_client.ping()
            logger.info(f"Redis connected successfully to {settings.redis_url}")
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis connection failed: {e}")
            logger.error("Redis is REQUIRED. Please ensure Redis is running.")
            logger.error(
                "Install: brew install redis (macOS) or apt-get install redis-server (Linux)"
            )
            logger.error(
                "Start: redis-server or docker run -d -p 6379:6379 redis:7-alpine"
            )
            sys.exit(1)

    return _connection_pool


def get_redis_client() -> Redis:
    """
    Get the shared Redis client instance

    Returns:
        Redis client

    Raises:
        SystemExit: If Redis is not available
    """
    global _redis_client

    if _redis_client is None:
        pool = get_connection_pool()
        _redis_client = Redis(connection_pool=pool)

    return _redis_client


def verify_redis_connection() -> bool:
    """
    Verify Redis is connected and responsive

    Returns:
        True if Redis is available

    Raises:
        SystemExit: If Redis is not available
    """
    try:
        client = get_redis_client()
        response = client.ping()

        if response:
            # Log Redis server info
            info = client.info("server")
            logger.info(
                f"Redis server info: version={info.get('redis_version')}, "
                f"mode={info.get('redis_mode', 'standalone')}"
            )

            # Check memory usage
            memory_info = client.info("memory")
            used_memory_mb = memory_info.get("used_memory", 0) / (1024 * 1024)
            logger.info(f"Redis memory usage: {used_memory_mb:.2f} MB")

            return True
    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Redis verification failed: {e}")
        logger.error("Redis is REQUIRED for this application to function.")
        sys.exit(1)

    return False


def close_redis_connection():
    """Close the Redis connection pool (for cleanup)"""
    global _connection_pool, _redis_client

    if _redis_client:
        _redis_client.close()
        _redis_client = None

    if _connection_pool:
        _connection_pool.disconnect()
        _connection_pool = None
        logger.info("Redis connection pool closed")


# Convenience functions for common operations
def get_with_prefix(key: str, prefix: str = "app") -> Optional[str]:
    """Get a value with key prefix"""
    client = get_redis_client()
    return client.get(f"{prefix}:{key}")


def set_with_prefix(
    key: str, value: str, prefix: str = "app", ex: Optional[int] = None
) -> bool:
    """Set a value with key prefix and optional expiry"""
    client = get_redis_client()
    return client.set(f"{prefix}:{key}", value, ex=ex)


def delete_with_prefix(key: str, prefix: str = "app") -> int:
    """Delete a key with prefix"""
    client = get_redis_client()
    return client.delete(f"{prefix}:{key}")


# Export the main functions
__all__ = [
    "get_redis_client",
    "verify_redis_connection",
    "close_redis_connection",
    "get_with_prefix",
    "set_with_prefix",
    "delete_with_prefix",
]
