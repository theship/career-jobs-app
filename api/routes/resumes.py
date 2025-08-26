"""Resume management routes."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Security,
    UploadFile,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

security = HTTPBearer()

logger = logging.getLogger(__name__)

from ..models.resumes import Resume, ResumeCreate, ResumeUpdate, ResumeVersion
from ..services.auth import get_current_user
from ..services.resume_processor import ResumeProcessor
from ..services.storage import StorageService
from ..utils.database import (
    get_authenticated_supabase_client,
    get_supabase_client,
    get_supabase_service_client,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])

# Services will be injected as dependencies
storage_service = StorageService()
resume_processor = ResumeProcessor()


@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Upload and process a new resume."""
    logger.info(f"Upload request from user: {current_user.get('user_id')}")
    logger.info(f"Current user data: {current_user}")
    logger.info(
        f"File: {file.filename}, Size: {file.size if hasattr(file, 'size') else 'unknown'}"
    )

    # Use authenticated Supabase client with user's JWT
    supabase = get_authenticated_supabase_client(credentials.credentials)
    user_id = current_user["user_id"]

    # Check if user exists in app_user table
    user_check = (
        supabase.table("app_user").select("user_id").eq("user_id", user_id).execute()
    )

    if not user_check.data:
        # Create user in app_user table
        logger.info(f"Creating app_user record for {user_id}")
        supabase.table("app_user").insert({"user_id": user_id}).execute()

    # Validate file type
    if not file.filename.endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF, DOCX, and TXT files are supported.",
        )

    # Validate file size (max 10MB)
    if hasattr(file, "size") and file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit.",
        )

    try:
        logger.info("Uploading to Supabase Storage...")
        # Upload to Supabase Storage
        file_path = await storage_service.upload_resume(
            file=file, user_id=current_user["user_id"]
        )
        logger.info(f"File uploaded to: {file_path}")

        # Extract text and process
        logger.info("Extracting text from file...")
        text_content = await resume_processor.extract_text(file)

        # Extract skills using multi-stage pipeline
        skills_data = await resume_processor.extract_skills(text_content)

        # Generate embeddings
        embedding = await resume_processor.generate_embedding(text_content)

        # Create resume record
        resume_id = str(uuid.uuid4())
        resume_data = {
            "id": resume_id,
            "user_id": current_user["user_id"],
            "name": name or file.filename,
            "file_path": file_path,
            "text_content": text_content,
            "skills": skills_data.skills,
            "skills_metadata": {
                "extraction_method": skills_data.method,
                "confidence_scores": skills_data.confidence_scores,
                "evidence_spans": skills_data.evidence_spans,
                "coverage": skills_data.coverage,
            },
            "embedding": embedding,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Save to database (already have supabase client from above)

        # Prepare data for insertion (matching schema.sql columns)
        # Compute SHA256 hash of the file
        import hashlib

        file_content = await file.read()
        await file.seek(0)  # Reset file pointer
        file_hash = hashlib.sha256(file_content).digest()

        insert_data = {
            "user_id": current_user["user_id"],
            "filename": resume_data["name"],
            "storage_path": resume_data["file_path"],
            "text_content": resume_data["text_content"],
            "embedding": (
                embedding.tolist() if hasattr(embedding, "tolist") else embedding
            ),
            "sha256": file_hash.hex(),  # Store as hex string for JSON compatibility
        }

        response = supabase.table("resumes").insert(insert_data).execute()

        if not response.data:
            raise Exception("Failed to save resume to database")

        return Resume(**response.data[0])

    except Exception as e:
        logger.error(f"Failed to process resume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}",
        )


@router.get("/debug-auth")
async def debug_auth(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check auth structure."""
    return {"current_user": current_user}


@router.get("/", response_model=List[Resume])
async def list_resumes(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """List all resumes for the current user."""
    supabase = get_authenticated_supabase_client(credentials.credentials)

    response = (
        supabase.table("resumes")
        .select("*")
        .eq("user_id", current_user["user_id"])
        .order("created_at", desc=True)
        .execute()
    )

    return [Resume(**row) for row in response.data] if response.data else []


@router.get("/{resume_id}", response_model=Resume)
async def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Get a specific resume by ID."""
    supabase = get_authenticated_supabase_client(credentials.credentials)

    response = (
        supabase.table("resumes")
        .select("*")
        .eq("resume_id", int(resume_id))
        .eq("user_id", current_user["user_id"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    return Resume(**response.data[0])


@router.put("/{resume_id}", response_model=Resume)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Update a resume's metadata."""
    supabase = get_authenticated_supabase_client(credentials.credentials)

    # First, get current resume
    current_response = (
        supabase.table("resumes")
        .select("*")
        .eq("resume_id", int(resume_id))
        .eq("user_id", current_user["user_id"])
        .execute()
    )

    if not current_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    current_resume = current_response.data[0]

    # Create version record
    version_data = {
        "resume_id": current_resume["resume_id"],
        "storage_path": current_resume.get("storage_path", resume.get("file_path", "")),
        "sha256": current_resume.get("sha256"),
    }

    supabase.table("resume_versions").insert(version_data).execute()

    # Update resume
    update_data_dict = {}
    if update_data.name is not None:
        update_data_dict["filename"] = update_data.name

    if update_data_dict:
        response = (
            supabase.table("resumes")
            .update(update_data_dict)
            .eq("resume_id", int(resume_id))
            .eq("user_id", current_user["user_id"])
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update resume",
            )

        return Resume(**response.data[0])

    return Resume(**current_resume)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Delete a resume and its associated data."""
    supabase = get_authenticated_supabase_client(credentials.credentials)

    # Check ownership and get resume
    response = (
        supabase.table("resumes")
        .select("*")
        .eq("resume_id", int(resume_id))
        .eq("user_id", current_user["user_id"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    resume = response.data[0]

    # Delete from storage
    await storage_service.delete_resume(
        resume.get("storage_path", resume.get("file_path", ""))
    )

    # Delete versions first (foreign key constraint)
    supabase.table("resume_versions").delete().eq("resume_id", int(resume_id)).execute()

    # Delete resume
    supabase.table("resumes").delete().eq("resume_id", int(resume_id)).execute()

    return {"message": "Resume deleted successfully"}


@router.post("/{resume_id}/reprocess")
async def reprocess_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Reprocess a resume with updated extraction logic."""
    supabase = get_authenticated_supabase_client(credentials.credentials)

    response = (
        supabase.table("resumes")
        .select("*")
        .eq("resume_id", int(resume_id))
        .eq("user_id", current_user["user_id"])
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    resume = response.data[0]

    try:
        # Re-extract skills with latest pipeline
        skills_data = await resume_processor.extract_skills(resume["text_content"])

        # Re-generate embeddings if needed
        embedding = await resume_processor.generate_embedding(resume["text_content"])

        # Update resume
        update_data = {
            "embedding": (
                embedding.tolist() if hasattr(embedding, "tolist") else embedding
            ),
        }

        result = (
            supabase.table("resumes")
            .update(update_data)
            .eq("resume_id", int(resume_id))
            .execute()
        )

        if not result.data:
            raise Exception("Failed to update resume")

        return {
            "message": "Resume reprocessed successfully",
            "resume": Resume(**result.data[0]),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reprocess resume: {str(e)}",
        )
