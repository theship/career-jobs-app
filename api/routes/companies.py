"""
User-facing Company Management Routes
Allows users to add and manage their own target companies
"""

import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.services.auth import get_current_user
from api.services.company_manager import CompanyManager
from api.utils.database import get_supabase_service_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


class CompanyAddRequest(BaseModel):
    """Request model for adding a company to user's watchlist"""

    company_name: str
    ats_system: Optional[str] = None  # If not provided, will auto-detect


class ATSDetectionResponse(BaseModel):
    """Response model for ATS detection"""

    company_name: str
    detected_ats: Optional[str]
    company_id: str
    confidence: float
    job_board_url: Optional[str]


class UserCompany(BaseModel):
    """Response model for a user's target company"""

    id: str
    company_name: str
    company_id: str
    ats_system: str
    job_board_url: Optional[str]
    active: bool
    last_checked: Optional[str]
    jobs_found: int = 0


async def detect_ats_system(company_name: str) -> ATSDetectionResponse:
    """
    Auto-detect which ATS system a company uses by testing endpoints.

    Args:
        company_name: Company name to check

    Returns:
        ATSDetectionResponse with detected ATS or None
    """
    # Normalize company name for URL (lowercase, remove spaces/special chars)
    import re

    company_id = re.sub(r"[^a-z0-9]", "", company_name.lower())

    # Test URLs for different ATS systems
    test_cases = [
        {
            "ats": "lever",
            "url": f"https://api.lever.co/v0/postings/{company_id}",
            "check_field": "data",
        },
        {
            "ats": "greenhouse",
            "url": f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs",
            "check_field": "jobs",
        },
        {
            "ats": "ashby",
            "url": f"https://jobs.ashby.com/{company_id}",
            "check_field": None,  # HTML response
        },
    ]

    async with httpx.AsyncClient(timeout=5.0) as client:
        for test in test_cases:
            try:
                response = await client.get(test["url"])

                if response.status_code == 200:
                    # Check if response looks valid
                    if test["check_field"]:
                        # JSON response
                        data = response.json()
                        if test["check_field"] in data:
                            return ATSDetectionResponse(
                                company_name=company_name,
                                detected_ats=test["ats"],
                                company_id=company_id,
                                confidence=0.9,
                                job_board_url=test["url"],
                            )
                    else:
                        # HTML response (Ashby)
                        if "ashby" in response.text.lower():
                            return ATSDetectionResponse(
                                company_name=company_name,
                                detected_ats="ashby",
                                company_id=company_id,
                                confidence=0.8,
                                job_board_url=f"https://jobs.ashby.com/{company_id}",
                            )
            except Exception as e:
                logger.debug(f"ATS detection failed for {test['ats']}: {e}")
                continue

    # No ATS detected
    return ATSDetectionResponse(
        company_name=company_name,
        detected_ats=None,
        company_id=company_id,
        confidence=0.0,
        job_board_url=None,
    )


@router.post("/detect-ats", response_model=ATSDetectionResponse)
async def detect_company_ats(
    company_name: str = Query(..., description="Company name to check"),
    current_user: dict = Depends(get_current_user),
):
    """
    Auto-detect which ATS system a company uses.
    Tests common ATS endpoints to identify the system.
    """
    try:
        result = await detect_ats_system(company_name)
        return result
    except Exception as e:
        logger.error(f"ATS detection failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to detect ATS system: {str(e)}"
        )


@router.post("/add", response_model=UserCompany)
async def add_company_to_watchlist(
    request: CompanyAddRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Add a company to user's personal watchlist.
    Will auto-detect ATS if not provided.
    """
    try:
        # Auto-detect ATS if not provided
        ats_system = request.ats_system
        company_id = None

        if not ats_system:
            detection = await detect_ats_system(request.company_name)
            if detection.detected_ats:
                ats_system = detection.detected_ats
                company_id = detection.company_id
                logger.info(
                    f"Auto-detected {ats_system} ATS for {request.company_name}"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not auto-detect ATS system. Please specify manually.",
                )

        if not company_id:
            # Generate company ID from name
            import re

            company_id = re.sub(r"[^a-z0-9]", "", request.company_name.lower())

        # Add to database
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Check if already exists
        existing = await company_manager.get_all_companies(
            active_only=False, ats_system=ats_system
        )

        for company in existing:
            if company["company_id"] == company_id:
                # Company already exists, just return it
                return UserCompany(
                    id=company["id"],
                    company_name=company["display_name"],
                    company_id=company["company_id"],
                    ats_system=company["ats_system"],
                    job_board_url=_get_job_board_url(
                        company["ats_system"], company["company_id"]
                    ),
                    active=company["active"],
                    last_checked=company.get("last_successful_fetch"),
                    jobs_found=0,  # TODO: Get actual count
                )

        # Add new company
        company = await company_manager.add_company(
            ats_system=ats_system,
            company_id=company_id,
            display_name=request.company_name,
            metadata={"added_by_user": current_user["user_id"]},
        )

        return UserCompany(
            id=company["id"],
            company_name=company["display_name"],
            company_id=company["company_id"],
            ats_system=company["ats_system"],
            job_board_url=_get_job_board_url(
                company["ats_system"], company["company_id"]
            ),
            active=True,
            last_checked=None,
            jobs_found=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add company: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add company: {str(e)}")


@router.get("/my-watchlist", response_model=List[UserCompany])
async def get_my_watchlist(
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's personal company watchlist.
    Returns all companies the user is tracking.
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Get all active companies (for now, all users see all companies)
        # TODO: Add user-specific filtering
        companies = await company_manager.get_all_companies(active_only=True)

        result = []
        for company in companies:
            result.append(
                UserCompany(
                    id=company["id"],
                    company_name=company["display_name"],
                    company_id=company["company_id"],
                    ats_system=company["ats_system"],
                    job_board_url=_get_job_board_url(
                        company["ats_system"], company["company_id"]
                    ),
                    active=company["active"],
                    last_checked=company.get("last_successful_fetch"),
                    jobs_found=0,  # TODO: Get actual count from job_postings
                )
            )

        return result

    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get watchlist: {str(e)}"
        )


@router.delete("/{company_id}")
async def remove_from_watchlist(
    company_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove a company from user's watchlist.
    (Currently just deactivates it globally - TODO: make user-specific)
    """
    try:
        supabase = get_supabase_service_client()
        company_manager = CompanyManager(supabase)

        # Deactivate the company
        await company_manager.update_company(
            company_id=company_id, updates={"active": False}
        )

        return {"message": "Company removed from watchlist"}

    except Exception as e:
        logger.error(f"Failed to remove company: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to remove company: {str(e)}"
        )


def _get_job_board_url(ats_system: str, company_id: str) -> str:
    """Generate the public job board URL for a company."""
    if ats_system == "lever":
        return f"https://jobs.lever.co/{company_id}"
    elif ats_system == "greenhouse":
        return f"https://boards.greenhouse.io/{company_id}"
    elif ats_system == "ashby":
        return f"https://jobs.ashby.com/{company_id}"
    else:
        return None
