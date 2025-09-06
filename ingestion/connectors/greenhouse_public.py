"""
Public Greenhouse Connector - No authentication required
Uses Greenhouse's public board API for job listings
"""

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from httpx import AsyncClient

from ingestion.connectors.base import ATSConnector, JobListing

logger = logging.getLogger(__name__)


class GreenhousePublicConnector(ATSConnector):
    """Connector for Greenhouse's public job board API (no auth required)"""

    def __init__(self, company_csv_path: str = "config/target_companies.csv"):
        """
        Initialize Greenhouse public connector

        Args:
            company_csv_path: Path to CSV file containing target companies
        """
        # No API key needed for public endpoints
        super().__init__(
            api_key="public",  # Placeholder since parent requires it
            base_url="https://boards-api.greenhouse.io/v1/boards",
            rate_limit=1.0,  # 1 request per second (60 per minute)
        )
        self.company_csv_path = company_csv_path
        self.companies = self._load_companies()

    def _load_companies(self) -> List[dict]:
        """Load target companies from CSV file"""
        companies = []
        csv_path = Path(self.company_csv_path)
        
        if not csv_path.exists():
            logger.warning(f"Company CSV not found at {csv_path}")
            return companies
            
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["ats_system"] == "greenhouse" and row["active"] == "true":
                    companies.append(row)
        
        logger.info(f"Loaded {len(companies)} Greenhouse companies from {csv_path}")
        return companies

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
        # This is a placeholder implementation
        logger.warning(f"fetch_job_details not implemented for public API")
        return None

    async def fetch_jobs(
        self, board_token: Optional[str] = None, limit: Optional[int] = None
    ) -> List[JobListing]:
        """
        Fetch jobs from Greenhouse's public API

        Args:
            board_token: Specific company board token to fetch from (optional)
            limit: Maximum number of jobs to fetch per company

        Returns:
            List of JobListing objects
        """
        all_jobs = []
        
        # If specific company requested
        if board_token:
            companies_to_fetch = [{"company_id": board_token}]
        else:
            companies_to_fetch = self.companies
        
        async with AsyncClient() as client:
            for company in companies_to_fetch:
                try:
                    board_token = company["company_id"]
                    display_name = company.get("display_name", board_token)
                    
                    logger.info(f"Fetching jobs from Greenhouse for {display_name}")
                    
                    # Apply rate limiting
                    await self.rate_limiter.acquire()
                    
                    # Greenhouse public API endpoint
                    url = f"{self.base_url}/{board_token}/jobs"
                    
                    response = await client.get(
                        url,
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
                        
                        logger.info(
                            f"Fetched {len(jobs_data)} jobs from {display_name}"
                        )
                    else:
                        logger.warning(
                            f"Failed to fetch from {display_name}: {response.status_code}"
                        )
                        
                except Exception as e:
                    logger.error(f"Error fetching from {board_token}: {e}")
                    continue
        
        # Filter to last 7 days (temporarily disabled to get some data)
        # recent_jobs = self.filter_last_7_days(all_jobs)
        # logger.info(f"Total jobs fetched: {len(recent_jobs)} (from last 7 days)")
        
        logger.info(f"Total jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _parse_job(self, job_data: dict, company_name: str) -> Optional[JobListing]:
        """
        Parse Greenhouse job data into JobListing

        Args:
            job_data: Raw job data from Greenhouse API
            company_name: Company display name

        Returns:
            JobListing object or None if parsing fails
        """
        try:
            # Extract location
            location = "Remote"
            if job_data.get("location", {}).get("name"):
                location = job_data["location"]["name"]
            elif job_data.get("offices"):
                # Combine office locations
                locations = [
                    office.get("name", "") 
                    for office in job_data.get("offices", [])
                    if office.get("name")
                ]
                if locations:
                    location = ", ".join(locations)
            
            # Parse posted date
            posted_at = None
            if job_data.get("updated_at"):
                # Parse ISO format date
                posted_at = datetime.fromisoformat(
                    job_data["updated_at"].replace("Z", "+00:00")
                )
            
            # Extract department
            department = None
            if job_data.get("departments"):
                departments = [
                    dept.get("name", "") 
                    for dept in job_data.get("departments", [])
                    if dept.get("name")
                ]
                if departments:
                    department = ", ".join(departments)
            
            # Build application URL
            application_url = job_data.get("absolute_url")
            if not application_url and job_data.get("id"):
                # Construct URL if not provided
                application_url = f"https://boards.greenhouse.io/{company_name.lower().replace(' ', '')}/jobs/{job_data['id']}"
            
            return JobListing(
                external_id=str(job_data["id"]),
                title=job_data["title"],
                company_name=company_name,
                location=location,
                department=department,
                posted_at=posted_at,
                application_url=application_url,
                description=job_data.get("content"),  # HTML content
                employment_type=None,  # Not always provided
                seniority=None,  # We could infer from title
                source_ats="greenhouse",
                raw_data=job_data,
            )
        except Exception as e:
            logger.error(f"Error parsing Greenhouse job: {e}")
            return None