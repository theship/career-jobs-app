"""Resume management routes."""

import csv
import io
import logging
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from ..models.resumes import Resume, ResumeUpdate
from ..services.activity_logger import activity_logger
from ..services.auth import get_current_user
from ..services.resume_processor import ResumeProcessor
from ..utils.advanced_rate_limit import advanced_limiter
from ..utils.database import get_authenticated_supabase_client
from ..utils.security import (
    FileSecurityError,
    calculate_file_hash,
    validate_csv,
    validate_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])

# Initialize services
resume_processor = ResumeProcessor()


@router.post("/upload", response_model=Resume)
@advanced_limiter.limit("resume_upload", "5/hour")  # Rate limit: 5 uploads per hour
async def upload_resume(
    request: Request,  # Required for rate limiter
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Upload and process a new resume with detailed progress tracking."""
    start_time = time.time()
    user_id = current_user["user_id"]

    file_size = file.size if hasattr(file, "size") else "unknown"
    logger.info(
        f"=== RESUME UPLOAD START === User: {user_id}, "
        f"File: {file.filename}, Size: {file_size}"
    )

    # Start activity logging
    log_id = await activity_logger.log_action_start(
        user_id=user_id,
        action_type="resume_upload",
        metadata={
            "filename": file.filename,
            "content_type": file.content_type,
            "custom_name": name,
        },
    )

    # Read file content
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    logger.info(f"File size: {file_size_mb:.2f}MB")

    # Validate and sanitize file based on type
    logger.info(f"Validating and sanitizing file: {file.filename}")
    try:
        if file.filename.lower().endswith(".pdf"):
            # Validate and sanitize PDF
            sanitized_content, safe_filename = validate_pdf(file_content, file.filename)
            file_content = sanitized_content
        else:
            # For now, reject non-PDF files until we add support
            await activity_logger.log_action_complete(
                log_id=log_id,
                success=False,
                error_details="Currently only PDF files are supported.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Currently only PDF files are supported.",
            )
    except FileSecurityError as e:
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=False,
            error_details=str(e.detail),
        )
        raise
    except Exception as e:
        logger.error(f"File validation error: {e}")
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=False,
            error_details="File validation failed.",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File validation failed. Please ensure your file is a valid PDF.",
        )

    try:
        # Update progress: File validated
        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "validated",
                "file_size_mb": round(file_size_mb, 2),
            },
        )
        # Check if we have a valid token
        if not current_user.get("token"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Valid authentication token required for upload",
            )

        # Use authenticated Supabase client with user's JWT
        logger.info(
            f"Current user info: user_id={current_user.get('user_id')}, "
            f"has_token={bool(current_user.get('token'))}, "
            f"trusted_service={current_user.get('trusted_service')}"
        )
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]
        logger.info(f"Processing upload for user_id: {user_id}")

        # Verify user exists in app_user table (should be created by trigger on signup)
        user_check = (
            supabase.table("app_user")
            .select("user_id")
            .eq("user_id", user_id)
            .execute()
        )

        if not user_check.data:
            # Auto-create app_user record for existing auth users
            # This handles users who signed up before the trigger was created
            logger.info(f"User {user_id} not found in app_user table - auto-creating")
            try:
                supabase.table("app_user").insert({"user_id": user_id}).execute()
                logger.info(f"Successfully created app_user record for {user_id}")
            except Exception as e:
                logger.error(f"Failed to auto-create app_user record: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to initialize user profile. Please try again.",
                )

        # Generate unique filename and storage path using secure hash
        file_hash = calculate_file_hash(file_content)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"{user_id}/{timestamp}_{file_hash[:8]}_{safe_filename}"

        # Upload to Supabase Storage using service client
        # Note: Storage bucket RLS policies need to be configured in Supabase dashboard
        # For now, we use service client for storage after validating the user
        logger.info(f"Uploading file to storage: {storage_filename}")
        try:
            from api.utils.database import get_supabase_service_client

            storage_client = get_supabase_service_client()
            storage_result = storage_client.storage.from_("resumes").upload(
                storage_filename,
                file_content,
                file_options={
                    "content-type": file.content_type or "application/octet-stream"
                },
            )
            logger.info(f"Storage upload result: {storage_result}")
        except Exception as storage_error:
            logger.error(f"Storage upload failed: {storage_error}")
            # Try to diagnose the specific issue
            if "row-level security policy" in str(storage_error):
                logger.error(
                    "RLS policy violation on storage bucket - "
                    "check Supabase dashboard settings"
                )
            raise

        # Extract text and process
        logger.info("Extracting text from file")
        text_extraction_start = time.time()
        # Create a mock file object with the content we already have

        class MockFile:
            def __init__(self, content: bytes, filename: str):
                self.content = content
                self.filename = filename
                self._position = 0

            async def read(self) -> bytes:
                return self.content

            async def seek(self, position: int) -> None:
                self._position = position

        mock_file = MockFile(file_content, safe_filename)
        text_content = await resume_processor.extract_text(mock_file)
        text_extraction_time = int((time.time() - text_extraction_start) * 1000)

        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "text_extracted",
                "text_length": len(text_content),
                "extraction_time_ms": text_extraction_time,
            },
        )
        logger.info(
            f"Text extracted: {len(text_content)} characters in "
            f"{text_extraction_time}ms"
        )

        # Check for custom vocabulary
        custom_vocab = None
        vocab_response = (
            supabase.table("user_skills_vocab")
            .select("vocab_data, skills_count")
            .eq("user_id", user_id)
            .execute()
        )
        if vocab_response.data:
            custom_vocab = vocab_response.data[0]["vocab_data"]
            skills_count = vocab_response.data[0]["skills_count"]
            logger.info(f"Using custom skills vocabulary with {skills_count} skills")

            # Update vocab usage stats
            supabase.table("user_skills_vocab").update(
                {
                    "last_used_at": datetime.utcnow().isoformat(),
                    "usage_count": vocab_response.data[0].get("usage_count", 0) + 1,
                }
            ).eq("user_id", user_id).execute()

        # Extract skills using multi-stage pipeline with optional custom vocab
        logger.info("Extracting skills from resume")
        skills_extraction_start = time.time()
        skills_data = await resume_processor.extract_skills(text_content, custom_vocab)
        skills_extraction_time = int((time.time() - skills_extraction_start) * 1000)

        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "skills_extracted",
                "skills_found": len(skills_data.skills),
                "using_custom_vocab": custom_vocab is not None,
                "skills_extraction_time_ms": skills_extraction_time,
            },
        )
        logger.info(
            f"Skills extracted: {len(skills_data.skills)} skills in "
            f"{skills_extraction_time}ms"
        )

        # Generate embeddings
        logger.info("Generating embeddings")
        embedding_start = time.time()
        embedding = await resume_processor.generate_embedding(text_content)
        embedding_time = int((time.time() - embedding_start) * 1000)

        await activity_logger.update_action_progress(
            log_id=log_id,
            status="in_progress",
            progress_data={
                "stage": "embeddings_generated",
                "embedding_dims": len(embedding),
                "embedding_time_ms": embedding_time,
            },
        )
        logger.info(
            f"Embeddings generated: {len(embedding)} dimensions in {embedding_time}ms"
        )

        # Create resume record
        resume_data = {
            "user_id": user_id,
            "filename": name or file.filename,
            "storage_path": storage_filename,
            "sha256": file_hash,
            "text_content": text_content,
            "embedding": embedding,
        }

        logger.info(f"Creating resume record in database for user {user_id}")
        try:
            insert_response = supabase.table("resumes").insert(resume_data).execute()
            resume_id = (
                insert_response.data[0]["resume_id"]
                if insert_response.data
                else "unknown"
            )
            logger.info(f"Database insert successful: resume_id = {resume_id}")
        except Exception as db_error:
            logger.error(f"Database insert failed: {db_error}")
            if "row-level security policy" in str(db_error):
                logger.error(
                    f"RLS policy violation on resumes table for user {user_id}"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save resume: {str(db_error)}",
            )

        if not insert_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create resume record",
            )

        resume_record = insert_response.data[0]

        # Store extracted skills in a separate table if they exist
        if skills_data.skills:
            logger.info(f"Storing {len(skills_data.skills)} extracted skills")
            skills_records = [
                {
                    "resume_id": resume_record["resume_id"],
                    "skill_name": skill,
                    "confidence": (
                        skills_data.confidence_scores.get(skill, 0.0)
                        if skills_data.confidence_scores
                        else 0.0
                    ),
                }
                for skill in skills_data.skills
            ]

            try:
                supabase.table("resume_skills").insert(skills_records).execute()
            except Exception as e:
                logger.warning(f"Failed to store skills: {e}")

        # Return the resume with skills count and complete logging
        resume_record["skills_count"] = len(skills_data.skills)

        # Calculate total processing time
        total_time = int((time.time() - start_time) * 1000)

        # Log successful completion
        await activity_logger.log_action_complete(
            log_id=log_id,
            success=True,
            result_data={
                "resume_id": resume_record["resume_id"],
                "filename": resume_record["filename"],
                "text_length": len(text_content),
                "skills_found": len(skills_data.skills),
                "total_processing_time_ms": total_time,
                "storage_path": storage_filename,
            },
        )

        logger.info(
            f"Resume upload completed successfully: "
            f"resume_id={resume_record['resume_id']}, "
            f"skills={len(skills_data.skills)}, time={total_time}ms"
        )

        return Resume(**resume_record)

    except Exception as e:
        logger.error(f"Failed to process resume: {e}")

        # Log failure
        await activity_logger.log_action_complete(
            log_id=log_id, success=False, error_details=str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}",
        )


@router.get("/", response_model=List[Resume])
async def list_resumes(
    current_user: dict = Depends(get_current_user),
):
    """List all resumes for the current user."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        response = (
            supabase.table("resumes")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        resumes = []
        for resume in response.data:
            # Get skills count for each resume
            skills_response = (
                supabase.table("resume_skills")
                .select("skill_name")
                .eq("resume_id", resume["resume_id"])
                .execute()
            )
            resume["skills_count"] = (
                len(skills_response.data) if skills_response.data else 0
            )
            resumes.append(Resume(**resume))

        return resumes

    except Exception as e:
        logger.error(f"Failed to list resumes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list resumes: {str(e)}",
        )


@router.get("/skills-vocab")
async def get_skills_vocabulary(
    current_user: dict = Depends(get_current_user),
):
    """Get the user's custom skills vocabulary if it exists."""
    try:
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        response = (
            supabase.table("user_skills_vocab")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            return {
                "has_custom_vocab": False,
                "message": "No custom skills vocabulary found",
            }

        vocab = response.data[0]
        vocab_data = vocab.get("vocab_data", [])

        # Handle vocab_data whether it's a list or dict
        sample_skills = []
        if isinstance(vocab_data, list):
            sample_skills = [
                v.get("skill", "") for v in vocab_data[:10] if isinstance(v, dict)
            ]
        elif isinstance(vocab_data, dict):
            # If stored as dict, get first 10 skills
            sample_skills = list(vocab_data.keys())[:10]

        return {
            "has_custom_vocab": True,
            "skills_count": vocab.get("skills_count", 0),
            "uploaded_at": vocab.get("uploaded_at"),
            "sample_skills": sample_skills,
        }

    except Exception as e:
        logger.error(f"Failed to get skills vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get skills vocabulary: {str(e)}",
        )


@router.get("/{resume_id}", response_model=Resume)
async def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific resume by ID."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        response = (
            supabase.table("resumes")
            .select("*")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

        resume = response.data[0]

        # Get skills for this resume
        skills_response = (
            supabase.table("resume_skills")
            .select("skill_name")
            .eq("resume_id", resume_id)
            .execute()
        )
        resume["skills_count"] = (
            len(skills_response.data) if skills_response.data else 0
        )

        return Resume(**resume)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resume: {str(e)}",
        )


@router.put("/{resume_id}", response_model=Resume)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a resume's metadata."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        # Check if resume exists and belongs to user
        check_response = (
            supabase.table("resumes")
            .select("resume_id")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

        # Build update data
        update_dict = {}
        if update_data.filename is not None:
            update_dict["filename"] = update_data.filename

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        # Update resume
        response = (
            supabase.table("resumes")
            .update(update_dict)
            .eq("resume_id", resume_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update resume",
            )

        resume = response.data[0]

        # Get skills count
        skills_response = (
            supabase.table("resume_skills")
            .select("skill_name")
            .eq("resume_id", resume_id)
            .execute()
        )
        resume["skills_count"] = (
            len(skills_response.data) if skills_response.data else 0
        )

        return Resume(**resume)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update resume: {str(e)}",
        )


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a resume and its associated data."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        # Check if resume exists and belongs to user
        check_response = (
            supabase.table("resumes")
            .select("storage_path")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

        storage_path = check_response.data[0]["storage_path"]

        # Delete from storage
        if storage_path:
            try:
                supabase.storage.from_("resumes").remove([storage_path])
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {e}")

        # Delete skills first (foreign key constraint)
        supabase.table("resume_skills").delete().eq("resume_id", resume_id).execute()

        # Delete resume
        supabase.table("resumes").delete().eq("resume_id", resume_id).execute()

        return {"message": "Resume deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete resume: {str(e)}",
        )


@router.post("/{resume_id}/reprocess")
async def reprocess_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Reprocess a resume with updated extraction logic."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        # Get resume
        response = (
            supabase.table("resumes")
            .select("*")
            .eq("resume_id", resume_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found",
            )

        resume = response.data[0]

        # Check for custom vocabulary
        custom_vocab = None
        vocab_response = (
            supabase.table("user_skills_vocab")
            .select("vocab_data")
            .eq("user_id", user_id)
            .execute()
        )
        if vocab_response.data:
            custom_vocab = vocab_response.data[0]["vocab_data"]
            logger.info("Using custom skills vocabulary for reprocessing")

        # Re-extract skills with latest pipeline and optional custom vocab
        skills_data = await resume_processor.extract_skills(
            resume["text_content"], custom_vocab
        )

        # Re-generate embeddings if needed
        embedding = await resume_processor.generate_embedding(resume["text_content"])

        # Update resume with new embedding
        (
            supabase.table("resumes")
            .update({"embedding": embedding})
            .eq("resume_id", resume_id)
            .execute()
        )

        # Delete old skills
        supabase.table("resume_skills").delete().eq("resume_id", resume_id).execute()

        # Store new skills
        if skills_data.skills:
            skills_records = [
                {
                    "resume_id": resume_id,
                    "skill_name": skill,
                    "confidence": (
                        skills_data.confidence_scores.get(skill, 0.0)
                        if skills_data.confidence_scores
                        else 0.0
                    ),
                }
                for skill in skills_data.skills
            ]
            supabase.table("resume_skills").insert(skills_records).execute()

        # Return updated resume
        resume["skills_count"] = len(skills_data.skills)

        return {
            "message": "Resume reprocessed successfully",
            "resume": Resume(**resume),
            "extracted_skills": skills_data.skills,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reprocess resume: {str(e)}",
        )


@router.post("/skills-vocab")
@advanced_limiter.limit(
    "skills_upload", "10/hour"
)  # Rate limit: 10 skills uploads per hour
async def upload_skills_vocabulary(
    request: Request,  # Required for rate limiter
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a custom skills vocabulary CSV file for the user.
    The CSV must contain columns: skill, category, aliases, tags
    """
    try:
        # Read file content
        content = await file.read()

        # Validate and sanitize CSV
        try:
            df, safe_filename = validate_csv(content, file.filename)
        except FileSecurityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e.detail)
            )

        # Convert DataFrame to CSV text for existing processing
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_text = csv_buffer.getvalue()
        reader = csv.DictReader(io.StringIO(csv_text))

        # Validate required columns
        required_columns = {"skill", "category", "aliases", "tags"}
        if not reader.fieldnames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file is empty or invalid",
            )

        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}",
            )

        # Parse and validate rows
        vocab_data = []
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
            if not row.get("skill"):
                continue  # Skip empty skill rows

            vocab_entry = {
                "skill": row["skill"].strip(),
                "category": row["category"].strip() if row["category"] else "",
                "aliases": (
                    [a.strip() for a in row["aliases"].split("|") if a.strip()]
                    if row["aliases"]
                    else []
                ),
                "tags": (
                    [t.strip() for t in row["tags"].split(",") if t.strip()]
                    if row["tags"]
                    else []
                ),
            }
            vocab_data.append(vocab_entry)

        if not vocab_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file contains no valid skill entries",
            )

        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(current_user["token"])
        user_id = current_user["user_id"]

        # Check if user already has custom vocab
        existing_vocab = (
            supabase.table("user_skills_vocab")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )

        # Store or update the vocabulary
        vocab_record = {
            "user_id": user_id,
            "vocab_data": vocab_data,
            "uploaded_at": datetime.utcnow().isoformat(),
            "skills_count": len(vocab_data),
        }

        if existing_vocab.data:
            # Update existing record
            response = (
                supabase.table("user_skills_vocab")
                .update(vocab_record)
                .eq("user_id", user_id)
                .execute()
            )
        else:
            # Insert new record
            response = (
                supabase.table("user_skills_vocab").insert(vocab_record).execute()
            )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save skills vocabulary",
            )

        return {
            "message": "Skills vocabulary uploaded successfully",
            "skills_count": len(vocab_data),
            "sample_skills": [v["skill"] for v in vocab_data[:5]],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload skills vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload skills vocabulary: {str(e)}",
        )


# Moved to before /{resume_id} route
