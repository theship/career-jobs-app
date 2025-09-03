"""
Authentication Routes
Handles user authentication and profile endpoints
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from api.services.auth import get_current_user

router = APIRouter()


@router.get("/me")
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current authenticated user profile

    Returns:
        User profile information
    """
    return {
        "user_id": current_user["user_id"],
        "email": current_user.get("email"),
        "role": current_user.get("role", "authenticated"),
        "metadata": current_user.get("metadata", {}),
    }


@router.get("/verify")
async def verify_token(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Verify JWT token is valid

    Returns:
        Token validation status
    """
    return {
        "valid": True,
        "user_id": current_user["user_id"],
        "expires_at": current_user.get("exp"),
    }


@router.get("/session")
async def get_session_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current session information

    Returns:
        Session details
    """
    return {
        "session_id": current_user.get("session_id"),
        "user_id": current_user["user_id"],
        "issued_at": current_user.get("iat"),
        "expires_at": current_user.get("exp"),
        "role": current_user.get("role", "authenticated"),
    }
