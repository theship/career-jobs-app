"""
Greenhouse ATS Connector
Documentation: https://developers.greenhouse.io/harvest.html
"""

import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import ATSConnector, JobListing

logger = logging.getLogger(__name__)


class GreenhouseConnector(ATSConnector):
    """Connector for Greenhouse ATS"""

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Greenhouse connector

        Args:
            api_key: Greenhouse Harvest API key
            **kwargs: Additional arguments for base class
        """
        base_url = "https://harvest.greenhouse.io/v1"
        super().__init__(api_key, base_url, **kwargs)

        # Greenhouse uses Basic Auth with API key as username
        self.auth_header = self._create_auth_header(api_key)

    def _create_auth_header(self, api_key: str) -> str:
        """Create Basic Auth header for Greenhouse"""
        # Greenhouse expects "API_KEY:" (with colon, no password)
        credentials = f"{api_key}:"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for Greenhouse API"""
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def fetch_jobs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        status: str = "open",
        **filters,
    ) -> List[JobListing]:
        """
        Fetch jobs from Greenhouse

        Args:
            limit: Maximum number of jobs to fetch
            offset: Pagination offset
            status: Job status (open, closed, draft)
            **filters: Additional filters (department_id, office_id, etc.)

        Returns:
            List of job listings
        """
        params = {
            "per_page": limit or 50,
            "page": (offset // (limit or 50)) + 1,
            "status": status,
        }

        # Add optional filters
        if "department_id" in filters:
            params["department_id"] = filters["department_id"]
        if "office_id" in filters:
            params["office_id"] = filters["office_id"]
        if "updated_after" in filters:
            params["updated_after"] = filters["updated_after"]

        response = await self._make_request("GET", "/jobs", params=params)

        jobs = []
        # Handle both direct array and wrapped response
        job_list = (
            response.get("jobs", response) if isinstance(response, dict) else response
        )

        for raw_job in job_list:
            try:
                job = self._parse_job(raw_job)
                jobs.append(job)
            except Exception as e:
                job_id = raw_job.get("id") if isinstance(raw_job, dict) else "unknown"
                logger.error(f"Failed to parse job {job_id}: {e}")
                continue

        return jobs

    async def fetch_job_details(self, job_id: str) -> JobListing:
        """
        Fetch detailed information for a specific job

        Args:
            job_id: Greenhouse job ID

        Returns:
            Detailed job listing
        """
        response = await self._make_request("GET", f"/jobs/{job_id}")
        return self._parse_job(response)

    def _parse_job(self, raw_job: Dict[str, Any]) -> JobListing:
        """
        Parse Greenhouse job data into standardized format

        Args:
            raw_job: Raw job data from Greenhouse API

        Returns:
            Standardized job listing
        """
        # Extract basic information
        job_id = str(raw_job["id"])
        title = raw_job.get("name") or raw_job.get("title", "Untitled")

        # Extract location from offices or location field
        location_parts = []

        # Check for location field first (common in API)
        if "location" in raw_job:
            if isinstance(raw_job["location"], dict):
                location = raw_job["location"].get("name", "Remote")
            else:
                location = raw_job["location"]
        # Otherwise check offices
        elif "offices" in raw_job and raw_job["offices"]:
            for office in raw_job["offices"]:
                if office.get("location"):
                    location_parts.append(office["location"].get("name", ""))
            location = ", ".join(filter(None, location_parts)) or "Remote"
        else:
            location = "Remote"

        # Extract department
        departments = raw_job.get("departments", [])
        department = departments[0]["name"] if departments else None

        # Parse posting date
        posted_at = self._parse_datetime(raw_job.get("created_at"))
        updated_at = self._parse_datetime(raw_job.get("updated_at"))

        # Extract custom fields and requirements
        custom_fields = raw_job.get("custom_fields", {})
        employment_type = custom_fields.get("employment_type")
        experience_level = custom_fields.get("experience_level")
        salary_min = custom_fields.get("salary_range_min")
        salary_max = custom_fields.get("salary_range_max")

        # Build application URL
        application_url = None
        if raw_job.get("absolute_url"):
            application_url = raw_job["absolute_url"]

        # Extract requirements and responsibilities from content
        content = raw_job.get("content", "")
        requirements = self._extract_list_from_html(content, "requirements")
        responsibilities = self._extract_list_from_html(content, "responsibilities")

        return JobListing(
            external_id=job_id,
            title=title,
            company_name=raw_job.get("company_name", "Unknown"),
            location=location,
            posted_at=posted_at or datetime.now(),
            department=department,
            description=content,
            requirements=requirements,
            responsibilities=responsibilities,
            skills=[],  # Would need additional parsing
            salary_min=salary_min,
            salary_max=salary_max,
            application_url=application_url,
            employment_type=employment_type,
            experience_level=experience_level,
            remote_type=self._determine_remote_type(location, raw_job),
            raw_data=raw_job,
            source_ats="greenhouse",
        )

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Greenhouse datetime string"""
        if not date_str:
            return None
        try:
            # Greenhouse uses ISO 8601 format
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Failed to parse date {date_str}: {e}")
            return None

    def _extract_list_from_html(self, html: str, section: str) -> List[str]:
        """Extract list items from HTML content"""
        # Simple extraction - would need proper HTML parsing in production
        items = []
        # This is a simplified version - in production use BeautifulSoup
        import re

        # Look for sections with headers
        pattern = rf"(?i)<h[23]>.*{section}.*</h[23]>(.*?)(?=<h[23]>|$)"
        match = re.search(pattern, html, re.DOTALL)

        if match:
            section_content = match.group(1)
            # Extract list items
            li_pattern = r"<li>(.*?)</li>"
            items = re.findall(li_pattern, section_content)
            # Clean HTML tags
            items = [re.sub(r"<.*?>", "", item).strip() for item in items]

        return items

    def _determine_remote_type(self, location: str, raw_job: Dict[str, Any]) -> str:
        """Determine if job is remote, hybrid, or on-site"""
        location_lower = location.lower()

        if "remote" in location_lower:
            return "Remote"
        elif "hybrid" in location_lower:
            return "Hybrid"
        else:
            # Check custom fields
            custom = raw_job.get("custom_fields", {})
            if custom.get("remote_option"):
                return custom["remote_option"]

        return "On-site"

    async def fetch_departments(self) -> List[Dict[str, Any]]:
        """Fetch all departments from Greenhouse"""
        response = await self._make_request("GET", "/departments")
        return response

    async def fetch_offices(self) -> List[Dict[str, Any]]:
        """Fetch all offices from Greenhouse"""
        response = await self._make_request("GET", "/offices")
        return response

    async def fetch_custom_fields(self) -> Dict[str, Any]:
        """Fetch custom field definitions"""
        response = await self._make_request("GET", "/custom_fields")
        return response
