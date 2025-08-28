"""
API routes for job scoring and ranking with comprehensive logging
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.activity_logger import activity_logger
from api.services.auth import get_current_user
from api.services.experiments import ExperimentConfig, ExperimentTracker
from api.services.score_explainer import ScoreExplainer
from api.utils.database import get_supabase_client
from scoring_engine.ranker import JobRanker, JobScore, ScoringWeights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scores", tags=["scoring"])


# Request/Response Models
class ScoringRequest(BaseModel):
    """Request model for scoring jobs"""

    resume_id: str = Field(..., description="Resume ID to score against")
    job_ids: Optional[List[str]] = Field(
        None, description="Specific job IDs to score (optional)"
    )
    limit: int = Field(100, ge=1, le=500, description="Maximum number of results")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum score threshold")
    experiment_config: Optional[Dict[str, Any]] = Field(
        None, description="Experiment configuration for W&B tracking"
    )


class ScoringWeightsRequest(BaseModel):
    """Custom scoring weights"""

    cosine_similarity: float = Field(0.5, ge=0.0, le=1.0)
    skills_overlap: float = Field(0.2, ge=0.0, le=1.0)
    seniority_fit: float = Field(0.1, ge=0.0, le=1.0)
    geographic_score: float = Field(0.1, ge=0.0, le=1.0)
    recency_bonus: float = Field(0.1, ge=0.0, le=1.0)


class ScoreResponse(BaseModel):
    """Response model for a single job score"""

    job_id: str
    title: str
    company_name: str
    total_score: float
    rank: int
    percentile: float
    cosine_sim: float
    skill_overlap: float
    seniority_fit: float
    geodist_km: float
    recency_bonus: float
    match_level: str


class ScoreBreakdownResponse(BaseModel):
    """Detailed score breakdown response"""

    job_id: str
    title: str
    company: str
    overall: Dict[str, Any]
    factor_breakdown: List[Dict[str, Any]]
    strengths: Dict[str, str]
    weaknesses: Dict[str, str]
    improvement_suggestions: List[str]
    skills_breakdown: Optional[Dict[str, Any]] = None
    location_insights: Optional[Dict[str, str]] = None


class BatchScoringResponse(BaseModel):
    """Response for batch scoring request"""

    resume_id: str
    total_jobs_scored: int
    processing_time_ms: float
    results: List[ScoreResponse]
    experiment_run_id: Optional[str] = None


# Helper functions
async def get_resume_data(resume_id: str, supabase):
    """Fetch resume data and embedding from database"""
    try:
        # Get resume data
        response = (
            supabase.table("resumes").select("*").eq("resume_id", resume_id).execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Resume not found")

        resume = response.data[0]

        # Get resume embedding from resumes table
        embedding_response = (
            supabase.table("resumes")
            .select("embedding")
            .eq("resume_id", resume_id)
            .execute()
        )

        if not embedding_response.data:
            raise HTTPException(status_code=404, detail="Resume embedding not found")

        resume["embedding"] = np.array(embedding_response.data[0]["embedding"])

        return resume

    except Exception as e:
        logger.error(f"Error fetching resume data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_jobs_data(job_ids: Optional[List[str]], limit: int, supabase):
    """Fetch jobs data and embeddings from database"""
    try:
        # Build query
        query = supabase.table("job_postings").select("*")

        if job_ids:
            query = query.in_("job_id", job_ids)
        else:
            # Get recent jobs
            query = query.order("posted_at", desc=True)

        query = query.limit(limit)
        response = query.execute()

        if not response.data:
            return [], []

        jobs = response.data
        job_ids = [j["job_id"] for j in jobs]

        # Job embeddings are in the job_postings table itself
        # Extract embeddings from the jobs we already fetched
        embeddings = []
        filtered_jobs = []
        for job in jobs:
            if job.get("embedding"):
                filtered_jobs.append(job)
                embeddings.append(np.array(job["embedding"]))

        if embeddings:
            embeddings = np.array(embeddings)

        return filtered_jobs, embeddings

    except Exception as e:
        logger.error(f"Error fetching jobs data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API Endpoints
@router.get("", response_model=List[ScoreResponse])  # Remove trailing slash
async def get_scores(
    resume_id: str = Query(..., description="Resume ID to get scores for"),
    limit: int = Query(50, description="Maximum number of scores to return"),
    current_user: Dict = Depends(get_current_user),
):
    """
    Get stored scores for a resume

    Returns previously calculated scores from the database.
    If no scores exist, returns empty list (client should call /run to calculate).
    """
    # Use authenticated client if we have a valid token, otherwise use service client
    if current_user.get("token") and current_user.get("token") != "test":
        from api.utils.database import get_authenticated_supabase_client
        try:
            supabase = get_authenticated_supabase_client(current_user["token"])
            logger.info(f"Using authenticated client for user {current_user['user_id']}")
        except Exception as e:
            logger.warning(f"Failed to use authenticated client: {e}, falling back to service client")
            from api.utils.database import get_supabase_service_client
            supabase = get_supabase_service_client()
    else:
        # Fallback to service client for trusted services or test tokens
        from api.utils.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        logger.info(f"Using service client for user {current_user['user_id']} (trusted service or test)")

    try:
        # Get scores from database
        response = (
            supabase.table("scores")
            .select("*, job_postings!inner(title, company_name, location, posted_at)")
            .eq("resume_id", resume_id)
            .eq("user_id", current_user["user_id"])
            .order("total_score", desc=True)
            .limit(limit)
            .execute()
        )

        # Return empty array if no scores found (not an error condition)
        if not response.data:
            logger.info(f"No scores found for resume {resume_id}, user {current_user['user_id']}")
            return []

        # Convert to response format
        results = []
        for idx, score in enumerate(response.data, 1):
            job = score.get("job_postings", {})
            results.append(
                ScoreResponse(
                    job_id=score["job_id"],
                    title=job.get("title", "Unknown"),
                    company_name=job.get("company_name", "Unknown"),
                    total_score=float(score["total_score"]),
                    rank=idx,
                    percentile=100 - (idx / len(response.data) * 100),
                    cosine_sim=float(score["cosine_sim"]),
                    skill_overlap=float(score["skill_overlap"]),
                    seniority_fit=float(score["seniority_fit"]),
                    geodist_km=(
                        float(score["geodist_km"]) if score["geodist_km"] else None
                    ),
                    recency_bonus=float(score["recency_bonus"]),
                    match_level=(
                        "high"
                        if float(score["total_score"]) > 0.7
                        else ("medium" if float(score["total_score"]) > 0.5 else "low")
                    ),
                )
            )

        return results

    except Exception as e:
        logger.error(f"Error fetching scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=BatchScoringResponse)
async def run_scoring(
    request: ScoringRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
):
    """
    Run scoring for a resume against jobs with detailed progress tracking

    Requires authentication.
    """
    start_time = time.time()
    user_id = current_user["user_id"]
    # Use authenticated client if we have a valid token, otherwise use service client
    if current_user.get("token") and current_user.get("token") != "test":
        from api.utils.database import get_authenticated_supabase_client
        try:
            supabase = get_authenticated_supabase_client(current_user["token"])
            logger.info(f"Using authenticated client for user {current_user['user_id']}")
        except Exception as e:
            logger.warning(f"Failed to use authenticated client: {e}, falling back to service client")
            from api.utils.database import get_supabase_service_client
            supabase = get_supabase_service_client()
    else:
        # Fallback to service client for trusted services or test tokens
        from api.utils.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        logger.info(f"Using service client for user {current_user['user_id']} (trusted service or test)")
    
    # Start activity logging
    log_id = await activity_logger.log_action_start(
        user_id=user_id,
        action_type="scoring_run",
        metadata={
            "resume_id": request.resume_id,
            "requested_limit": request.limit,
            "min_score": request.min_score,
            "has_experiment_config": request.experiment_config is not None,
        }
    )
    
    logger.info(f"Starting scoring run for resume {request.resume_id}, user {user_id}")

    # Initialize experiment tracker if config provided
    experiment_tracker = None
    if request.experiment_config:
        experiment_tracker = ExperimentTracker()
        config = ExperimentConfig(
            name=request.experiment_config.get("name", "scoring_run"),
            description=request.experiment_config.get("description"),
            tags=request.experiment_config.get("tags", ["api_scoring"]),
        )

        # Set custom weights if provided
        if "weights" in request.experiment_config:
            weights_dict = request.experiment_config["weights"]
            config.weights = ScoringWeights(**weights_dict)

        run = experiment_tracker.start_experiment(config, request.resume_id)
        experiment_run_id = run.id if run else None
    else:
        experiment_run_id = None

    try:
        # Fetch resume data
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={"stage": "fetching_resume"}
        )
        resume_fetch_start = time.time()
        resume_data = await get_resume_data(request.resume_id, supabase)
        resume_embedding = resume_data.pop("embedding")
        resume_fetch_time = int((time.time() - resume_fetch_start) * 1000)
        
        logger.info(f"Resume data fetched in {resume_fetch_time}ms")
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "resume_fetched",
                "resume_fetch_time_ms": resume_fetch_time,
            }
        )

        # Fetch jobs data
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={"stage": "fetching_jobs", "message": "Loading job postings..."}
        )
        jobs_fetch_start = time.time()
        jobs_data, job_embeddings = await get_jobs_data(
            request.job_ids,
            request.limit * 2,  # Fetch more to account for filtering
            supabase,
        )
        jobs_fetch_time = int((time.time() - jobs_fetch_start) * 1000)
        
        logger.info(f"Fetched {len(jobs_data)} jobs in {jobs_fetch_time}ms")
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "jobs_fetched",
                "jobs_count": len(jobs_data),
                "jobs_fetch_time_ms": jobs_fetch_time,
            }
        )

        if not jobs_data:
            await activity_logger.log_action_complete(
                log_id=log_id,
                success=True,
                result_data={
                    "total_jobs_scored": 0,
                    "message": "No jobs to score"
                }
            )
            return BatchScoringResponse(
                resume_id=request.resume_id,
                total_jobs_scored=0,
                processing_time_ms=0,
                results=[],
                experiment_run_id=experiment_run_id,
            )

        # Initialize ranker with custom weights if provided
        weights = ScoringWeights()
        if request.experiment_config and "weights" in request.experiment_config:
            weights_dict = request.experiment_config["weights"]
            weights = ScoringWeights(**weights_dict)

        ranker = JobRanker(weights=weights)

        # Run ranking with progress updates
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "calculating_scores",
                "message": f"Calculating similarities for {len(jobs_data)} jobs..."
            }
        )
        
        scoring_start = time.time()
        scores = ranker.rank_jobs(
            jobs_data=jobs_data,
            resume_data=resume_data,
            resume_embedding=resume_embedding,
            job_embeddings=job_embeddings,
            top_k=request.limit,
            min_score_threshold=request.min_score,
        )
        scoring_time = int((time.time() - scoring_start) * 1000)
        
        # Log scoring statistics
        if scores:
            top_score = scores[0].total_score
            avg_score = sum(s.total_score for s in scores) / len(scores)
            above_threshold = len([s for s in scores if s.total_score >= request.min_score])
        else:
            top_score = avg_score = above_threshold = 0
        
        logger.info(
            f"Scoring completed: {len(scores)} matches in {scoring_time}ms, "
            f"top_score={top_score:.3f}, avg_score={avg_score:.3f}"
        )
        
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "scores_calculated",
                "scoring_time_ms": scoring_time,
                "matches_found": len(scores),
                "top_score": round(top_score, 3),
                "avg_score": round(avg_score, 3),
                "above_threshold": above_threshold,
            }
        )

        # Convert to response format
        explainer = ScoreExplainer(weights=weights)
        results = []
        for score in scores:
            summary = explainer.generate_summary(score)
            results.append(
                ScoreResponse(
                    job_id=score.job_id,
                    title=score.title,
                    company_name=score.company_name,
                    total_score=score.total_score,
                    rank=score.rank,
                    percentile=score.percentile,
                    cosine_sim=score.cosine_sim,
                    skill_overlap=score.skill_overlap,
                    seniority_fit=score.seniority_fit,
                    geodist_km=score.geodist_km,
                    recency_bonus=score.recency_bonus,
                    match_level=summary["overall"]["match_level"],
                )
            )

        processing_time_ms = (time.time() - start_time) * 1000

        # Log to W&B if tracking
        if experiment_tracker:
            background_tasks.add_task(
                experiment_tracker.log_scoring_run,
                scores,
                request.resume_id,
                processing_time_ms,
            )

        # Store scoring results in database
        background_tasks.add_task(
            store_scoring_results,
            request.resume_id,
            scores,
            current_user["user_id"],
            supabase,
        )
        
        # Log successful completion
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=True,
            result_data={
                "resume_id": request.resume_id,
                "total_jobs_scored": len(results),
                "processing_time_ms": processing_time_ms,
                "top_score": round(scores[0].total_score, 3) if scores else 0,
                "avg_score": round(sum(r.total_score for r in results) / len(results), 3) if results else 0,
                "jobs_evaluated": len(jobs_data),
                "matches_returned": len(results),
            }
        )
        
        logger.info(
            f"Scoring run completed successfully: {len(results)} matches returned "
            f"in {processing_time_ms}ms for user {user_id}"
        )

        return BatchScoringResponse(
            resume_id=request.resume_id,
            total_jobs_scored=len(results),
            processing_time_ms=processing_time_ms,
            results=results,
            experiment_run_id=experiment_run_id,
        )
        
    except Exception as e:
        logger.error(f"Scoring run failed: {e}")
        
        # Log failure
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=False,
            error_details=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Scoring failed: {str(e)}"
        )

    finally:
        if experiment_tracker:
            background_tasks.add_task(experiment_tracker.finish_experiment)


@router.get("/breakdown/{job_id}", response_model=ScoreBreakdownResponse)
async def get_score_breakdown(
    job_id: str,
    resume_id: str = Query(..., description="Resume ID"),
    current_user: Dict = Depends(get_current_user),
):
    """
    Get detailed score breakdown for a specific job-resume pair

    Requires authentication.
    """
    # Use authenticated client if we have a valid token, otherwise use service client
    if current_user.get("token") and current_user.get("token") != "test":
        from api.utils.database import get_authenticated_supabase_client
        try:
            supabase = get_authenticated_supabase_client(current_user["token"])
            logger.info(f"Using authenticated client for user {current_user['user_id']}")
        except Exception as e:
            logger.warning(f"Failed to use authenticated client: {e}, falling back to service client")
            from api.utils.database import get_supabase_service_client
            supabase = get_supabase_service_client()
    else:
        # Fallback to service client for trusted services or test tokens
        from api.utils.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        logger.info(f"Using service client for user {current_user['user_id']} (trusted service or test)")

    # Fetch stored score or recalculate
    score_response = (
        supabase.table("scores")
        .select("*")
        .eq("resume_id", resume_id)
        .eq("job_id", job_id)
        .eq("user_id", current_user["user_id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if score_response.data:
        # Use cached score
        cached = score_response.data[0]
        return ScoreBreakdownResponse(**cached["breakdown"])

    # Recalculate score
    resume_data = await get_resume_data(resume_id, supabase)
    resume_embedding = resume_data.pop("embedding")

    jobs_data, job_embeddings = await get_jobs_data([job_id], 1, supabase)

    if not jobs_data:
        raise HTTPException(status_code=404, detail="Job not found")

    ranker = JobRanker()
    job_score = ranker.score_single_job(
        jobs_data[0], resume_data, resume_embedding, job_embeddings[0]
    )

    explainer = ScoreExplainer()
    breakdown = explainer.generate_summary(job_score)

    # Add skills breakdown if available
    if job_score.skills_details:
        breakdown["skills_breakdown"] = {
            "exact_matches": job_score.skills_details.exact_matches,
            "fuzzy_matches": [
                {"skill": m.skill, "matched_with": m.matched_with}
                for m in job_score.skills_details.fuzzy_matches
            ],
            "missing_required": job_score.skills_details.missing_required,
            "missing_preferred": job_score.skills_details.missing_preferred,
        }

    # Add location insights if available
    if job_score.geo_details:
        from scoring_engine.geo_scorer import GeoScorer

        geo_scorer = GeoScorer()
        breakdown["location_insights"] = geo_scorer.get_location_insights(
            job_score.geo_details
        )

    return ScoreBreakdownResponse(**breakdown)


@router.post("/export")
async def export_scores(
    resume_id: str = Query(..., description="Resume ID"),
    format: str = Query("csv", description="Export format (csv or json)"),
    include_details: bool = Query(True, description="Include detailed breakdowns"),
    current_user: Dict = Depends(get_current_user),
):
    """
    Export scoring results in CSV or JSON format with progress tracking

    Requires authentication.
    """
    start_time = time.time()
    user_id = current_user["user_id"]
    # Use authenticated client if we have a valid token, otherwise use service client
    if current_user.get("token") and current_user.get("token") != "test":
        from api.utils.database import get_authenticated_supabase_client
        try:
            supabase = get_authenticated_supabase_client(current_user["token"])
            logger.info(f"Using authenticated client for user {current_user['user_id']}")
        except Exception as e:
            logger.warning(f"Failed to use authenticated client: {e}, falling back to service client")
            from api.utils.database import get_supabase_service_client
            supabase = get_supabase_service_client()
    else:
        # Fallback to service client for trusted services or test tokens
        from api.utils.database import get_supabase_service_client
        supabase = get_supabase_service_client()
        logger.info(f"Using service client for user {current_user['user_id']} (trusted service or test)")
    
    # Start activity logging
    log_id = await activity_logger.log_action_start(
        user_id=user_id,
        action_type="csv_export",
        metadata={
            "resume_id": resume_id,
            "format": format,
            "include_details": include_details,
        }
    )
    
    logger.info(f"Starting {format} export for resume {resume_id}, user {user_id}")

    try:
        # Fetch scoring results
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={"stage": "fetching_scores", "message": "Retrieving scoring results..."}
        )
        
        response = (
            supabase.table("scores")
            .select("*, job_postings!inner(title, company_name, location)")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .order("total_score", desc=True)
            .execute()
        )

        if not response.data:
            await activity_logger.log_action_complete(
                log_id=log_id,
                success=False,
                error_details="No scoring results found"
            )
            raise HTTPException(status_code=404, detail="No scoring results found")
        
        logger.info(f"Found {len(response.data)} scores to export")

        # Convert to JobScore objects
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={"stage": "preparing_data", "message": f"Preparing {len(response.data)} records..."}
        )
        
        scores = []
        for idx, result in enumerate(response.data, 1):
            job = result.get("job_postings", {})
            score = JobScore(
                job_id=result["job_id"],
                title=job.get("title", "Unknown"),
                company_name=job.get("company_name", "Unknown"),
                total_score=float(result["total_score"]),
                rank=idx,
                percentile=100 - (idx / len(response.data) * 100),
                cosine_sim=float(result["cosine_sim"]),
                skill_overlap=float(result["skill_overlap"]),
                seniority_fit=float(result["seniority_fit"]),
                geodist_km=float(result["geodist_km"]) if result["geodist_km"] else None,
                recency_bonus=float(result["recency_bonus"]),
            )
            scores.append(score)

        # Generate export content
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={"stage": "generating_export", "message": f"Generating {format.upper()} file..."}
        )
        
        explainer = ScoreExplainer()

        if format == "csv":
            content = explainer.export_to_csv(scores, include_breakdowns=include_details)
            media_type = "text/csv"
            filename = f"job_matches_{resume_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            content = explainer.export_to_json(scores, include_details=include_details)
            media_type = "application/json"
            filename = f"job_matches_{resume_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Calculate file size
        file_size_kb = len(content.encode()) / 1024
        processing_time = int((time.time() - start_time) * 1000)
        
        # Log successful completion
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=True,
            result_data={
                "resume_id": resume_id,
                "format": format,
                "records_exported": len(scores),
                "file_size_kb": round(file_size_kb, 2),
                "filename": filename,
                "processing_time_ms": processing_time,
                "include_details": include_details,
            }
        )
        
        logger.info(
            f"Export completed: {len(scores)} records, {file_size_kb:.2f}KB, "
            f"{processing_time}ms for user {user_id}"
        )

        from fastapi.responses import Response

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        
        # Log failure
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=False,
            error_details=str(e)
        )
        
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/optimize-weights")
async def optimize_scoring_weights(
    sweep_config: Optional[Dict[str, Any]] = None,
    current_user: Dict = Depends(get_current_user),
):
    """
    Create a W&B sweep for optimizing scoring weights

    Requires authentication.
    """
    if not sweep_config:
        from api.services.experiments import get_default_sweep_config

        sweep_config = get_default_sweep_config()

    tracker = ExperimentTracker()
    sweep_id = tracker.create_sweep(sweep_config)

    if not sweep_id:
        raise HTTPException(
            status_code=500, detail="Failed to create optimization sweep"
        )

    return {
        "sweep_id": sweep_id,
        "project": tracker.project_name,
        "config": sweep_config,
        "instructions": f"Run sweep agent with: wandb agent {tracker.entity}/{tracker.project_name}/{sweep_id}",
    }


# Background tasks
async def store_scoring_results(
    resume_id: str, scores: List[JobScore], user_id: str, supabase
):
    """Store scoring results in database for caching and history"""
    try:
        # First, check which scores already exist
        existing_scores = (
            supabase.table("scores")
            .select("job_id")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )
        existing_job_ids = {score["job_id"] for score in existing_scores.data or []}

        records = []
        for score in scores[:50]:  # Store top 50
            # Skip if score already exists for this job
            if score.job_id in existing_job_ids:
                continue

            record = {
                "resume_id": resume_id,
                "job_id": score.job_id,
                "user_id": user_id,
                "cosine_sim": score.cosine_sim,
                "skill_overlap": score.skill_overlap,
                "seniority_fit": score.seniority_fit,
                "geodist_km": score.geodist_km if score.geodist_km else None,
                "recency_bonus": score.recency_bonus,
                "total_score": score.total_score,
            }
            records.append(record)

        if records:
            supabase.table("scores").insert(records).execute()
            logger.info(f"Stored {len(records)} new scores for resume {resume_id}")

    except Exception as e:
        logger.error(f"Failed to store scoring results: {e}")
