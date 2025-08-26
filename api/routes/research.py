"""
API endpoints for company research functionality
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.auth import get_current_user
from api.services.research import CompanyResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


class CompanyResearchRequest(BaseModel):
    """Request model for company research"""

    company_domain: str = Field(
        ..., description="Company website domain", example="stripe.com"
    )
    use_cache: bool = Field(
        True, description="Whether to use cached results if available"
    )


class CompanyResearchResponse(BaseModel):
    """Response model for company research"""

    company_domain: str
    company_name: str
    industry: str
    headquarters: Optional[str] = None
    founded: Optional[str] = None
    competitors: list[Dict[str, Any]]
    excellence: list[Dict[str, Any]]
    shortcomings: list[Dict[str, Any]]
    aspirations: list[Dict[str, Any]]
    recent_news: Optional[list[Dict[str, Any]]] = None
    culture_values: Optional[list[Dict[str, Any]]] = None
    generated_at: str
    model_used: str
    quality_scores: Optional[Dict[str, float]] = None


class ClearCacheRequest(BaseModel):
    """Request model for clearing cache"""

    company_domain: Optional[str] = Field(
        None, description="Specific company to clear, or None for all"
    )


# Initialize service (in production, this would be dependency injected)
# Lazy initialization to avoid startup failures
research_service = None


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


@router.post("/generate", response_model=CompanyResearchResponse)
async def generate_company_research(
    request: CompanyResearchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> CompanyResearchResponse:
    """
    Generate or retrieve company research

    Args:
        request: Research request with company domain
        current_user: Authenticated user

    Returns:
        Structured company research data
    """
    try:
        logger.info(
            f"User {current_user.get('id', 'unknown')} requesting research for {request.company_domain}"
        )

        # Generate or retrieve research
        service = get_research_service()
        research = service.research_company(
            company_domain=request.company_domain,
            use_cache=request.use_cache,
        )

        # Calculate quality scores
        quality_scores = service.get_research_quality_score(research)
        research["quality_scores"] = quality_scores

        # Log quality warning if score is low
        if quality_scores["overall"] < 0.7:
            logger.warning(
                f"Low quality research generated for {request.company_domain}: {quality_scores['overall']:.2f}"
            )

        return CompanyResearchResponse(**research)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate research: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate company research"
        )


@router.get("/{company_domain}", response_model=CompanyResearchResponse)
async def get_company_research(
    company_domain: str,
    use_cache: bool = Query(
        True, description="Use cached results if available"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> CompanyResearchResponse:
    """
    Get company research by domain

    Args:
        company_domain: Company website domain
        use_cache: Whether to use cached results
        current_user: Authenticated user

    Returns:
        Company research data
    """
    try:
        service = get_research_service()
        research = service.research_company(
            company_domain=company_domain,
            use_cache=use_cache,
        )

        # Add quality scores
        research["quality_scores"] = service.get_research_quality_score(
            research
        )

        return CompanyResearchResponse(**research)

    except Exception as e:
        logger.error(f"Failed to get research for {company_domain}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve company research"
        )


@router.post("/cache/clear")
async def clear_research_cache(
    request: ClearCacheRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Clear research cache

    Args:
        request: Cache clear request
        current_user: Authenticated user (must be admin in production)

    Returns:
        Status message
    """
    try:
        service = get_research_service()
        service.clear_cache(company_domain=request.company_domain)

        if request.company_domain:
            message = f"Cleared cache for {request.company_domain}"
        else:
            message = "Cleared all research cache"

        logger.info(f"User {current_user.get('id', 'unknown')}: {message}")
        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/quality/{company_domain}")
async def get_research_quality(
    company_domain: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get quality scores for existing research

    Args:
        company_domain: Company website domain
        current_user: Authenticated user

    Returns:
        Quality scores and improvement suggestions
    """
    try:
        # Get cached research (don't generate new)
        service = get_research_service()
        research = service._get_cached_research(company_domain)

        if not research:
            raise HTTPException(
                status_code=404,
                detail=f"No research found for {company_domain}. Generate research first.",
            )

        # Calculate quality scores
        scores = service.get_research_quality_score(research)

        # Generate improvement suggestions
        suggestions = []
        if scores["competitor_coverage"] < 0.7:
            suggestions.append("Add more competitor analysis")
        if scores["source_coverage"] < 0.7:
            suggestions.append("Include more source URLs for aspirations")
        if scores["detail_level"] < 0.7:
            suggestions.append("Provide more detailed descriptions")

        return {
            "company_domain": company_domain,
            "quality_scores": scores,
            "improvement_suggestions": suggestions,
            "meets_quality_threshold": scores["overall"] >= 0.7,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assess research quality: {e}")
        raise HTTPException(status_code=500, detail="Failed to assess quality")
