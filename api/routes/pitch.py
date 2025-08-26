"""
API endpoints for pitch generation functionality
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from api.models import User
from api.services.pitch_generator import PitchGeneratorService
from api.services.research import CompanyResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pitch", tags=["pitch"])


class PitchGenerationRequest(BaseModel):
    """Request model for pitch generation"""

    resume_id: str = Field(..., description="ID of the resume to use")
    job_id: str = Field(..., description="ID of the job to apply for")
    include_research: bool = Field(
        True, description="Include company research in pitch"
    )
    personalization_level: str = Field(
        "high", description="Level of personalization: low, medium, high"
    )


class PitchResponse(BaseModel):
    """Response model for generated pitch"""

    job_id: str
    job_title: str
    company_name: str
    headline: str
    opening: str
    two_minute_pitch: str
    bullet_points: list[str]
    why_this_company: str
    why_this_role: str
    questions_to_ask: list[Dict[str, str]]
    potential_objections: list[Dict[str, str]]
    closing_statement: str
    generated_at: str
    skills_match_score: Optional[float] = None
    quality_scores: Optional[Dict[str, float]] = None


class EmailTemplateRequest(BaseModel):
    """Request model for email template generation"""

    pitch_id: str = Field(..., description="ID of previously generated pitch")
    recipient_name: Optional[str] = Field(None, description="Name of recipient")


class InterviewPrepRequest(BaseModel):
    """Request model for interview prep generation"""

    pitch_id: str = Field(..., description="ID of previously generated pitch")
    interview_type: str = Field(
        "general", description="Type of interview: general, technical, behavioral"
    )


# Initialize services (in production, these would be dependency injected)
pitch_service = PitchGeneratorService()
research_service = CompanyResearchService()

# In-memory storage for pitches (in production, use database)
pitch_storage: Dict[str, Dict[str, Any]] = {}


def _get_mock_resume_data(resume_id: str) -> Dict[str, Any]:
    """Mock function to get resume data (replace with real DB query)"""
    return {
        "resume_id": resume_id,
        "skills": ["Python", "JavaScript", "React", "Django", "PostgreSQL", "Docker"],
        "years_experience": 5,
        "seniority": "senior",
        "location": "San Francisco, CA",
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "Tech Company",
                "duration": "2020-present",
                "technologies": ["Python", "React", "AWS"],
            }
        ],
        "education": [
            {"degree": "BS Computer Science", "school": "UC Berkeley", "year": "2018"}
        ],
        "highlights": [
            "Led team of 5 engineers",
            "Improved API performance by 40%",
            "Shipped 3 major features",
        ],
    }


def _get_mock_job_data(job_id: str) -> Dict[str, Any]:
    """Mock function to get job data (replace with real DB query)"""
    return {
        "job_id": job_id,
        "title": "Staff Software Engineer",
        "company_name": "Stripe",
        "company_domain": "stripe.com",
        "required_skills": ["Python", "distributed systems", "API design"],
        "preferred_skills": ["Rust", "payments experience", "fintech"],
        "seniority": "staff",
        "location": "San Francisco, CA",
        "remote_type": "Hybrid",
        "responsibilities": [
            "Design and build scalable payment systems",
            "Lead technical initiatives",
            "Mentor junior engineers",
        ],
        "requirements": [
            "7+ years experience",
            "Strong Python skills",
            "Experience with high-scale systems",
        ],
    }


def _get_mock_skills_score(resume_id: str, job_id: str) -> float:
    """Mock function to get skills matching score (replace with real calculation)"""
    return 0.75  # 75% match


@router.post("/generate", response_model=PitchResponse)
async def generate_pitch(
    request: PitchGenerationRequest,
    current_user: User = Depends(get_current_user),
) -> PitchResponse:
    """
    Generate a personalized pitch for a job application

    Args:
        request: Pitch generation request
        current_user: Authenticated user

    Returns:
        Generated pitch with multiple components
    """
    try:
        logger.info(f"User {current_user.id} generating pitch for job {request.job_id}")

        # Get resume and job data (mock for now)
        resume_data = _get_mock_resume_data(request.resume_id)
        job_data = _get_mock_job_data(request.job_id)

        # Get company research if requested
        company_research = {}
        if request.include_research and job_data.get("company_domain"):
            try:
                company_research = research_service.research_company(
                    company_domain=job_data["company_domain"],
                    use_cache=True,
                )
            except Exception as e:
                logger.warning(f"Failed to get company research: {e}")
                # Continue without research

        # Get skills matching score
        skills_score = _get_mock_skills_score(request.resume_id, request.job_id)

        # Generate pitch
        pitch = pitch_service.generate_pitch(
            resume_data=resume_data,
            job_data=job_data,
            company_research=company_research,
            skills_match_score=skills_score,
        )

        # Calculate quality scores
        quality_scores = pitch_service.score_pitch_quality(pitch)
        pitch["quality_scores"] = quality_scores

        # Store pitch for later retrieval
        pitch_id = f"{current_user.id}_{request.job_id}_{len(pitch_storage)}"
        pitch_storage[pitch_id] = pitch
        pitch["pitch_id"] = pitch_id

        # Log quality warning if score is low
        if quality_scores["overall"] < 0.7:
            logger.warning(
                f"Low quality pitch generated: {quality_scores['overall']:.2f}"
            )

        return PitchResponse(**pitch)

    except Exception as e:
        logger.error(f"Failed to generate pitch: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate pitch")


@router.post("/email-template")
async def generate_email_template(
    request: EmailTemplateRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Generate email template from existing pitch

    Args:
        request: Email template request
        current_user: Authenticated user

    Returns:
        Email subject and body
    """
    try:
        # Retrieve stored pitch
        pitch = pitch_storage.get(request.pitch_id)
        if not pitch:
            raise HTTPException(status_code=404, detail="Pitch not found")

        # Generate email template
        email = pitch_service.generate_email_template(
            pitch=pitch,
            recipient_name=request.recipient_name,
        )

        return email

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate email template: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate email template")


