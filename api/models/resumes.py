"""Resume data models."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResumeBase(BaseModel):
    """Base resume model."""

    name: str = Field(..., description="Resume name/title")
    skills: Optional[List[str]] = Field(
        default=[], description="Extracted skills"
    )
    skills_metadata: Optional[Dict[str, Any]] = Field(
        default={},
        description="Metadata about skill extraction (confidence, evidence, etc.)",
    )


class ResumeCreate(ResumeBase):
    """Model for creating a new resume."""

    pass


class ResumeUpdate(BaseModel):
    """Model for updating a resume."""

    filename: Optional[str] = None


class Resume(BaseModel):
    """Complete resume model matching database schema."""

    resume_id: int = Field(..., description="Resume ID")
    user_id: str = Field(..., description="User ID (UUID)")
    filename: str = Field(..., description="Original filename")
    storage_path: str = Field(..., description="Storage path in bucket")
    sha256: Optional[str] = Field(None, description="File hash")
    text_content: Optional[str] = Field(None, description="Extracted text")
    embedding: Optional[Any] = Field(None, description="Vector embedding")
    created_at: datetime = Field(..., description="Creation timestamp")
    skills_count: Optional[int] = Field(
        0, description="Number of extracted skills"
    )

    class Config:
        from_attributes = True


class ResumeVersion(BaseModel):
    """Resume version for tracking changes."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resume_id: str
    version_number: int
    name: str
    text_content: str
    skills: List[str]
    skills_metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SkillExtractionResult(BaseModel):
    """Result from skill extraction pipeline."""

    skills: List[str] = Field(..., description="Extracted skills list")
    method: str = Field(..., description="Extraction method used")
    confidence_scores: Dict[str, float] = Field(
        ..., description="Confidence score for each skill"
    )
    evidence_spans: Dict[str, List[Dict[str, int]]] = Field(
        ..., description="Character offsets for skill evidence in text"
    )
    coverage: float = Field(
        ..., description="Percentage of skills extracted from vocabulary"
    )
    years_experience: Optional[Dict[str, float]] = Field(
        default=None, description="Years of experience for each skill"
    )
