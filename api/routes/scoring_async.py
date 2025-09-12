"""
Async scoring routes with SSE streaming and Redis pubsub
"""

import ast
import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.services.auth import get_current_user
from api.utils.database import get_supabase_service_client
from api.utils.redis_client import get_redis_client
from scoring_engine.ranker import JobRanker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scores", tags=["scoring"])


class ScoringRequest(BaseModel):
    """Request model for async scoring"""

    resume_id: str = Field(..., description="Resume ID to score against")
    limit: int = Field(500, ge=1, le=1000, description="Maximum number of results")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum score threshold")
    batch_size: int = Field(
        10, ge=1, le=50, description="Batch size for progressive updates"
    )


class ScoringStartResponse(BaseModel):
    """Response when scoring starts"""

    task_id: str
    resume_id: str
    status: str = "processing"
    message: str = "Scoring started"


@router.post("/run", response_model=ScoringStartResponse)
async def start_scoring(
    request: ScoringRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
):
    """
    Start async scoring process.
    Returns immediately with a task_id for SSE streaming.
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    user_id = current_user["user_id"]

    # Initialize Redis for task tracking
    redis = get_redis_client()
    task_key = f"scoring:task:{task_id}"

    # Store initial task status
    redis.setex(
        task_key,
        600,  # 10 minute TTL
        json.dumps(
            {
                "task_id": task_id,
                "resume_id": request.resume_id,
                "user_id": user_id,
                "status": "initializing",
                "created_at": time.time(),
                "progress": {"total": 0, "processed": 0, "current_batch": 0},
            }
        ),
    )

    # Start background scoring task
    background_tasks.add_task(
        process_scoring_async,
        task_id=task_id,
        resume_id=request.resume_id,
        user_id=user_id,
        limit=request.limit,
        min_score=request.min_score,
        batch_size=request.batch_size,
    )

    logger.info(f"Started scoring task {task_id} for resume {request.resume_id}")

    return ScoringStartResponse(
        task_id=task_id,
        resume_id=request.resume_id,
        status="processing",
        message="Scoring started - connect to SSE endpoint for updates",
    )


@router.get("/stream/{task_id}")
async def stream_scoring_updates(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """
    Stream scoring progress via Server-Sent Events (SSE).
    Client connects here after starting scoring to receive real-time updates.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        redis = get_redis_client()
        pubsub = redis.pubsub()
        channel = f"scoring:updates:{task_id}"

        try:
            # Subscribe to task updates
            pubsub.subscribe(channel)

            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"

            # Check current task status
            task_data = redis.get(f"scoring:task:{task_id}")
            if task_data:
                task_info = json.loads(task_data)
                yield f"data: {json.dumps({'type': 'status', **task_info})}\n\n"

            # Listen for updates with timeout
            last_heartbeat = time.time()
            while True:
                message = pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    update = json.loads(data)
                    yield f"data: {json.dumps(update)}\n\n"

                    # Close stream when complete
                    if update.get("type") == "complete":
                        break

                # Send heartbeat every 30 seconds to keep connection alive
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f": heartbeat\n\n"
                    last_heartbeat = current_time
                    
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for task {task_id}")
        except Exception as e:
            logger.error(f"SSE stream error for task {task_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def process_scoring_async(
    task_id: str,
    resume_id: str,
    user_id: str,
    limit: int,
    min_score: float,
    batch_size: int,
):
    """
    Process scoring asynchronously with progressive updates via Redis pubsub.
    """
    redis = get_redis_client()
    supabase = get_supabase_service_client()
    task_key = f"scoring:task:{task_id}"
    channel = f"scoring:updates:{task_id}"

    try:
        # Update status to fetching data
        redis.setex(
            task_key,
            600,
            json.dumps(
                {
                    "task_id": task_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "fetching_data",
                    "progress": {"total": 0, "processed": 0},
                }
            ),
        )

        # Publish status update
        redis.publish(
            channel,
            json.dumps(
                {
                    "type": "status",
                    "status": "fetching_data",
                    "message": "Fetching resume and job data...",
                }
            ),
        )

        # Fetch resume data
        resume_response = (
            supabase.table("resumes")
            .select("*")
            .eq("resume_id", resume_id)
            .single()
            .execute()
        )
        if not resume_response.data:
            raise ValueError(f"Resume {resume_id} not found")

        resume_data = resume_response.data
        resume_embedding = resume_data.get("embedding", [])

        # Convert embedding from string to list if needed
        if isinstance(resume_embedding, str):
            try:
                # Handle numpy string representation
                if resume_embedding.startswith("np."):
                    # Extract the array from numpy string representation
                    # Remove numpy prefixes and parse as literal
                    cleaned = (
                        resume_embedding.replace("np.str_('", "")
                        .replace("')", "")
                        .replace("np.float32(", "")
                        .replace(")", "")
                    )
                    resume_embedding = ast.literal_eval(cleaned)
                else:
                    resume_embedding = json.loads(resume_embedding)
            except Exception as e:
                logger.warning(f"Failed to parse resume embedding: {e}")
                resume_embedding = []

        # Fetch all jobs
        jobs_response = supabase.table("job_postings").select("*").execute()
        jobs_data = jobs_response.data or []
        total_jobs = len(jobs_data)

        logger.info(
            f"Task {task_id}: Processing {total_jobs} jobs for resume {resume_id}"
        )

        # Update status to scoring
        redis.setex(
            task_key,
            600,
            json.dumps(
                {
                    "task_id": task_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "scoring",
                    "progress": {"total": total_jobs, "processed": 0},
                }
            ),
        )

        redis.publish(
            channel,
            json.dumps(
                {
                    "type": "status",
                    "status": "scoring",
                    "message": f"Scoring {total_jobs} jobs...",
                    "total": total_jobs,
                }
            ),
        )

        # Initialize ranker
        ranker = JobRanker()
        all_scores = []

        # Process jobs in batches
        for i in range(0, total_jobs, batch_size):
            batch = jobs_data[i:i + batch_size]
            batch_num = i // batch_size + 1

            # Score batch
            batch_scores = []
            for job in batch:
                # Get job embedding
                job_embedding = job.get("embedding", [])

                # Convert embedding from string to list if needed
                if isinstance(job_embedding, str):
                    try:
                        # Handle numpy string representation
                        if job_embedding.startswith("np."):
                            # Extract the array from numpy string representation
                            # Remove numpy prefixes and parse as literal
                            cleaned = (
                                job_embedding.replace("np.str_('", "")
                                .replace("')", "")
                                .replace("np.float32(", "")
                                .replace(")", "")
                            )
                            job_embedding = ast.literal_eval(cleaned)
                        else:
                            job_embedding = json.loads(job_embedding)
                    except Exception:
                        # Skip jobs with unparseable embeddings
                        job_embedding = []

                if not job_embedding:
                    continue

                # Calculate score
                score = ranker.score_single_job(
                    job, resume_data, resume_embedding, job_embedding
                )
                if score.total_score >= min_score:
                    batch_scores.append(score)

            # Store batch in database
            if batch_scores:
                records = []
                for score in batch_scores:
                    records.append(
                        {
                            "resume_id": resume_id,
                            "job_id": score.job_id,
                            "user_id": user_id,
                            "total_score": float(score.total_score),
                            "cosine_sim": float(score.cosine_sim),
                            "skill_overlap": float(score.skill_overlap),
                            "seniority_fit": float(score.seniority_fit),
                            "geodist_km": (
                                float(score.geodist_km) if score.geodist_km else None
                            ),
                            "recency_bonus": float(score.recency_bonus),
                        }
                    )

                # Insert batch into database
                supabase.table("scores").insert(records).execute()
                all_scores.extend(batch_scores)

            # Update progress
            processed = min(i + batch_size, total_jobs)
            redis.setex(
                task_key,
                600,
                json.dumps(
                    {
                        "task_id": task_id,
                        "resume_id": resume_id,
                        "user_id": user_id,
                        "status": "scoring",
                        "progress": {
                            "total": total_jobs,
                            "processed": processed,
                            "current_batch": batch_num,
                            "scores_found": len(all_scores),
                        },
                    }
                ),
            )

            # Publish progress update with the new batch of scores
            batch_data = []
            if batch_scores:
                # Get job details for this batch
                job_ids = [s.job_id for s in batch_scores]
                jobs_detail = {j["job_id"]: j for j in batch if j["job_id"] in job_ids}

                for score in batch_scores:
                    job = jobs_detail.get(score.job_id, {})
                    # Determine match level based on score
                    match_level = "low"
                    if score.total_score >= 0.7:
                        match_level = "high"
                    elif score.total_score >= 0.5:
                        match_level = "medium"
                    
                    batch_data.append(
                        {
                            "job_id": score.job_id,
                            "title": job.get("title"),
                            "company_name": job.get("company_name"),
                            "location": job.get("location"),
                            "posted_at": job.get("posted_at"),
                            "total_score": score.total_score,
                            "cosine_sim": score.cosine_sim,
                            "skill_overlap": score.skill_overlap,
                            "seniority_fit": score.seniority_fit,
                            "geodist_km": score.geodist_km,
                            "recency_bonus": score.recency_bonus,
                            "match_level": match_level,
                        }
                    )

            # Publish progress update with new matches
            redis.publish(
                channel,
                json.dumps(
                    {
                        "type": "progress",
                        "batch": batch_num,
                        "processed": processed,
                        "total": total_jobs,
                        "scores_found": len(all_scores),
                        "new_matches": batch_data,  # Include the actual match data
                        "message": f"Processed {processed}/{total_jobs} jobs, found {len(all_scores)} matches",
                    }
                ),
            )

            logger.info(
                f"Task {task_id}: Processed batch {batch_num}, {processed}/{total_jobs} jobs"
            )

            # Small delay to avoid overwhelming
            await asyncio.sleep(0.1)

        # Sort scores by total_score descending and limit
        all_scores.sort(key=lambda x: x.total_score, reverse=True)
        final_scores = all_scores[:limit]

        # Mark complete
        redis.setex(
            task_key,
            600,
            json.dumps(
                {
                    "task_id": task_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "complete",
                    "progress": {
                        "total": total_jobs,
                        "processed": total_jobs,
                        "scores_found": len(final_scores),
                    },
                    "completed_at": time.time(),
                }
            ),
        )

        # Publish completion
        redis.publish(
            channel,
            json.dumps(
                {
                    "type": "complete",
                    "total_processed": total_jobs,
                    "matches_found": len(final_scores),
                    "message": f"Scoring complete! Found {len(final_scores)} matches",
                }
            ),
        )

        logger.info(
            f"Task {task_id}: Completed scoring, found {len(final_scores)} matches"
        )

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)

        # Update status to failed
        redis.setex(
            task_key,
            600,
            json.dumps(
                {
                    "task_id": task_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "failed",
                    "error": str(e),
                    "failed_at": time.time(),
                }
            ),
        )

        # Publish error
        redis.publish(
            channel,
            json.dumps({"type": "error", "message": f"Scoring failed: {str(e)}"}),
        )


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """Get current status of a scoring task."""
    redis = get_redis_client()
    task_data = redis.get(f"scoring:task:{task_id}")

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return json.loads(task_data)