@router.post("/interview-prep")
async def generate_interview_prep(
    request: InterviewPrepRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate interview preparation materials

    Args:
        request: Interview prep request
        current_user: Authenticated user

    Returns:
        Interview preparation guide
    """
    try:
        # Retrieve stored pitch
        pitch = pitch_storage.get(request.pitch_id)
        if not pitch:
            raise HTTPException(status_code=404, detail="Pitch not found")

        # Get company research if available
        company_domain = pitch.get("company_domain")
        company_research = {}
        if company_domain:
            try:
                company_research = research_service.research_company(
                    company_domain=company_domain,
                    use_cache=True,
                )
            except Exception as e:
                logger.warning(f"Could not get company research: {e}")

        # Generate interview prep
        prep = pitch_service.generate_interview_prep(
            pitch=pitch,
            company_research=company_research,
        )

        # Add interview type specific content
        prep["interview_type"] = request.interview_type
        if request.interview_type == "technical":
            prep["technical_topics"] = [
                "Data structures and algorithms",
                "System design",
                "Code review exercise",
                "Technical problem solving",
            ]
        elif request.interview_type == "behavioral":
            prep["behavioral_questions"] = [
                "Tell me about a challenging project",
                "Describe a time you led a team",
                "How do you handle conflict?",
                "What's your biggest weakness?",
            ]

        return prep

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate interview prep: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate interview prep")


@router.get("/quality/{pitch_id}")
async def get_pitch_quality(
    pitch_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get quality assessment for a generated pitch

    Args:
        pitch_id: ID of the pitch
        current_user: Authenticated user

    Returns:
        Quality scores and improvement suggestions
    """
    try:
        # Retrieve stored pitch
        pitch = pitch_storage.get(pitch_id)
        if not pitch:
            raise HTTPException(status_code=404, detail="Pitch not found")

        # Calculate quality scores
        scores = pitch_service.score_pitch_quality(pitch)

        # Generate improvement suggestions
        suggestions = []
        if scores["headline_quality"] < 0.7:
            suggestions.append("Improve headline - make it more compelling")
        if scores["pitch_length"] < 1.0:
            suggestions.append("Adjust pitch length to 300-400 words")
        if scores["personalization"] < 1.0:
            suggestions.append("Add more personalized elements")

        return {
            "pitch_id": pitch_id,
            "quality_scores": scores,
            "improvement_suggestions": suggestions,
            "meets_quality_threshold": scores["overall"] >= 0.7,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assess pitch quality: {e}")
        raise HTTPException(status_code=500, detail="Failed to assess quality")
