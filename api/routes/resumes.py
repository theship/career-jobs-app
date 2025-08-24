"""Resume management routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from datetime import datetime
import uuid

from ..services.auth import get_current_user
from ..models.resumes import Resume, ResumeVersion, ResumeCreate, ResumeUpdate
from ..services.storage import StorageService
from ..services.resume_processor import ResumeProcessor
from ..utils.db import get_db_connection

router = APIRouter(prefix="/resumes", tags=["resumes"])

# Services will be injected as dependencies
storage_service = StorageService()
resume_processor = ResumeProcessor()


@router.post("/upload", response_model=Resume)
async def upload_resume(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """Upload and process a new resume."""
    # Validate file type
    if not file.filename.endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF, DOCX, and TXT files are supported."
        )
    
    # Validate file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit."
        )
    
    try:
        # Upload to Supabase Storage
        file_path = await storage_service.upload_resume(
            file=file,
            user_id=current_user["sub"]
        )
        
        # Extract text and process
        text_content = await resume_processor.extract_text(file)
        
        # Extract skills using multi-stage pipeline
        skills_data = await resume_processor.extract_skills(text_content)
        
        # Generate embeddings
        embedding = await resume_processor.generate_embedding(text_content)
        
        # Create resume record
        resume_id = str(uuid.uuid4())
        resume_data = {
            "id": resume_id,
            "user_id": current_user["sub"],
            "name": name or file.filename,
            "file_path": file_path,
            "text_content": text_content,
            "skills": skills_data["skills"],
            "skills_metadata": {
                "extraction_method": skills_data["method"],
                "confidence_scores": skills_data["confidence_scores"],
                "evidence_spans": skills_data["evidence_spans"],
                "coverage": skills_data["coverage"]
            },
            "embedding": embedding,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Save to database
        async with db.pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO resumes (
                    id, user_id, name, file_path, text_content,
                    skills, skills_metadata, embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                RETURNING *
                """,
                resume_id,
                current_user["sub"],
                resume_data["name"],
                resume_data["file_path"],
                resume_data["text_content"],
                resume_data["skills"],
                resume_data["skills_metadata"],
                embedding
            )
        
        return Resume(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )


@router.get("/", response_model=List[Resume])
async def list_resumes(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """List all resumes for the current user."""
    async with db.pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT * FROM resumes
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            current_user["sub"]
        )
    
    return [Resume(**row) for row in results]


@router.get("/{resume_id}", response_model=Resume)
async def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """Get a specific resume by ID."""
    async with db.pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT * FROM resumes
            WHERE id = $1 AND user_id = $2
            """,
            resume_id,
            current_user["sub"]
        )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found"
        )
    
    return Resume(**result)


@router.put("/{resume_id}", response_model=Resume)
async def update_resume(
    resume_id: str,
    update_data: ResumeUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """Update a resume's metadata."""
    async with db.pool.acquire() as conn:
        # First, create a version snapshot
        current_resume = await conn.fetchrow(
            """
            SELECT * FROM resumes
            WHERE id = $1 AND user_id = $2
            """,
            resume_id,
            current_user["sub"]
        )
        
        if not current_resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        # Create version record
        await conn.execute(
            """
            INSERT INTO resume_versions (
                id, resume_id, version_number, name, text_content,
                skills, skills_metadata, embedding
            )
            SELECT 
                gen_random_uuid(), id, 
                COALESCE((SELECT MAX(version_number) + 1 FROM resume_versions WHERE resume_id = $1), 1),
                name, text_content, skills, skills_metadata, embedding
            FROM resumes
            WHERE id = $1
            """,
            resume_id
        )
        
        # Update resume
        update_fields = []
        update_values = []
        param_count = 1
        
        if update_data.name is not None:
            update_fields.append(f"name = ${param_count}")
            update_values.append(update_data.name)
            param_count += 1
        
        if update_data.skills is not None:
            update_fields.append(f"skills = ${param_count}")
            update_values.append(update_data.skills)
            param_count += 1
        
        update_fields.append(f"updated_at = ${param_count}")
        update_values.append(datetime.utcnow())
        param_count += 1
        
        update_values.extend([resume_id, current_user["sub"]])
        
        result = await conn.fetchrow(
            f"""
            UPDATE resumes
            SET {', '.join(update_fields)}
            WHERE id = ${param_count} AND user_id = ${param_count + 1}
            RETURNING *
            """,
            *update_values
        )
    
    return Resume(**result)


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """Delete a resume and its associated data."""
    async with db.pool.acquire() as conn:
        # Check ownership
        resume = await conn.fetchrow(
            """
            SELECT * FROM resumes
            WHERE id = $1 AND user_id = $2
            """,
            resume_id,
            current_user["sub"]
        )
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        # Delete from storage
        await storage_service.delete_resume(resume["file_path"])
        
        # Delete versions first (foreign key constraint)
        await conn.execute(
            "DELETE FROM resume_versions WHERE resume_id = $1",
            resume_id
        )
        
        # Delete resume
        await conn.execute(
            "DELETE FROM resumes WHERE id = $1",
            resume_id
        )
    
    return {"message": "Resume deleted successfully"}


@router.post("/{resume_id}/reprocess")
async def reprocess_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db_connection)
):
    """Reprocess a resume with updated extraction logic."""
    async with db.pool.acquire() as conn:
        resume = await conn.fetchrow(
            """
            SELECT * FROM resumes
            WHERE id = $1 AND user_id = $2
            """,
            resume_id,
            current_user["sub"]
        )
        
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume not found"
            )
        
        try:
            # Re-extract skills with latest pipeline
            skills_data = await resume_processor.extract_skills(resume["text_content"])
            
            # Re-generate embeddings if needed
            embedding = await resume_processor.generate_embedding(resume["text_content"])
            
            # Update resume
            result = await conn.fetchrow(
                """
                UPDATE resumes
                SET skills = $1,
                    skills_metadata = $2,
                    embedding = $3::vector,
                    updated_at = $4
                WHERE id = $5
                RETURNING *
                """,
                skills_data["skills"],
                {
                    "extraction_method": skills_data["method"],
                    "confidence_scores": skills_data["confidence_scores"],
                    "evidence_spans": skills_data["evidence_spans"],
                    "coverage": skills_data["coverage"]
                },
                embedding,
                datetime.utcnow(),
                resume_id
            )
            
            return {"message": "Resume reprocessed successfully", "resume": Resume(**result)}
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reprocess resume: {str(e)}"
            )