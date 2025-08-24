"""Resume data models."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class ResumeBase(BaseModel):
    """Base resume model."""
    name: str = Field(..., description="Resume name/title")
    skills: Optional[List[str]] = Field(default=[], description="Extracted skills")
    skills_metadata: Optional[Dict[str, Any]] = Field(
        default={},
        description="Metadata about skill extraction (confidence, evidence, etc.)"
    )


class ResumeCreate(ResumeBase):
    """Model for creating a new resume."""
    pass


class ResumeUpdate(BaseModel):
    """Model for updating a resume."""
    name: Optional[str] = None
    skills: Optional[List[str]] = None


class Resume(ResumeBase):
    """Complete resume model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    file_path: str
    text_content: str
    embedding: Optional[List[float]] = None
    created_at: datetime
    updated_at: datetime
    
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
        ..., 
        description="Confidence score for each skill"
    )
    evidence_spans: Dict[str, List[Dict[str, int]]] = Field(
        ...,
        description="Character offsets for skill evidence in text"
    )
    coverage: float = Field(
        ...,
        description="Percentage of skills extracted from vocabulary"
    )
    years_experience: Optional[Dict[str, float]] = Field(
        default=None,
        description="Years of experience for each skill"
    )