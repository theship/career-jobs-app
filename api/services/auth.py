"""
Service-to-Service Authentication
Requires all requests to come from trusted Next.js server
Next.js handles user authentication and forwards user info via headers
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)


def verify_service_secret(x_service_secret: Optional[str] = Header(None)) -> bool:
    """
    Verify that the request is coming from our trusted Next.js server
    
    Args:
        x_service_secret: Secret token from X-Service-Secret header
    
    Returns:
        True if the secret is valid
    
    Raises:
        HTTPException: If the secret is invalid or missing
    """
    if not x_service_secret:
        raise HTTPException(
            status_code=403,
            detail="Service authentication required. Direct API access is not allowed."
        )
    
    expected_secret = os.getenv("SERVICE_SECRET")
    if not expected_secret:
        logger.error("SERVICE_SECRET environment variable is not configured")
        raise HTTPException(
            status_code=500,
            detail="Service authentication not configured"
        )
    
    if x_service_secret != expected_secret:
        logger.warning(f"Invalid service secret attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid service authentication"
        )
    
    return True


# Dependency for protected routes
def get_current_user(
    request: Request,
    x_service_secret: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user
    
    All requests MUST come through the Next.js proxy with:
    1. Valid service secret (proves it's from our Next.js server)
    2. User information headers (pre-validated by Next.js)
    
    Args:
        request: FastAPI request object
        x_service_secret: Service secret from X-Service-Secret header
        x_user_id: User ID forwarded by Next.js
        x_user_email: User email forwarded by Next.js
        x_user_token: JWT token forwarded by Next.js (for database operations)
    
    Returns:
        User information dictionary
    
    Raises:
        HTTPException: If service secret is invalid or user info is missing
    """
    # Skip authentication for OPTIONS requests
    if request.method == "OPTIONS":
        return {}
    
    # Verify this is from our trusted Next.js server
    verify_service_secret(x_service_secret)
    
    # Check if user information was provided
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="User authentication required"
        )
    
    # Return user information trusted from Next.js
    user_info = {
        "user_id": x_user_id,
        "email": x_user_email,
        "token": x_user_token,  # Include token for database operations if needed
        "trusted_service": True,
    }
    
    logger.debug(f"Authenticated request for user {x_user_id}")
    
    return user_info


# Optional dependency - allows unauthenticated access
def get_current_user_optional(
    request: Request,
    x_service_secret: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_user_email: Optional[str] = Header(None),
    x_user_token: Optional[str] = Header(None),
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication - returns None if no valid user
    Still requires service secret to ensure request is from Next.js
    """
    # Skip authentication for OPTIONS requests
    if request.method == "OPTIONS":
        return None
    
    # Verify this is from our trusted Next.js server
    try:
        verify_service_secret(x_service_secret)
    except HTTPException:
        return None
    
    # If no user info provided, return None (anonymous access)
    if not x_user_id:
        return None
    
    return {
        "user_id": x_user_id,
        "email": x_user_email,
        "token": x_user_token,
        "trusted_service": True,
    }
