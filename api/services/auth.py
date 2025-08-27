"""
JWT Authentication Service with JWKS Support
Uses Supabase's JWT Signing Keys (RS256/ES256)
Supports both direct JWT validation and trusted service authentication
"""

import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

import jwt
from fastapi import Header, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


# Custom security scheme that allows OPTIONS requests
class OptionalHTTPBearer(HTTPBearer):
    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        # Allow OPTIONS requests through without authentication
        if request.method == "OPTIONS":
            return None
        return await super().__call__(request)


# Security scheme
security = OptionalHTTPBearer(auto_error=False)


class JWTAuthService:
    """Handle JWT verification using Supabase JWKS"""

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")

        # JWKS URL for Supabase
        self.jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

        # Initialize JWKS client with caching
        self.jwks_client = PyJWKClient(
            self.jwks_url, cache_keys=True, lifespan=300  # Cache for 5 minutes
        )

        # Expected audience
        self.audience = "authenticated"

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token using JWKS

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Get the signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Verify and decode the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                options={"verify_exp": True},
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT validation error: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"Unexpected error during JWT validation: {e}")
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )

    def extract_user_id(self, payload: Dict[str, Any]) -> str:
        """Extract user ID from token payload"""
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        return user_id

    def extract_user_email(self, payload: Dict[str, Any]) -> Optional[str]:
        """Extract user email from token payload"""
        return payload.get("email")

    def extract_user_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user metadata from token payload"""
        return payload.get("user_metadata", {})


# Singleton instance
@lru_cache()
def get_auth_service() -> JWTAuthService:
    """Get singleton auth service instance"""
    return JWTAuthService()


# Dependency to validate service-to-service authentication
def validate_service_secret(x_service_secret: Optional[str] = Header(None)) -> bool:
    """
    Validate that the request is coming from our trusted Next.js server

    Args:
        x_service_secret: Secret token from X-Service-Secret header

    Returns:
        True if the secret is valid
    """
    if not x_service_secret:
        return False

    expected_secret = os.getenv("SERVICE_SECRET")
    if not expected_secret:
        # If no secret is configured, service auth is disabled
        return False

    return x_service_secret == expected_secret


# Dependency for protected routes
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_service_secret: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user

    Supports two authentication methods:
    1. Direct JWT token from browser (legacy, will be phased out)
    2. Service-to-service auth from trusted Next.js server (preferred)

    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        x_service_secret: Service secret from X-Service-Secret header

    Returns:
        User information dictionary
    """
    # Skip authentication for OPTIONS requests
    if request.method == "OPTIONS":
        return {}

    # Check if this is a trusted service request
    is_trusted_service = validate_service_secret(x_service_secret)

    # If it's a trusted service and has credentials, validate the forwarded token
    # If no credentials from trusted service, it means the endpoint is being accessed publicly
    if not credentials and not is_trusted_service:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # If no credentials but is trusted service, allow through
    # (for public endpoints accessed via Next.js proxy)
    if not credentials and is_trusted_service:
        return {"trusted_service": True, "user_id": None, "token": None}

    auth_service = get_auth_service()

    # Verify the token (works for both direct and proxied requests)
    payload = auth_service.verify_token(credentials.credentials)

    # Extract user information
    user_info = {
        "user_id": auth_service.extract_user_id(payload),
        "email": auth_service.extract_user_email(payload),
        "metadata": auth_service.extract_user_metadata(payload),
        "role": payload.get("role", "authenticated"),
        "session_id": payload.get("session_id"),
        "iat": payload.get("iat"),
        "exp": payload.get("exp"),
        "trusted_service": is_trusted_service,  # Flag to indicate if request is from trusted service
        "token": credentials.credentials,  # Include the token for database operations
    }

    return user_info


# Optional dependency - allows unauthenticated access
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication - returns None if no valid token
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
