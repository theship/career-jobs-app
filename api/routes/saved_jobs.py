"""
Saved Jobs API Routes
Handles saving/unsaving jobs for users
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.services.auth import get_current_user
from api.utils.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saved-jobs", tags=["saved-jobs"])


class SavedJob(BaseModel):
    """Saved job model"""

    id: str
    user_id: str
    job_id: str
    saved_at: datetime
    notes: Optional[str] = None


class SaveJobRequest(BaseModel):
    """Request model for saving a job"""

    notes: Optional[str] = Field(None, description="Optional notes about the job")


class UpdateNotesRequest(BaseModel):
    """Request model for updating job notes"""

    notes: str = Field(..., description="Updated notes for the saved job")


@router.get("", response_model=List[dict])
async def get_saved_jobs(
    current_user: dict = Depends(get_current_user), include_job_details: bool = True
):
    """
    Get all saved jobs for the current user

    Args:
        current_user: Current authenticated user
        include_job_details: Whether to include full job details

    Returns:
        List of saved jobs
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    try:
        if include_job_details:
            # Join with job_postings to get full job details
            response = (
                supabase.table("saved_jobs")
                .select("*, job_postings(*)")
                .eq("user_id", user_id)
                .order("saved_at", desc=True)
                .execute()
            )
        else:
            # Just get saved job records
            response = (
                supabase.table("saved_jobs")
                .select("*")
                .eq("user_id", user_id)
                .order("saved_at", desc=True)
                .execute()
            )

        return response.data

    except Exception as e:
        logger.exception("Failed to fetch saved jobs")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch saved jobs",
        ) from e


@router.post("/{job_id}", response_model=dict)
async def save_job(
    job_id: str,
    request: SaveJobRequest = SaveJobRequest(),
    current_user: dict = Depends(get_current_user),
):
    """
    Save a job for the current user

    Args:
        job_id: ID of the job to save
        request: Optional notes
        current_user: Current authenticated user

    Returns:
        Created saved job record
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    # First check if job exists
    job_response = (
        supabase.table("job_postings").select("job_id").eq("job_id", job_id).execute()
    )
    if not job_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Check if already saved
    existing = (
        supabase.table("saved_jobs")
        .select("*")
        .eq("user_id", user_id)
        .eq("job_id", job_id)
        .execute()
    )

    if existing.data:
        # Already saved, just return existing
        return existing.data[0]

    try:
        # Create saved job record
        saved_job_data = {"user_id": user_id, "job_id": job_id, "notes": request.notes}

        response = supabase.table("saved_jobs").insert(saved_job_data).execute()

        if response.data:
            logger.info(f"User {user_id} saved job {job_id}")
            return response.data[0]
        else:
            raise Exception("Failed to save job")

    except Exception as e:
        logger.exception("Failed to save job")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save job",
        ) from e


@router.delete("/{job_id}")
async def unsave_job(job_id: str, current_user: dict = Depends(get_current_user)):
    """
    Remove a saved job for the current user

    Args:
        job_id: ID of the job to unsave
        current_user: Current authenticated user

    Returns:
        Success message
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    try:
        # Delete the saved job record
        response = (
            supabase.table("saved_jobs")
            .delete()
            .eq("user_id", user_id)
            .eq("job_id", job_id)
            .execute()
        )

        if response.data:
            logger.info(f"User {user_id} unsaved job {job_id}")
            return {"message": "Job unsaved successfully"}
        else:
            # Job wasn't saved, but that's ok
            return {"message": "Job was not saved"}

    except Exception as e:
        logger.exception("Failed to unsave job")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsave job",
        ) from e


@router.get("/check/{job_id}")
async def check_if_saved(job_id: str, current_user: dict = Depends(get_current_user)):
    """
    Check if a job is saved by the current user

    Args:
        job_id: ID of the job to check
        current_user: Current authenticated user

    Returns:
        Object with is_saved boolean and saved job data if applicable
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    try:
        response = (
            supabase.table("saved_jobs")
            .select("*")
            .eq("user_id", user_id)
            .eq("job_id", job_id)
            .execute()
        )

        if response.data:
            return {"is_saved": True, "saved_job": response.data[0]}
        else:
            return {"is_saved": False, "saved_job": None}

    except Exception as e:
        logger.exception("Failed to check saved status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check saved status",
        ) from e


@router.patch("/{job_id}/notes")
async def update_saved_job_notes(
    job_id: str,
    request: UpdateNotesRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update notes for a saved job

    Args:
        job_id: ID of the saved job
        request: Updated notes
        current_user: Current authenticated user

    Returns:
        Updated saved job record
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    try:
        # Update the notes
        response = (
            supabase.table("saved_jobs")
            .update({"notes": request.notes})
            .eq("user_id", user_id)
            .eq("job_id", job_id)
            .execute()
        )

        if response.data:
            logger.info(f"User {user_id} updated notes for saved job {job_id}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Saved job not found"
            )

    except Exception as e:
        logger.exception("Failed to update saved job notes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notes",
        ) from e


@router.get("/count")
async def get_saved_jobs_count(current_user: dict = Depends(get_current_user)):
    """
    Get count of saved jobs for the current user

    Args:
        current_user: Current authenticated user

    Returns:
        Count of saved jobs
    """
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    try:
        response = (
            supabase.table("saved_jobs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )

        return {"count": response.count or 0}

    except Exception as e:
        logger.exception("Failed to get saved jobs count")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get count",
        ) from e
