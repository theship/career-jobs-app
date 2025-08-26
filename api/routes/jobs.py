"""
Job Management API Routes
Endpoints for job ingestion, retrieval, and management
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.services.auth import get_current_user
from api.utils.database import get_supabase_client
from ingestion.orchestrator import JobIngestionOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# Pydantic models for request/response
class JobResponse(BaseModel):
    """Job response model"""

    job_id: str
    company_name: str
    company_domain: str
    title: str
    location: Optional[str] = None
    remote_type: Optional[str] = None
    posted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    department: Optional[str] = None
    employment_type: Optional[str] = None
    seniority: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    job_url: str
    description_text: Optional[str] = None
    requirements_text: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime


class JobSearchRequest(BaseModel):
    """Job search request model"""

    query: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None
    seniority: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[float] = None
    company_name: Optional[str] = None
    limit: int = 20
    offset: int = 0


class IngestionRequest(BaseModel):
    """Job ingestion request model"""

    sources: Optional[List[str]] = None  # Specific sources to ingest from
    limit_per_source: Optional[int] = None
    normalize: bool = True
    store: bool = True


class IngestionResponse(BaseModel):
    """Job ingestion response model"""

    message: str
    sources_processed: int
    total_jobs_ingested: int
    details: dict


# Public endpoints (no auth required for job browsing)
@router.get("", response_model=List[JobResponse])
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    seniority: Optional[str] = Query(None),
    remote_type: Optional[str] = Query(None),
):
    """
    List all jobs with optional filters

    Args:
        limit: Maximum number of jobs to return
        offset: Pagination offset
        seniority: Filter by seniority level
        remote_type: Filter by remote type

    Returns:
        List of jobs
    """
    supabase = get_supabase_client()

    # Build query
    query = supabase.table("job_postings").select("*")

    # Apply filters
    if seniority:
        query = query.eq("seniority", seniority)
    if remote_type:
        query = query.eq("remote_type", remote_type)

    # Apply pagination and ordering
    query = query.order("posted_at", desc=True)
    query = query.range(offset, offset + limit - 1)

    # Execute query
    response = query.execute()

    return response.data


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """
    Get a specific job by ID

    Args:
        job_id: Job ID

    Returns:
        Job details
    """
    supabase = get_supabase_client()

    response = supabase.table("job_postings").select("*").eq("job_id", job_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")

    return response.data[0]


@router.post("/search", response_model=List[JobResponse])
async def search_jobs(request: JobSearchRequest):
    """
    Search jobs with advanced filters

    Args:
        request: Search parameters

    Returns:
        List of matching jobs
    """
    supabase = get_supabase_client()

    # Build query
    query = supabase.table("job_postings").select("*")

    # Apply text search if query provided
    if request.query:
        # Use PostgreSQL text search on title and description
        query = query.or_(
            f"title.ilike.%{request.query}%,"
            f"description_text.ilike.%{request.query}%,"
            f"company_name.ilike.%{request.query}%"
        )

    # Apply filters
    if request.skills:
        # Filter jobs that have any of the requested skills
        for skill in request.skills:
            query = query.contains("skills", [skill])

    if request.location:
        query = query.ilike("location", f"%{request.location}%")

    if request.remote_type:
        query = query.eq("remote_type", request.remote_type)

    if request.seniority:
        query = query.eq("seniority", request.seniority)

    if request.employment_type:
        query = query.eq("employment_type", request.employment_type)

    if request.salary_min:
        query = query.gte("salary_max", request.salary_min)

    if request.company_name:
        query = query.ilike("company_name", f"%{request.company_name}%")

    # Apply pagination and ordering
    query = query.order("posted_at", desc=True)
    query = query.range(request.offset, request.offset + request.limit - 1)

    # Execute query
    response = query.execute()

    return response.data


@router.get("/similar/{job_id}", response_model=List[JobResponse])
async def find_similar_jobs(job_id: str, limit: int = Query(10, ge=1, le=50)):
    """
    Find jobs similar to a given job

    Args:
        job_id: Reference job ID
        limit: Maximum number of similar jobs to return

    Returns:
        List of similar jobs
    """
    supabase = get_supabase_client()

    # Get reference job
    ref_response = (
        supabase.table("job_postings").select("*").eq("job_id", job_id).execute()
    )

    if not ref_response.data:
        raise HTTPException(status_code=404, detail="Job not found")

    ref_job = ref_response.data[0]

    # Find similar jobs based on skills and other attributes
    query = supabase.table("job_postings").select("*")
    query = query.neq("job_id", job_id)

    # Filter by similar attributes
    # Note: skills column doesn't exist in current schema
    # if ref_job.get("skills"):
    #     query = query.overlaps("skills", ref_job["skills"])

    if ref_job.get("seniority"):
        query = query.eq("seniority", ref_job["seniority"])

    if ref_job.get("remote_type"):
        query = query.eq("remote_type", ref_job["remote_type"])

    # Limit results
    query = query.limit(limit)

    response = query.execute()

    return response.data


# Protected endpoints (require authentication for job management)
@router.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(
    request: IngestionRequest, current_user: dict = Depends(get_current_user)
):
    """
    Trigger job ingestion from configured ATS sources

    Args:
        request: Ingestion parameters
        current_user: Authenticated user

    Returns:
        Ingestion results
    """
    # Check if user has admin role (optional)
    # if current_user.get("role") != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create orchestrator
        orchestrator = JobIngestionOrchestrator()

        # Run ingestion
        if request.sources:
            # Ingest from specific sources
            results = {}
            for source in request.sources:
                if source in orchestrator.connectors:
                    jobs = await orchestrator.ingest_from_source(
                        orchestrator.connectors[source],
                        source,
                        limit=request.limit_per_source,
                        normalize=request.normalize,
                        store=request.store,
                    )
                    results[source] = jobs
        else:
            # Ingest from all sources
            results = await orchestrator.ingest_all_sources(
                limit_per_source=request.limit_per_source,
                normalize=request.normalize,
                store=request.store,
            )

        # Calculate totals
        total_jobs = sum(len(jobs) for jobs in results.values())
        sources_processed = len(results)

        return IngestionResponse(
            message=f"Successfully ingested {total_jobs} jobs from {sources_processed} sources",
            sources_processed=sources_processed,
            total_jobs_ingested=total_jobs,
            details={
                source: {
                    "jobs_ingested": len(jobs),
                    "sample_titles": [j.title for j in jobs[:3]],
                }
                for source, jobs in results.items()
            },
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/refresh-embeddings")
async def refresh_job_embeddings(
    batch_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    Refresh embeddings for jobs without them

    Args:
        batch_size: Number of jobs to process
        current_user: Authenticated user

    Returns:
        Number of embeddings updated
    """
    try:
        orchestrator = JobIngestionOrchestrator()
        updated = await orchestrator.update_job_embeddings(batch_size=batch_size)

        return {
            "message": f"Successfully updated {updated} job embeddings",
            "embeddings_updated": updated,
        }

    except Exception as e:
        logger.error(f"Failed to refresh embeddings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh embeddings: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_jobs(current_user: dict = Depends(get_current_user)):
    """
    Clean up expired and duplicate jobs

    Args:
        current_user: Authenticated user

    Returns:
        Cleanup results
    """
    try:
        orchestrator = JobIngestionOrchestrator()

        # Remove duplicates
        duplicates_removed = await orchestrator.deduplicate_jobs()

        # Clean expired jobs
        expired_cleaned = await orchestrator.cleanup_expired_jobs()

        return {
            "message": "Cleanup completed successfully",
            "duplicates_removed": duplicates_removed,
            "expired_jobs_cleaned": expired_cleaned,
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/stats/summary", response_model=dict)
async def get_job_stats():
    """
    Get job statistics summary

    Returns:
        Job statistics
    """
    supabase = get_supabase_client()

    # Get total jobs
    total_response = (
        supabase.table("job_postings").select("job_id", count="exact").execute()
    )
    total_jobs = total_response.count

    # For now, consider all jobs as active since we don't have is_active column
    active_jobs = total_jobs

    # Get unique companies
    companies_response = supabase.table("job_postings").select("company_name").execute()
    unique_companies = len(
        set(
            job["company_name"]
            for job in companies_response.data
            if job.get("company_name")
        )
    )

    # Jobs by source - we don't have source_ats column in current schema
    # TODO: Add source tracking when we have the field
    jobs_by_source = {"unknown": total_jobs if total_jobs else 0}

    # Get jobs by seniority level
    exp_response = supabase.table("job_postings").select("seniority").execute()
    jobs_by_experience = {}
    for job in exp_response.data:
        level = job.get("seniority", "Not Specified")
        jobs_by_experience[level] = jobs_by_experience.get(level, 0) + 1

    # Get jobs by remote type
    remote_response = supabase.table("job_postings").select("remote_type").execute()
    jobs_by_remote = {}
    for job in remote_response.data:
        remote = job.get("remote_type", "Not Specified")
        jobs_by_remote[remote] = jobs_by_remote.get(remote, 0) + 1

    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "unique_companies": unique_companies,
        "jobs_by_source": jobs_by_source,
        "jobs_by_seniority": jobs_by_experience,
        "jobs_by_remote_type": jobs_by_remote,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
