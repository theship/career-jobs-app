"""
JWT Authentication Service with JWKS Support
Uses Supabase's JWT Signing Keys (RS256/ES256)
"""

import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


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


# Dependency for protected routes
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User information dictionary
    """
    auth_service = get_auth_service()

    # Verify the token
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