@router.get("")
async def get_scores(
    resume_id: str = Query(..., description="Resume ID to get scores for"),
    limit: int = Query(500, description="Maximum number of scores to return"),
    current_user: Dict = Depends(get_current_user),
):
    """
    Get stored scores for a resume from the database.
    """
    supabase = get_supabase_service_client()

    try:
        response = (
            supabase.table("scores")
            .select("*, job_postings!inner(title, company_name, location, posted_at)")
            .eq("resume_id", resume_id)
            .eq("user_id", current_user["user_id"])
            .order("total_score", desc=True)
            .limit(limit)
            .execute()
        )

        if not response.data:
            return []

        # Format response
        results = []
        for score in response.data:
            job = score.get("job_postings", {})
            
            # Determine match level based on score
            match_level = "low"
            if score["total_score"] >= 0.7:
                match_level = "high"
            elif score["total_score"] >= 0.5:
                match_level = "medium"
                
            results.append(
                {
                    "job_id": score["job_id"],
                    "title": job.get("title"),
                    "company_name": job.get("company_name"),
                    "location": job.get("location"),
                    "posted_at": job.get("posted_at"),
                    "total_score": score["total_score"],
                    "cosine_sim": score["cosine_sim"],
                    "skill_overlap": score["skill_overlap"],
                    "seniority_fit": score["seniority_fit"],
                    "geodist_km": score["geodist_km"],
                    "recency_bonus": score["recency_bonus"],
                    "match_level": match_level,
                }
            )

        return results

    except Exception as e:
        logger.error(f"Error fetching scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))
