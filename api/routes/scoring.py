"""
API routes for job scoring and ranking
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.auth import get_current_user
from api.services.experiments import ExperimentConfig, ExperimentTracker
from api.services.score_explainer import ScoreExplainer
from api.utils.database import get_supabase_client
from scoring_engine.ranker import JobRanker, JobScore, ScoringWeights

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scores", tags=["scoring"])


# Request/Response Models
class ScoringRequest(BaseModel):
    """Request model for scoring jobs"""

    resume_id: str = Field(..., description="Resume ID to score against")
    job_ids: Optional[List[str]] = Field(
        None, description="Specific job IDs to score (optional)"
    )
    limit: int = Field(
        100, ge=1, le=500, description="Maximum number of results"
    )
    min_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Minimum score threshold"
    )
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
            supabase.table("resumes")
            .select("*")
            .eq("resume_id", resume_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Resume not found")

        resume = response.data[0]

        # Get resume embedding
        embedding_response = (
            supabase.table("resume_embeddings")
            .select("embedding")
            .eq("resume_id", resume_id)
            .execute()
        )

        if not embedding_response.data:
            raise HTTPException(
                status_code=404, detail="Resume embedding not found"
            )

        resume["embedding"] = np.array(embedding_response.data[0]["embedding"])

        return resume

    except Exception as e:
        logger.error(f"Error fetching resume data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_jobs_data(job_ids: Optional[List[str]], limit: int, supabase):
    """Fetch jobs data and embeddings from database"""
    try:
        # Build query
        query = supabase.table("jobs").select("*")

        if job_ids:
            query = query.in_("job_id", job_ids)
        else:
            # Get recent, active jobs
            query = query.eq("is_active", True).order("posted_at", desc=True)

        query = query.limit(limit)
        response = query.execute()

        if not response.data:
            return [], []

        jobs = response.data
        job_ids = [j["job_id"] for j in jobs]

        # Get job embeddings
        embedding_response = (
            supabase.table("job_embeddings")
            .select("job_id, embedding")
            .in_("job_id", job_ids)
            .execute()
        )

        # Create embedding lookup
        embedding_lookup = {
            e["job_id"]: np.array(e["embedding"])
            for e in embedding_response.data
        }

        # Align embeddings with jobs
        embeddings = []
        filtered_jobs = []
        for job in jobs:
            if job["job_id"] in embedding_lookup:
                filtered_jobs.append(job)
                embeddings.append(embedding_lookup[job["job_id"]])

        if embeddings:
            embeddings = np.array(embeddings)

        return filtered_jobs, embeddings

    except Exception as e:
        logger.error(f"Error fetching jobs data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# API Endpoints
@router.get("/", response_model=List[ScoreResponse])
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
    supabase = get_supabase_client()

    try:
        # Get scores from database
        response = (
            supabase.table("scores")
            .select(
                "*, job_postings!inner(title, company_name, location, posted_at)"
            )
            .eq("resume_id", resume_id)
            .eq("user_id", current_user["user_id"])
            .order("total_score", desc=True)
            .limit(limit)
            .execute()
        )

        if not response.data:
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
                        float(score["geodist_km"])
                        if score["geodist_km"]
                        else None
                    ),
                    recency_bonus=float(score["recency_bonus"]),
                    match_level=(
                        "high"
                        if float(score["total_score"]) > 0.7
                        else (
                            "medium"
                            if float(score["total_score"]) > 0.5
                            else "low"
                        )
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
    Run scoring for a resume against jobs

    Requires authentication.
    """
    start_time = time.time()
    supabase = get_supabase_client()

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
        resume_data = await get_resume_data(request.resume_id, supabase)
        resume_embedding = resume_data.pop("embedding")

        # Fetch jobs data
        jobs_data, job_embeddings = await get_jobs_data(
            request.job_ids,
            request.limit * 2,  # Fetch more to account for filtering
            supabase,
        )

        if not jobs_data:
            return BatchScoringResponse(
                resume_id=request.resume_id,
                total_jobs_scored=0,
                processing_time_ms=0,
                results=[],
                experiment_run_id=experiment_run_id,
            )

        # Initialize ranker with custom weights if provided
        weights = ScoringWeights()
        if (
            request.experiment_config
            and "weights" in request.experiment_config
        ):
            weights_dict = request.experiment_config["weights"]
            weights = ScoringWeights(**weights_dict)

        ranker = JobRanker(weights=weights)

        # Run ranking
        scores = ranker.rank_jobs(
            jobs_data=jobs_data,
            resume_data=resume_data,
            resume_embedding=resume_embedding,
            job_embeddings=job_embeddings,
            top_k=request.limit,
            min_score_threshold=request.min_score,
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

        return BatchScoringResponse(
            resume_id=request.resume_id,
            total_jobs_scored=len(results),
            processing_time_ms=processing_time_ms,
            results=results,
            experiment_run_id=experiment_run_id,
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
    supabase = get_supabase_client()

    # Fetch stored score or recalculate
    score_response = (
        supabase.table("scoring_results")
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
    include_details: bool = Query(
        True, description="Include detailed breakdowns"
    ),
    current_user: Dict = Depends(get_current_user),
):
    """
    Export scoring results in CSV or JSON format

    Requires authentication.
    """
    supabase = get_supabase_client()

    # Fetch scoring results
    response = (
        supabase.table("scoring_results")
        .select("*")
        .eq("resume_id", resume_id)
        .eq("user_id", current_user["user_id"])
        .order("score", desc=True)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="No scoring results found")

    # Convert to JobScore objects
    scores = []
    for result in response.data:
        score = JobScore(
            job_id=result["job_id"],
            title=result["job_title"],
            company_name=result["company_name"],
            total_score=result["score"],
            rank=result["rank"],
            percentile=result["percentile"],
            cosine_sim=result["cosine_sim"],
            skill_overlap=result["skill_overlap"],
            seniority_fit=result["seniority_fit"],
            geodist_km=result["geodist_km"],
            recency_bonus=result["recency_bonus"],
        )
        scores.append(score)

    explainer = ScoreExplainer()

    if format == "csv":
        content = explainer.export_to_csv(
            scores, include_breakdowns=include_details
        )
        media_type = "text/csv"
        filename = (
            f"scores_{resume_id}_{datetime.now().strftime('%Y%m%d')}.csv"
        )
    else:
        content = explainer.export_to_json(
            scores, include_details=include_details
        )
        media_type = "application/json"
        filename = (
            f"scores_{resume_id}_{datetime.now().strftime('%Y%m%d')}.json"
        )

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
        existing_job_ids = {
            score["job_id"] for score in existing_scores.data or []
        }

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
            logger.info(
                f"Stored {len(records)} new scores for resume {resume_id}"
            )

    except Exception as e:
        logger.error(f"Failed to store scoring results: {e}")
