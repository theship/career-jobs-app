"""
Lever ATS Connector
Documentation: https://hire.lever.co/developer/documentation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import ATSConnector, JobListing

logger = logging.getLogger(__name__)


class LeverConnector(ATSConnector):
    """Connector for Lever ATS"""
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Lever connector
        
        Args:
            api_key: Lever API key
            **kwargs: Additional arguments for base class
        """
        base_url = "https://api.lever.co/v1"
        super().__init__(api_key, base_url, **kwargs)
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for Lever API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def fetch_jobs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        state: str = "published",
        **filters
    ) -> List[JobListing]:
        """
        Fetch jobs from Lever
        
        Args:
            limit: Maximum number of jobs to fetch
            offset: Pagination offset
            state: Job state (published, internal, closed)
            **filters: Additional filters (team, location, commitment)
        
        Returns:
            List of job listings
        """
        params = {
            "limit": limit or 50,
            "offset": offset,
            "state": state,
            "mode": "json",  # Return JSON instead of HTML
        }
        
        # Add optional filters
        if "team" in filters:
            params["team"] = filters["team"]
        if "location" in filters:
            params["location"] = filters["location"]
        if "commitment" in filters:
            params["commitment"] = filters["commitment"]
        if "department" in filters:
            params["department"] = filters["department"]
        
        response = await self._make_request("GET", "/postings", params=params)
        
        jobs = []
        for raw_job in response.get("data", []):
            try:
                job = self._parse_job(raw_job)
                jobs.append(job)
            except Exception as e:
                logger.error(f"Failed to parse job {raw_job.get('id')}: {e}")
                continue
        
        return jobs
    
    async def fetch_job_details(self, job_id: str) -> JobListing:
        """
        Fetch detailed information for a specific job
        
        Args:
            job_id: Lever job ID
        
        Returns:
            Detailed job listing
        """
        response = await self._make_request("GET", f"/postings/{job_id}")
        return self._parse_job(response)
    
    def _parse_job(self, raw_job: Dict[str, Any]) -> JobListing:
        """
        Parse Lever job data into standardized format
        
        Args:
            raw_job: Raw job data from Lever API
        
        Returns:
            Standardized job listing
        """
        # Extract basic information
        job_id = raw_job["id"]
        title = raw_job["text"]
        
        # Extract location
        location = raw_job.get("categories", {}).get("location", "Remote")
        if isinstance(location, list):
            location = ", ".join(location) if location else "Remote"
        
        # Extract team/department
        team = raw_job.get("categories", {}).get("team")
        department = raw_job.get("categories", {}).get("department", team)
        
        # Parse dates
        posted_at = self._parse_timestamp(raw_job.get("createdAt"))
        updated_at = self._parse_timestamp(raw_job.get("updatedAt"))
        
        # Extract employment details
        commitment = raw_job.get("categories", {}).get("commitment", "Full-time")
        level = raw_job.get("categories", {}).get("level", "")
        
        # Parse job content
        content = raw_job.get("content", {})
        description = content.get("description", "")
        
        # Extract lists from content
        lists = content.get("lists", [])
        requirements = []
        responsibilities = []
        benefits = []
        
        for list_item in lists:
            list_title = list_item.get("text", "").lower()
            list_content = list_item.get("content", [])
            
            if "requirement" in list_title or "qualification" in list_title:
                requirements.extend(list_content)
            elif "responsibilit" in list_title or "duties" in list_title:
                responsibilities.extend(list_content)
            elif "benefit" in list_title or "perk" in list_title:
                benefits.extend(list_content)
        
        # Build application URL
        application_url = raw_job.get("hostedUrl") or raw_job.get("applyUrl")
        
        # Determine remote type
        remote_type = self._determine_remote_type(location, commitment)
        
        # Extract salary info (often in additional field)
        salary_info = raw_job.get("salaryRange", {})
        salary_min = salary_info.get("min")
        salary_max = salary_info.get("max")
        salary_currency = salary_info.get("currency", "USD")
        
        return JobListing(
            external_id=job_id,
            title=title,
            company_name=raw_job.get("company", "Unknown"),
            location=location,
            posted_at=posted_at or datetime.now(timezone.utc),
            department=department,
            description=description,
            requirements=requirements,
            responsibilities=responsibilities,
            skills=self._extract_skills_from_lists(requirements + responsibilities),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            benefits=benefits,
            application_url=application_url,
            employment_type=commitment,
            experience_level=level,
            remote_type=remote_type,
            raw_data=raw_job,
            source_ats="lever",
        )
    
    def _parse_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Parse Lever timestamp (milliseconds since epoch)"""
        if not timestamp:
            return None
        try:
            # Lever uses milliseconds since epoch
            return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp {timestamp}: {e}")
            return None
    
    def _determine_remote_type(self, location: str, commitment: str) -> str:
        """Determine if job is remote, hybrid, or on-site"""
        location_lower = location.lower()
        commitment_lower = commitment.lower() if commitment else ""
        
        if "remote" in location_lower or "remote" in commitment_lower:
            return "Remote"
        elif "hybrid" in location_lower or "hybrid" in commitment_lower:
            return "Hybrid"
        elif "distributed" in location_lower:
            return "Remote"
        else:
            return "On-site"
    
    def _extract_skills_from_lists(self, items: List[str]) -> List[str]:
        """Extract potential skills from requirement/responsibility lists"""
        skills = []
        
        # Common skill keywords to look for
        skill_keywords = [
            "python", "javascript", "java", "react", "angular", "vue",
            "node", "django", "flask", "fastapi", "sql", "nosql",
            "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd",
            "git", "agile", "scrum", "rest", "api", "microservices",
            "machine learning", "data science", "tensorflow", "pytorch"
        ]
        
        for item in items:
            item_lower = item.lower() if isinstance(item, str) else ""
            for keyword in skill_keywords:
                if keyword in item_lower and keyword not in skills:
                    # Capitalize properly
                    proper_name = keyword
                    if keyword == "sql":
                        proper_name = "SQL"
                    elif keyword == "nosql":
                        proper_name = "NoSQL"
                    elif keyword == "api":
                        proper_name = "API"
                    elif keyword == "aws":
                        proper_name = "AWS"
                    elif keyword == "gcp":
                        proper_name = "GCP"
                    elif keyword == "ci/cd":
                        proper_name = "CI/CD"
                    else:
                        proper_name = keyword.title()
                    
                    skills.append(proper_name)
        
        return skills[:20]  # Limit to top 20 skills
    
    async def fetch_teams(self) -> List[str]:
        """Fetch all teams from Lever"""
        response = await self._make_request("GET", "/postings", params={"group": "team"})
        teams = []
        for group in response.get("data", []):
            if group.get("title"):
                teams.append(group["title"])
        return teams
    
    async def fetch_locations(self) -> List[str]:
        """Fetch all locations from Lever"""
        response = await self._make_request("GET", "/postings", params={"group": "location"})
        locations = []
        for group in response.get("data", []):
            if group.get("title"):
                locations.append(group["title"])
        return locations
    
    async def fetch_commitments(self) -> List[str]:
        """Fetch all commitment types (Full-time, Part-time, etc.)"""
        response = await self._make_request("GET", "/postings", params={"group": "commitment"})
        commitments = []
        for group in response.get("data", []):
            if group.get("title"):
                commitments.append(group["title"])
        return commitments