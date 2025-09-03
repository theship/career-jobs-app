"""
HMAC-based request signing and replay attack prevention
"""

import hashlib
import hmac
import json
import time
from typing import Dict, Optional, Tuple

import redis
import structlog
from fastapi import HTTPException, Request, status

logger = structlog.get_logger()

# Redis connection for replay prevention
# In production, use Redis Sentinel or Cluster for HA
try:
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except (redis.ConnectionError, redis.TimeoutError):
    logger.warning("Redis not available - replay prevention disabled")
    REDIS_AVAILABLE = False
    redis_client = None

# Configuration
HMAC_SECRET = None  # Set from environment
REQUEST_TIMEOUT_SECONDS = 300  # 5 minutes
NONCE_EXPIRY_SECONDS = 600  # 10 minutes


def initialize_hmac(secret: str):
    """Initialize HMAC secret from environment"""
    global HMAC_SECRET
    HMAC_SECRET = secret.encode("utf-8")


def generate_signature(
    method: str, path: str, timestamp: str, nonce: str, body: Optional[str] = None
) -> str:
    """
    Generate HMAC-SHA256 signature for request

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        timestamp: Unix timestamp as string
        nonce: Unique request identifier
        body: Request body as string (for POST/PUT)

    Returns:
        Hex-encoded HMAC signature
    """
    if not HMAC_SECRET:
        raise ValueError("HMAC secret not initialized")

    # Create canonical request string
    parts = [method.upper(), path, timestamp, nonce]

    # Add body hash for requests with body
    if body:
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        parts.append(body_hash)

    canonical_string = "\n".join(parts)

    # Generate HMAC
    signature = hmac.new(
        HMAC_SECRET, canonical_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return signature


def verify_request_signature(
    request: Request,
    signature: str,
    timestamp: str,
    nonce: str,
    body: Optional[bytes] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Verify HMAC signature and check for replay attacks

    Args:
        request: FastAPI request object
        signature: Provided signature
        timestamp: Request timestamp
        nonce: Request nonce
        body: Raw request body

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check timestamp freshness
    try:
        request_time = float(timestamp)
        current_time = time.time()

        if abs(current_time - request_time) > REQUEST_TIMEOUT_SECONDS:
            logger.warning(
                "Request timestamp outside acceptable window",
                timestamp=timestamp,
                current_time=current_time,
                difference=abs(current_time - request_time),
            )
            return False, "Request timestamp expired"
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    # Check for replay attack using nonce
    if REDIS_AVAILABLE and redis_client:
        nonce_key = f"nonce:{nonce}"

        # Check if nonce was already used
        if redis_client.exists(nonce_key):
            logger.warning(
                "Replay attack detected - nonce reuse",
                nonce=nonce,
                path=request.url.path,
                ip=request.client.host if request.client else "unknown",
            )
            return False, "Nonce already used (replay attack)"

        # Store nonce with expiry
        redis_client.setex(nonce_key, NONCE_EXPIRY_SECONDS, timestamp)

    # Generate expected signature
    body_str = body.decode("utf-8") if body else None
    expected_signature = generate_signature(
        method=request.method,
        path=request.url.path,
        timestamp=timestamp,
        nonce=nonce,
        body=body_str,
    )

    # Constant-time comparison
    is_valid = hmac.compare_digest(signature, expected_signature)

    if not is_valid:
        logger.warning(
            "Invalid HMAC signature",
            path=request.url.path,
            method=request.method,
            provided_signature=signature[:10] + "...",
            ip=request.client.host if request.client else "unknown",
        )
        return False, "Invalid signature"

    return True, None


def require_hmac_validation(
    request: Request,
    x_signature: Optional[str] = None,
    x_timestamp: Optional[str] = None,
    x_nonce: Optional[str] = None,
    body: Optional[bytes] = None,
):
    """
    FastAPI dependency to require HMAC validation

    Raises:
        HTTPException: If validation fails
    """
    if not all([x_signature, x_timestamp, x_nonce]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required HMAC headers",
        )

    is_valid, error_message = verify_request_signature(
        request=request,
        signature=x_signature,
        timestamp=x_timestamp,
        nonce=x_nonce,
        body=body,
    )

    if not is_valid:
        # Log security event
        logger.error(
            "HMAC validation failed",
            event_type="hmac_failure",
            category="security",
            severity="HIGH",
            error=error_message,
            path=request.url.path,
            ip=request.client.host if request.client else "unknown",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_message or "Invalid request signature",
        )


def cleanup_expired_nonces():
    """
    Cleanup expired nonces from Redis (run periodically)
    This is handled automatically by Redis TTL, but can be called manually
    """
    if not REDIS_AVAILABLE or not redis_client:
        return

    # Redis handles expiry automatically with SETEX
    # This function is here for manual cleanup if needed
    pass


# Client-side helper for generating signed requests
class HMACClient:
    """Helper class for generating signed requests"""

    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8")

    def sign_request(
        self, method: str, url: str, body: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Generate headers for signed request

        Args:
            method: HTTP method
            url: Full URL or path
            body: Request body as dict

        Returns:
            Dictionary of headers to add to request
        """
        import uuid
        from urllib.parse import urlparse

        # Parse URL to get path
        parsed = urlparse(url)
        path = parsed.path
        if parsed.query:
            path += f"?{parsed.query}"

        # Generate timestamp and nonce
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())

        # Convert body to JSON string if provided
        body_str = json.dumps(body, separators=(",", ":")) if body else None

        # Generate signature
        global HMAC_SECRET
        temp_secret = HMAC_SECRET
        HMAC_SECRET = self.secret

        signature = generate_signature(
            method=method, path=path, timestamp=timestamp, nonce=nonce, body=body_str
        )

        HMAC_SECRET = temp_secret

        return {"X-Signature": signature, "X-Timestamp": timestamp, "X-Nonce": nonce}


# Monitoring and alerting
def log_security_metrics():
    """Log security metrics for monitoring"""
    if not REDIS_AVAILABLE or not redis_client:
        return

    # Count nonces (active requests)
    nonce_count = len(redis_client.keys("nonce:*"))

    logger.info(
        "HMAC security metrics",
        active_nonces=nonce_count,
        redis_available=REDIS_AVAILABLE,
    )
