"""Resume management routes."""

import hashlib
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..models.resumes import Resume, ResumeUpdate
from ..services.auth import get_current_user
from ..services.resume_processor import ResumeProcessor
from ..utils.database import get_authenticated_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])
security = HTTPBearer()

# Initialize services
resume_processor = ResumeProcessor()


@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Upload and process a new resume."""
    # Validate file type
    if not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF, DOCX, and TXT files are supported.",
        )

    # Validate file size (max 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit.",
        )
    await file.seek(0)  # Reset file pointer

    try:
        # Use authenticated Supabase client with user's JWT
        supabase = get_authenticated_supabase_client(credentials.credentials)
        user_id = current_user["user_id"]

        # Check if user exists in app_user table
        user_check = (
            supabase.table("app_user")
            .select("user_id")
            .eq("user_id", user_id)
            .execute()
        )

        if not user_check.data:
            # Create user in app_user table
            logger.info(f"Creating app_user record for {user_id}")
            supabase.table("app_user").insert({"user_id": user_id}).execute()

        # Generate unique filename and storage path
        file_hash = hashlib.sha256(file_content).hexdigest()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"{user_id}/{timestamp}_{file_hash[:8]}_{file.filename}"

        # Upload to Supabase Storage
        logger.info(f"Uploading file to storage: {storage_filename}")
        supabase.storage.from_("resumes").upload(
            storage_filename,
            file_content,
            file_options={
                "content-type": file.content_type or "application/octet-stream"
            },
        )

        # Extract text and process
        logger.info("Extracting text from file")
        text_content = await resume_processor.extract_text(file)

        # Extract skills using multi-stage pipeline
        logger.info("Extracting skills from resume")
        skills_data = await resume_processor.extract_skills(text_content)

        # Generate embeddings
        logger.info("Generating embeddings")
        embedding = await resume_processor.generate_embedding(text_content)

        # Create resume record
        resume_data = {
            "user_id": user_id,
            "filename": name or file.filename,
            "storage_path": storage_filename,
            "sha256": file_hash,
            "text_content": text_content,
            "embedding": embedding,
        }

        logger.info("Creating resume record in database")
        insert_response = supabase.table("resumes").insert(resume_data).execute()

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

        # Return the resume with skills count
        resume_record["skills_count"] = len(skills_data.skills)
        return Resume(**resume_record)

    except Exception as e:
        logger.error(f"Failed to process resume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}",
        )


@router.get("/", response_model=List[Resume])
async def list_resumes(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """List all resumes for the current user."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(credentials.credentials)
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


@router.get("/{resume_id}", response_model=Resume)
async def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get a specific resume by ID."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(credentials.credentials)
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update a resume's metadata."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(credentials.credentials)
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Delete a resume and its associated data."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(credentials.credentials)
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Reprocess a resume with updated extraction logic."""
    try:
        # Use authenticated Supabase client
        supabase = get_authenticated_supabase_client(credentials.credentials)
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

        # Re-extract skills with latest pipeline
        skills_data = await resume_processor.extract_skills(resume["text_content"])

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
