"""
Public Lever Connector - No authentication required
Uses Lever's public posting API for job boards
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


class LeverPublicConnector(ATSConnector):
    """Connector for Lever's public job postings API (no auth required)"""

    def __init__(self, company_csv_path: str = "config/target_companies.csv"):
        """
        Initialize Lever public connector

        Args:
            company_csv_path: Path to CSV file containing target companies
        """
        # No API key needed for public endpoints
        super().__init__(
            api_key="public",  # Placeholder since parent requires it
            base_url="https://api.lever.co/v0/postings",
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
                if row["ats_system"] == "lever" and row["active"] == "true":
                    companies.append(row)
        
        logger.info(f"Loaded {len(companies)} Lever companies from {csv_path}")
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
        self, company_id: Optional[str] = None, limit: Optional[int] = None
    ) -> List[JobListing]:
        """
        Fetch jobs from Lever's public API

        Args:
            company_id: Specific company to fetch from (optional)
            limit: Maximum number of jobs to fetch per company

        Returns:
            List of JobListing objects
        """
        all_jobs = []
        
        # If specific company requested
        if company_id:
            companies_to_fetch = [{"company_id": company_id}]
        else:
            companies_to_fetch = self.companies
        
        async with AsyncClient() as client:
            for company in companies_to_fetch:
                try:
                    company_id = company["company_id"]
                    display_name = company.get("display_name", company_id)
                    
                    logger.info(f"Fetching jobs from Lever for {display_name}")
                    
                    # Apply rate limiting
                    await self.rate_limiter.acquire()
                    
                    # Lever public API endpoint
                    url = f"{self.base_url}/{company_id}"
                    params = {"mode": "json"}
                    
                    response = await client.get(
                        url,
                        params=params,
                        timeout=30.0,
                        follow_redirects=True,
                    )
                    
                    if response.status_code == 200:
                        jobs_data = response.json()
                        
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
                    logger.error(f"Error fetching from {company_id}: {e}")
                    continue
        
        # Filter to last 7 days (temporarily disabled to get some data)
        # recent_jobs = self.filter_last_7_days(all_jobs)
        # logger.info(f"Total jobs fetched: {len(recent_jobs)} (from last 7 days)")
        
        logger.info(f"Total jobs fetched: {len(all_jobs)}")
        return all_jobs

    def _parse_job(self, job_data: dict, company_name: str) -> Optional[JobListing]:
        """
        Parse Lever job data into JobListing

        Args:
            job_data: Raw job data from Lever API
            company_name: Company display name

        Returns:
            JobListing object or None if parsing fails
        """
        try:
            # Extract location
            location = "Remote"
            if job_data.get("categories", {}).get("location"):
                location = job_data["categories"]["location"]
            elif job_data.get("workplaceType"):
                location = job_data["workplaceType"]
            
            # Parse posted date
            posted_at = None
            if job_data.get("createdAt"):
                # Lever provides timestamp in milliseconds
                timestamp_ms = job_data["createdAt"]
                posted_at = datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=timezone.utc
                )
            
            # Build description
            description_parts = []
            if job_data.get("description"):
                description_parts.append(job_data["description"])
            if job_data.get("lists"):
                for list_item in job_data["lists"]:
                    if list_item.get("text"):
                        description_parts.append(list_item["text"])
            
            return JobListing(
                external_id=job_data["id"],
                title=job_data["text"],  # Lever uses 'text' for job title
                company_name=company_name,
                location=location,
                department=job_data.get("categories", {}).get("department"),
                posted_at=posted_at,
                application_url=job_data.get("hostedUrl") or job_data.get("applyUrl"),
                description="\n\n".join(description_parts) if description_parts else None,
                employment_type=job_data.get("categories", {}).get("commitment"),
                seniority=job_data.get("categories", {}).get("level"),
                source_ats="lever",
                raw_data=job_data,
            )
        except Exception as e:
            logger.error(f"Error parsing Lever job: {e}")
            return None