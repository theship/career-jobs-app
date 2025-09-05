"""
New endpoints for pitch history management using database storage
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from api.services.auth import get_current_user
from api.utils.database import get_supabase_service_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pitch", tags=["pitch"])


@router.get("/history/{pitch_id}")
async def get_pitch_history(
    pitch_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retrieve a previously generated pitch from database

    Args:
        pitch_id: ID of the pitch to retrieve
        current_user: Authenticated user

    Returns:
        Pitch data
    """
    supabase = get_supabase_service_client()

    # Get pitch from database (RLS ensures user can only see their own)
    response = (
        supabase.table("pitch_history")
        .select("*")
        .eq("pitch_id", pitch_id)
        .eq("user_id", current_user.get("user_id"))
        .limit(1)
        .execute()
    )

    if not response or not response.data:
        raise HTTPException(status_code=404, detail="Pitch not found")

    return response.data[0]


@router.get("/history")
async def list_pitch_history(
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    List recent pitch history for the authenticated user

    Args:
        current_user: Authenticated user
        limit: Maximum number of pitches to return
        offset: Number of pitches to skip

    Returns:
        List of recent pitches
    """
    supabase = get_supabase_service_client()

    # Get user's pitches from database (RLS ensures user isolation)
    response = (
        supabase.table("pitch_history")
        .select("*")
        .eq("user_id", current_user.get("user_id"))
        .order("generated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    if not response or not response.data:
        return []

    return response.data


@router.delete("/history/{pitch_id}")
async def delete_pitch(
    pitch_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a pitch from history

    Args:
        pitch_id: ID of the pitch to delete
        current_user: Authenticated user

    Returns:
        Success message
    """
    supabase = get_supabase_service_client()

    # Delete pitch (RLS ensures user can only delete their own)
    response = (
        supabase.table("pitch_history")
        .delete()
        .eq("pitch_id", pitch_id)
        .eq("user_id", current_user.get("user_id"))
        .execute()
    )

    if not response or not response.data:
        raise HTTPException(status_code=404, detail="Pitch not found")

    return {"message": "Pitch deleted successfully"}


@router.get("/history/stats")
async def get_pitch_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get statistics about user's pitch history

    Args:
        current_user: Authenticated user

    Returns:
        Statistics about pitches
    """
    supabase = get_supabase_service_client()

    # Get user's pitch count
    response = (
        supabase.table("pitch_history")
        .select("pitch_id", count="exact")
        .eq("user_id", current_user.get("user_id"))
        .execute()
    )

    total_pitches = response.count if response else 0

    # Get recent pitches for average quality score
    recent_response = (
        supabase.table("pitch_history")
        .select("quality_scores")
        .eq("user_id", current_user.get("user_id"))
        .order("generated_at", desc=True)
        .limit(20)
        .execute()
    )

    avg_quality = 0.0
    if recent_response and recent_response.data:
        quality_scores = [
            p.get("quality_scores", {}).get("overall", 0.0)
            for p in recent_response.data
            if p.get("quality_scores")
        ]
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)

    return {
        "total_pitches": total_pitches,
        "average_quality_score": avg_quality,
        "recent_count": len(recent_response.data) if recent_response else 0,
    }
