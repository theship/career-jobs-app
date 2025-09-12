"""
Admin API Routes
Endpoints for managing target companies and ingestion
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from api.services.auth import get_current_user, require_admin
from api.services.company_manager import CompanyManager
from api.utils.database import get_supabase_service_client
from ingestion.orchestrator import JobIngestionOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# Pydantic models for request/response
class CompanyCreateRequest(BaseModel):
    """Request model for creating a company"""

    ats_system: str  # lever, greenhouse, ashby
    company_id: str
    display_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    priority: int = 2  # 1=high, 2=medium, 3=low
    check_frequency_days: int = 1
    metadata: Optional[Dict] = None


class CompanyUpdateRequest(BaseModel):
    """Request model for updating a company"""

    display_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    priority: Optional[int] = None
    check_frequency_days: Optional[int] = None
    active: Optional[bool] = None
    metadata: Optional[Dict] = None


class CompanyResponse(BaseModel):
    """Response model for a company"""

    id: str
    ats_system: str
    company_id: str
    display_name: str
    industry: Optional[str]
    company_size: Optional[str]
    priority: int
    check_frequency_days: int
    active: bool
    last_successful_fetch: Optional[datetime]
    last_fetch_attempt: Optional[datetime]
    consecutive_failures: int
    error_details: Optional[str]
    metadata: Optional[Dict]
    created_at: datetime
    updated_at: datetime


class IngestionStatsResponse(BaseModel):
    """Response model for ingestion statistics"""

    total_runs: int
    successful_runs: int
    failed_runs: int
    total_jobs_fetched: int
    total_jobs_created: int
    total_jobs_updated: int
    total_embeddings: int
    avg_duration_ms: float
    success_rate: float


class IngestionRunRequest(BaseModel):
    """Request model for triggering ingestion"""

    ats_system: Optional[str] = None  # Filter by ATS
    company_ids: Optional[List[str]] = None  # Specific companies
    limit_per_company: Optional[int] = None
    parallel: bool = True


@router.get("/companies", response_model=List[CompanyResponse])
async def list_companies(
    active_only: bool = Query(False, description="Only show active companies"),
    ats_system: Optional[str] = Query(None, description="Filter by ATS system"),
    current_user: dict = Depends(require_admin),
):
    """
    List all target companies with their status

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        companies = await company_manager.get_all_companies(
            active_only=active_only, ats_system=ats_system
        )

        return companies

    except Exception as e:
        logger.error(f"Failed to list companies: {e}")
        raise HTTPException(status_code=500, detail="Failed to list companies")


@router.post("/companies", response_model=CompanyResponse)
async def create_company(
    request: CompanyCreateRequest,
    current_user: dict = Depends(require_admin),
):
    """
    Add a new target company

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Check if company already exists
        existing = await company_manager.get_all_companies(
            active_only=False, ats_system=request.ats_system
        )

        for company in existing:
            if company["company_id"] == request.company_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Company {request.company_id} already exists for {request.ats_system}",
                )

        # Create new company
        company = await company_manager.add_company(
            ats_system=request.ats_system,
            company_id=request.company_id,
            display_name=request.display_name,
            industry=request.industry,
            priority=request.priority,
            check_frequency_days=request.check_frequency_days,
            metadata=request.metadata,
        )

        if not company:
            raise HTTPException(status_code=500, detail="Failed to create company")

        return company

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create company: {e}")
        raise HTTPException(status_code=500, detail="Failed to create company")


@router.patch("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    request: CompanyUpdateRequest,
    current_user: dict = Depends(require_admin),
):
    """
    Update a target company's settings

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Build update dict from non-None values
        updates = {k: v for k, v in request.dict().items() if v is not None}

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        company = await company_manager.update_company(company_id, **updates)

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        return company

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update company")


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    current_user: dict = Depends(require_admin),
):
    """
    Delete a target company

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        success = await company_manager.delete_company(company_id)

        if not success:
            raise HTTPException(status_code=404, detail="Company not found")

        return {"message": "Company deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete company")


@router.get("/companies/{company_id}/stats", response_model=IngestionStatsResponse)
async def get_company_stats(
    company_id: str,
    days: int = Query(30, description="Number of days to look back"),
    current_user: dict = Depends(require_admin),
):
    """
    Get ingestion statistics for a specific company

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        stats = await company_manager.get_company_stats(
            company_uuid=company_id, days=days
        )

        return stats

    except Exception as e:
        logger.error(f"Failed to get stats for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get company stats")


@router.get("/ingestion/stats", response_model=IngestionStatsResponse)
async def get_overall_stats(
    days: int = Query(30, description="Number of days to look back"),
    current_user: dict = Depends(require_admin),
):
    """
    Get overall ingestion statistics across all companies

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        stats = await company_manager.get_company_stats(days=days)

        return stats

    except Exception as e:
        logger.error(f"Failed to get overall stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


@router.post("/ingestion/run")
async def trigger_ingestion(
    request: IngestionRunRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_admin),
):
    """
    Manually trigger job ingestion

    Requires admin privileges
    """
    try:
        # Create orchestrator
        orchestrator = JobIngestionOrchestrator()

        # If specific companies requested, filter them
        if request.company_ids:
            # Get specific companies from database
            supabase = get_supabase_service_client()
            company_manager = CompanyManager(supabase)

            # This would need to be implemented to filter by IDs
            # For now, we'll run all companies
            logger.info(
                f"Running ingestion for specific companies: {request.company_ids}"
            )

        # Add to background tasks
        background_tasks.add_task(
            run_ingestion_background,
            orchestrator,
            request.limit_per_company,
            request.parallel,
        )

        return {
            "message": "Ingestion started in background",
            "parallel": request.parallel,
            "limit_per_company": request.limit_per_company,
        }

    except Exception as e:
        logger.error(f"Failed to trigger ingestion: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger ingestion")


async def run_ingestion_background(
    orchestrator: JobIngestionOrchestrator,
    limit_per_company: Optional[int],
    parallel: bool,
):
    """
    Background task to run ingestion
    """
    try:
        logger.info(f"Starting background ingestion (parallel={parallel})")

        results = await orchestrator.ingest_all_sources(
            limit_per_source=limit_per_company,
            normalize=True,
            store=True,
            parallel=parallel,
        )

        total_jobs = sum(len(jobs) for jobs in results.values())
        logger.info(f"Background ingestion complete: {total_jobs} total jobs")

        # Run cleanup
        duplicates_removed = await orchestrator.deduplicate_jobs()
        logger.info(f"Removed {duplicates_removed} duplicate jobs")

    except Exception as e:
        logger.error(f"Background ingestion failed: {e}")


@router.post("/companies/reset-failures")
async def reset_company_failures(
    company_ids: Optional[List[str]] = None,
    current_user: dict = Depends(require_admin),
):
    """
    Reset consecutive failure counts for companies

    Requires admin privileges
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Get companies to reset
        if company_ids:
            companies = [{"id": cid} for cid in company_ids]
        else:
            companies = await company_manager.get_all_companies(active_only=False)

        # Reset each company
        reset_count = 0
        for company in companies:
            await company_manager.update_company(
                company["id"], consecutive_failures=0, error_details=None, active=True
            )
            reset_count += 1

        return {"message": f"Reset {reset_count} companies", "count": reset_count}

    except Exception as e:
        logger.error(f"Failed to reset company failures: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset failures")
