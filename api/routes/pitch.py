"""
API endpoints for pitch generation functionality
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.services.auth import get_current_user
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
        "general",
        description="Type of interview: general, technical, behavioral",
    )


# Initialize services (in production, these would be dependency injected)
# Lazy initialization to avoid startup failures
pitch_service = None
research_service = None


def get_pitch_service():
    global pitch_service
    # Always try to initialize if not available
    # This allows the service to start working once the key is added
    if pitch_service is None:
        try:
            pitch_service = PitchGeneratorService()
            logger.info("Pitch service initialized successfully")
        except ValueError as e:
            logger.warning(f"Pitch service not available: {e}")
            # Don't cache the failure - raise but allow retry
            raise ValueError(f"Pitch service not configured: {e}")
    return pitch_service


def get_research_service():
    global research_service
    if research_service is None:
        try:
            research_service = CompanyResearchService()
        except ValueError as e:
            logger.warning(f"Research service not available: {e}")
            raise HTTPException(
                status_code=503,
                detail="Research service not configured. Please set OPENAI_API_KEY.",
            )
    return research_service


# In-memory storage for pitches (in production, use database)
pitch_storage: Dict[str, Dict[str, Any]] = {}


async def _get_resume_data(resume_id: str, user_token: str) -> Dict[str, Any]:
    """Get actual resume data from database"""
    # Use service client for now since we're in development mode
    from api.utils.database import get_supabase_service_client
    supabase = get_supabase_service_client()
    
    # Get resume from database
    response = supabase.table("resumes").select("*").eq("resume_id", resume_id).limit(1).execute()
    
    if not response or not response.data:
        # Fall back to mock data if resume not found
        return {
            "resume_id": resume_id,
            "skills": [
                "Python",
                "JavaScript",
                "React",
                "Django",
                "PostgreSQL",
                "Docker",
            ],
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
                {
                    "degree": "BS Computer Science",
                    "school": "UC Berkeley",
                    "year": "2018",
                }
            ],
            "highlights": [
                "Led team of 5 engineers",
                "Improved API performance by 40%",
                "Shipped 3 major features",
            ],
        }
    
    resume = response.data[0]
    
    # Convert database format to expected format
    return {
        "resume_id": resume["resume_id"],
        "skills": resume.get("skills", []),
        "years_experience": resume.get("years_experience", 0),
        "seniority": resume.get("seniority", "mid"),
        "location": resume.get("location", ""),
        "experience": resume.get("parsed_data", {}).get("experience", []),
        "education": resume.get("parsed_data", {}).get("education", []),
        "highlights": resume.get("parsed_data", {}).get("highlights", []),
        "text": resume.get("content", ""),
    }


async def _get_job_data(job_id: str, user_token: str) -> Dict[str, Any]:
    """Get actual job data from database"""
    # Use service client for now since we're in development mode
    from api.utils.database import get_supabase_service_client
    supabase = get_supabase_service_client()
    
    # Get job from database
    response = supabase.table("job_postings").select("*").eq("job_id", job_id).limit(1).execute()
    
    if not response or not response.data:
        # Fall back to mock data if job not found
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
    
    job = response.data[0]
    
    # Convert database format to expected format
    return {
        "job_id": job["job_id"],
        "title": job.get("title", ""),
        "company_name": job.get("company_name", ""),
        "company_domain": job.get("company_domain", ""),
        "required_skills": job.get("required_skills", []),
        "preferred_skills": job.get("preferred_skills", []),
        "seniority": job.get("seniority", "mid"),
        "location": job.get("location", ""),
        "remote_type": job.get("remote_type", ""),
        "responsibilities": job.get("responsibilities", []),
        "requirements": job.get("requirements", []),
        "description": job.get("description", ""),
    }


async def _get_skills_score(resume_id: str, job_id: str, user_token: str) -> float:
    """Get actual skills matching score from database or calculate it"""
    # Use service client for now since we're in development mode
    from api.utils.database import get_supabase_service_client
    supabase = get_supabase_service_client()
    
    # Try to get existing score from database
    response = supabase.table("scores").select("skill_overlap").eq("resume_id", resume_id).eq("job_id", job_id).limit(1).execute()
    
    if response and response.data:
        return response.data[0].get("skill_overlap", 0.75)
    
    # Fall back to default score
    return 0.75  # 75% match


@router.post("/generate", response_model=PitchResponse)
async def generate_pitch(
    request: PitchGenerationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
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
        logger.info(
            f"User {current_user.get('user_id', 'unknown')} generating pitch for job {request.job_id}"
        )

        # Get resume and job data from database
        user_token = current_user.get('token', '')
        resume_data = await _get_resume_data(request.resume_id, user_token)
        job_data = await _get_job_data(request.job_id, user_token)

        # Get company research if requested
        company_research = {}
        if request.include_research and job_data.get("company_domain"):
            try:
                service = get_research_service()
                company_research = service.research_company(
                    company_domain=job_data["company_domain"],
                    use_cache=True,
                )
            except Exception as e:
                logger.warning(f"Failed to get company research: {e}")
                # Continue without research

        # Get skills matching score
        skills_score = await _get_skills_score(request.resume_id, request.job_id, user_token)

        # Try to generate pitch with OpenAI
        try:
            service = get_pitch_service()
            logger.info("Got pitch service successfully")
            pitch = service.generate_pitch(
                resume_data=resume_data,
                job_data=job_data,
                company_research=company_research,
                skills_match_score=skills_score,
            )
            logger.info("Generated pitch successfully")
            
            # Add required fields for PitchResponse
            pitch["job_id"] = request.job_id

            # Calculate quality scores
            quality_scores = service.score_pitch_quality(pitch)
            pitch["quality_scores"] = quality_scores

            # Store pitch for later retrieval
            user_id = current_user.get('user_id', 'unknown')
            pitch_id = f"{user_id}_{request.job_id}_{len(pitch_storage)}"
            pitch_storage[pitch_id] = pitch
            pitch["pitch_id"] = pitch_id

            # Log quality warning if score is low
            if quality_scores["overall"] < 0.7:
                logger.warning(
                    f"Low quality pitch generated: {quality_scores['overall']:.2f}"
                )

            return PitchResponse(**pitch)
            
        except (HTTPException, ValueError, Exception) as e:
            # If OpenAI is not available, return the data fields instead
            logger.warning(f"Pitch generation failed: {type(e).__name__}: {str(e)}, returning data fields")
            
            # Format the job data
            job_fields = f"""**Job Information:**
