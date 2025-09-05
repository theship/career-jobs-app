"""
Advanced rate limiting with per-user, per-IP, and per-route quotas
"""

import hashlib
import time
from functools import wraps
from typing import Any, Dict, Optional

import structlog
from fastapi import HTTPException, Request, status

from api.utils.redis_client import get_redis_client

logger = structlog.get_logger()

# Get Redis client (REQUIRED - will fail fast if not available)
redis_client = get_redis_client()

# Rate limit configurations per endpoint category
RATE_LIMITS = {
    # Edge/CDN level (IP-based)
    "edge": {
        "global": "1000/hour",  # Global per IP
        "burst": "50/minute",  # Burst protection
    },
    # User-level quotas
    "user": {
        "uploads": {
            "resume": "5/hour",
            "skills_vocab": "10/hour",
            "total_files": "20/day",
        },
        "ai_operations": {
            "embeddings": "100/hour",
            "gpt_completions": "50/hour",
            "pitch_generation": "20/hour",
            "research": "30/hour",
        },
        "data_operations": {
            "score_calculations": "200/hour",
            "job_searches": "500/hour",
            "exports": "10/hour",
        },
    },
    # Per-route specific limits
    "routes": {
        "/api/v1/resumes/upload": "5/hour",
        "/api/v1/pitch/generate": "20/hour",
        "/api/v1/research/company": "30/hour",
        "/api/v1/scores/calculate": "100/hour",
        "/api/v1/jobs/search": "200/hour",
        "/api/v1/export/*": "10/hour",
        "/api/v1/embeddings/*": "100/hour",
    },
}


def get_identifier(request: Request, user_id: Optional[str] = None) -> str:
    """
    Get unique identifier for rate limiting
    Combines IP and user ID for accurate tracking
    """
    ip = request.client.host if request.client else "unknown"

    if user_id:
        # Hash the combination for privacy
        identifier = hashlib.sha256(f"{ip}:{user_id}".encode()).hexdigest()[:16]
        return f"user:{identifier}"
    else:
        # Anonymous users tracked by IP only
        return f"ip:{ip}"


def check_rate_limit(
    key: str, limit: int, window_seconds: int, identifier: str
) -> tuple[bool, Dict[str, Any]]:
    """
    Check if rate limit is exceeded using sliding window

    Returns:
        (is_allowed, metadata)
    """
    now = time.time()
    window_start = now - window_seconds

    # Create Redis key
    redis_key = f"rate_limit:{key}:{identifier}"

    pipe = redis_client.pipeline()

    # Remove old entries outside the window
    pipe.zremrangebyscore(redis_key, 0, window_start)

    # Count requests in current window
    pipe.zcard(redis_key)

    # Add current request
    pipe.zadd(redis_key, {str(now): now})

    # Set expiry
    pipe.expire(redis_key, window_seconds + 60)

    results = pipe.execute()
    request_count = results[1]

    # Check if limit exceeded
    is_allowed = request_count < limit

    metadata = {
        "limit": limit,
        "window": window_seconds,
        "requests": request_count + 1,
        "remaining": max(0, limit - request_count - 1),
        "reset_at": int(now + window_seconds),
    }

    if not is_allowed:
        logger.warning(
            "Rate limit exceeded", key=key, identifier=identifier, **metadata
        )

    return is_allowed, metadata


def parse_rate_limit(rate_string: str) -> tuple[int, int]:
    """
    Parse rate limit string like "100/hour" to (limit, window_seconds)
    """
    limit, period = rate_string.split("/")
    limit = int(limit)

    period_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }

    return limit, period_seconds.get(period, 3600)


class AdvancedRateLimiter:
    """
    Advanced rate limiter with Redis (REQUIRED)
    """

    def __init__(self):
        # Redis is required - no fallbacks
        self.redis = get_redis_client()

    def limit(self, rate_limit_key: str, rate_string: Optional[str] = None):
        """
        Decorator for rate limiting endpoints
        """

        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Get user ID from kwargs if available
                user_id = None
                for arg in args:
                    if isinstance(arg, dict) and "user_id" in arg:
                        user_id = arg["user_id"]
                        break

                identifier = get_identifier(request, user_id)

                # Determine rate limit
                if rate_string:
                    limit_str = rate_string
                else:
                    # Look up from configuration
                    limit_str = RATE_LIMITS.get("routes", {}).get(
                        request.url.path, "100/hour"  # Default
                    )

                limit, window = parse_rate_limit(limit_str)

                # Check rate limit
                is_allowed, metadata = check_rate_limit(
                    rate_limit_key, limit, window, identifier
                )

                if not is_allowed:
                    # Add rate limit headers
                    headers = {
                        "X-RateLimit-Limit": str(metadata["limit"]),
                        "X-RateLimit-Remaining": str(metadata["remaining"]),
                        "X-RateLimit-Reset": str(metadata["reset_at"]),
                        "Retry-After": str(metadata["reset_at"] - int(time.time())),
                    }

                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded",
                        headers=headers,
                    )

                # Add rate limit info to response headers
                response = await func(request, *args, **kwargs)
                if hasattr(response, "headers"):
                    response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
                    response.headers["X-RateLimit-Remaining"] = str(
                        metadata["remaining"]
                    )
                    response.headers["X-RateLimit-Reset"] = str(metadata["reset_at"])

                return response

            return wrapper

        return decorator

    def check_user_quota(self, user_id: str, quota_type: str, operation: str) -> bool:
        """
        Check if user has exceeded their quota for specific operation
        """
        quota_config = RATE_LIMITS.get("user", {}).get(quota_type, {}).get(operation)
        if not quota_config:
            return True

        limit, window = parse_rate_limit(quota_config)
        is_allowed, _ = check_rate_limit(
            f"user_quota:{quota_type}:{operation}", limit, window, f"user:{user_id}"
        )

        return is_allowed

    def get_user_usage(self, user_id: str) -> Dict[str, Any]:
        """
        Get current usage statistics for a user
        """
        usage = {}

        for quota_type, operations in RATE_LIMITS.get("user", {}).items():
            usage[quota_type] = {}

            for operation, limit_str in operations.items():
                limit, window = parse_rate_limit(limit_str)
                key = f"rate_limit:user_quota:{quota_type}:{operation}:user:{user_id}"

                # Get current count
                now = time.time()
                window_start = now - window
                count = redis_client.zcount(key, window_start, now)

                usage[quota_type][operation] = {
                    "used": count,
                    "limit": limit,
                    "remaining": max(0, limit - count),
                    "reset_at": int(now + window),
                }

        return usage


# Global instance
advanced_limiter = AdvancedRateLimiter()

# Convenience decorators for common operations
limit_upload = advanced_limiter.limit("upload", "5/hour")
limit_ai_operation = advanced_limiter.limit("ai_operation", "50/hour")
limit_data_operation = advanced_limiter.limit("data_operation", "200/hour")


# Monitoring functions
def log_rate_limit_metrics():
    """Log rate limiting metrics for monitoring"""
    # Get all rate limit keys
    keys = redis_client.keys("rate_limit:*")

    metrics = {
        "total_tracked_entities": len(keys),
        "active_users": len([k for k in keys if b":user:" in k]),
        "active_ips": len([k for k in keys if b":ip:" in k]),
    }

    logger.info("Rate limit metrics", **metrics)


def cleanup_expired_keys():
    """Clean up expired rate limit keys (run periodically)"""
    # Redis handles expiry automatically, but we can force cleanup
    redis_client.execute_command("MEMORY", "PURGE")
