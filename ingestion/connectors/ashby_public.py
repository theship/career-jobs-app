"""
Public Ashby Connector - No authentication required
Uses Ashby's public job board API for job listings
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path

import httpx
from httpx import AsyncClient

from ingestion.connectors.base import ATSConnector, JobListing

logger = logging.getLogger(__name__)


class AshbyPublicConnector(ATSConnector):
    """Connector for Ashby's public job board API (no auth required)"""

    def __init__(self):
        """
        Initialize Ashby public connector
        
        Note: Companies are now loaded from database, not CSV
        """
        # No API key needed for public endpoints
        super().__init__(
            api_key="public",  # Placeholder since parent requires it
            base_url="https://api.ashbyhq.com/posting-api/job-board",
            rate_limit=1.0,  # 1 request per second (60 per minute)
        )
        # Companies will be loaded from database by orchestrator
        self.companies = []

    def set_companies(self, companies: List[dict]):
        """
        Set companies to fetch from (called by orchestrator)
        
        Args:
            companies: List of company dicts from database
        """
        self.companies = companies
        logger.info(f"Configured {len(companies)} Ashby companies")

    def _get_default_headers(self) -> dict:
        """Get default headers for API requests"""
        return {
            "Accept": "application/json",
            "User-Agent": "JobIngestionBot/1.0",
        }

    async def fetch_job_details(self, job_id: str) -> Optional[JobListing]:
        """
        Fetch detailed information for a specific job
        
        Args:
            job_id: The job identifier
            
        Returns:
            JobListing object or None
        """
        # For public API, we already get full details in fetch_jobs
        logger.warning(f"fetch_job_details not needed for Ashby public API")
        return None

    async def fetch_jobs(
        self, client_name: Optional[str] = None, limit: Optional[int] = None
    ) -> List[JobListing]:
        """
        Fetch jobs from Ashby's public API
        
        Args:
            client_name: Specific company client name to fetch from (optional)
            limit: Maximum number of jobs to fetch per company
            
        Returns:
            List of JobListing objects
        """
        all_jobs = []
        
        # If specific company requested
        if client_name:
            companies_to_fetch = [{"company_id": client_name}]
        else:
            companies_to_fetch = self.companies
        
        async with AsyncClient() as client:
            for company in companies_to_fetch:
                try:
                    client_name = company["company_id"]
                    display_name = company.get("display_name", client_name)
                    
                    logger.info(f"Fetching jobs from Ashby for {display_name}")
                    
                    # Apply rate limiting
                    await self.rate_limiter.acquire()
                    
                    # Ashby public API endpoint
                    url = f"{self.base_url}/{client_name}"
                    params = {"includeCompensation": "true"}
                    
                    response = await client.get(
                        url,
                        params=params,
                        timeout=30.0,
                        follow_redirects=True,
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        jobs_data = data.get("jobs", [])
                        
                        # Parse each job
                        for job_data in jobs_data[:limit] if limit else jobs_data:
                            job = self._parse_job(job_data, display_name)
                            if job:
                                all_jobs.append(job)
                        
                        # Log differently based on whether jobs were found
                        if len(jobs_data) == 0:
                            logger.info(
                                f"No open positions at {display_name} (valid endpoint)"
                            )
                        else:
                            logger.info(
                                f"Fetched {len(jobs_data)} jobs from {display_name}"
                            )
                    elif response.status_code == 404:
                        logger.error(
                            f"Company {display_name} not found on Ashby (404) - may need different client name or doesn't use Ashby"
                        )
                        # Don't raise exception, just skip this company  
                    else:
                        logger.warning(
                            f"Unexpected status from {display_name}: {response.status_code}"
                        )
                        
                except Exception as e:
                    logger.error(f"Error fetching from {client_name}: {e}")
                    continue
        
        logger.info(f"Total jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _parse_job(self, job_data: dict, company_name: str) -> Optional[JobListing]:
        """
        Parse Ashby job data into JobListing
        
        Args:
            job_data: Raw job data from Ashby API
            company_name: Company display name
            
        Returns:
            JobListing object or None if parsing fails
        """
        try:
            # Extract location
            location = "Remote"
            if job_data.get("location"):
                location = job_data["location"]
            elif job_data.get("locations") and len(job_data["locations"]) > 0:
                # Combine multiple locations
                locations = [loc.get("locationName", "") for loc in job_data["locations"]]
                location = ", ".join(filter(None, locations))
            
            # Parse employment type
            employment_type = None
            if job_data.get("employmentType"):
                employment_type = job_data["employmentType"]
            
            # Parse seniority from title or level
            seniority = None
            title = job_data.get("title", "")
            if "Senior" in title or "Sr" in title:
                seniority = "senior"
            elif "Staff" in title or "Principal" in title:
                seniority = "staff"
            elif "Lead" in title or "Manager" in title:
                seniority = "lead"
            elif "Junior" in title or "Jr" in title:
                seniority = "junior"
            elif "Intern" in title:
                seniority = "intern"
            
            # Extract department/team
            department = job_data.get("team")
            
            # Parse compensation if available
            salary_min = None
            salary_max = None
            currency = None
            if job_data.get("compensation"):
                comp = job_data["compensation"]
                if comp.get("compensationTiers") and len(comp["compensationTiers"]) > 0:
                    tier = comp["compensationTiers"][0]
                    salary_min = tier.get("min")
                    salary_max = tier.get("max")
                    currency = comp.get("currency", "USD")
            
            # Parse posted date - try multiple fields
            posted_at = None
            date_fields = ["publishedDate", "publishedAt", "createdAt", "updatedAt"]
            for field in date_fields:
                if job_data.get(field):
                    try:
                        # Ashby uses ISO format
                        posted_at = datetime.fromisoformat(
                            job_data[field].replace("Z", "+00:00")
                        )
                        break
                    except:
                        logger.debug(f"Could not parse date from {field}: {job_data.get(field)}")
            
            # Build description from various fields
            description_parts = []
            if job_data.get("description"):
                description_parts.append(job_data["description"])
            if job_data.get("descriptionHtml"):
                # Could strip HTML here if needed
                description_parts.append(job_data["descriptionHtml"])
            
            # Get application URL
            application_url = job_data.get("applicationUrl") or job_data.get("jobUrl")
            if not application_url and job_data.get("id"):
                # Construct URL if not provided
                application_url = f"https://jobs.ashbyhq.com/{company_name}/{job_data['id']}"
            
            return JobListing(
                external_id=job_data["id"],
                title=title,
                company_name=company_name,
                location=location,
                department=department,
                posted_at=posted_at,
                application_url=application_url,
                description="\n\n".join(description_parts) if description_parts else None,
                employment_type=employment_type,
                experience_level=seniority,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                source_ats="ashby",
                raw_data=job_data,
            )
        except Exception as e:
            logger.error(f"Error parsing Ashby job: {e}")
            return None