Title: {job_data.get('title', 'N/A')}
Company: {job_data.get('company_name', 'N/A')}
Location: {job_data.get('location', 'N/A')}
Remote Type: {job_data.get('remote_type', 'N/A')}
Seniority: {job_data.get('seniority', 'N/A')}

Required Skills:
{chr(10).join(f"• {skill}" for skill in job_data.get('required_skills', []))}

Preferred Skills:
{chr(10).join(f"• {skill}" for skill in job_data.get('preferred_skills', []))}

Responsibilities:
{chr(10).join(f"• {resp}" for resp in job_data.get('responsibilities', [])[:3])}

Requirements:
{chr(10).join(f"• {req}" for req in job_data.get('requirements', [])[:3])}"""

            # Format the resume data
            resume_fields = f"""**Your Profile:**
Years of Experience: {resume_data.get('years_experience', 'N/A')}
Seniority Level: {resume_data.get('seniority', 'N/A')}
Location: {resume_data.get('location', 'N/A')}

Skills:
{chr(10).join(f"• {skill}" for skill in resume_data.get('skills', [])[:10])}

Recent Experience:
{chr(10).join(f"• {exp.get('title', 'N/A')} at {exp.get('company', 'N/A')}" for exp in resume_data.get('experience', [])[:3])}

Key Highlights:
{chr(10).join(f"• {highlight}" for highlight in resume_data.get('highlights', [])[:3])}

Skills Match Score: {skills_score:.0%}"""
            
            # Create a fallback response
            fallback_pitch = {
                "job_id": request.job_id,
                "job_title": job_data.get("title", "Position"),
                "company_name": job_data.get("company_name", "Company"),
                "headline": "Pitch Generation Service Unavailable",
                "opening": "The AI pitch generation service is currently unavailable. Below are the matched job and profile details that would be used to generate your personalized pitch:",
                "two_minute_pitch": f"{job_fields}\n\n{resume_fields}",
                "bullet_points": [
                    "AI pitch generation requires OpenAI API configuration",
                    "Your resume and job details have been successfully matched",
                    f"Your skills match score for this position is {skills_score:.0%}"
                ],
                "why_this_company": "Company research data would appear here when AI service is available.",
                "why_this_role": "Role-specific pitch would appear here when AI service is available.",
                "questions_to_ask": [
                    {"question": "What are the key challenges for this role?", "purpose": "Understand priorities"},
                    {"question": "How would you describe the team culture?", "purpose": "Assess fit"},
                    {"question": "What does success look like in this position?", "purpose": "Align expectations"}
                ],
                "potential_objections": [
                    {"objection": "Service unavailable", "response": "Please try again later or contact support"}
                ],
                "closing_statement": "When the AI service is available, you'll receive a fully personalized pitch tailored to this specific opportunity.",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "skills_match_score": skills_score
            }
            
            return PitchResponse(**fallback_pitch)

    except Exception as e:
        logger.error(f"Failed to generate pitch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate pitch: {str(e)}")


@router.post("/email-template")
async def generate_email_template(
    request: EmailTemplateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
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
        service = get_pitch_service()
        email = service.generate_email_template(
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
                service = get_research_service()
                company_research = service.research_company(
                    company_domain=company_domain,
                    use_cache=True,
                )
            except Exception as e:
                logger.warning(f"Could not get company research: {e}")

        # Generate interview prep
        service = get_pitch_service()
        prep = service.generate_interview_prep(
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
    current_user: Dict[str, Any] = Depends(get_current_user),
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
        service = get_pitch_service()
        scores = service.score_pitch_quality(pitch)

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
