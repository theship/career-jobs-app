"""
Base ATS Connector class for job ingestion
Provides common interface and utilities for all ATS integrations
"""

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import httpx
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)


class JobListing(BaseModel):
    """Standardized job listing model across all ATS systems"""
    
    # Required fields
    external_id: str = Field(..., description="ATS-specific job ID")
    title: str = Field(..., description="Job title")
    company_name: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location (city, state, country)")
    posted_at: datetime = Field(..., description="When the job was posted")
    
    # Optional fields
    department: Optional[str] = Field(None, description="Department or team")
    description: Optional[str] = Field(None, description="Full job description")
    requirements: Optional[List[str]] = Field(default_factory=list, description="Job requirements")
    responsibilities: Optional[List[str]] = Field(default_factory=list, description="Job responsibilities")
    skills: Optional[List[str]] = Field(default_factory=list, description="Required/preferred skills")
    
    # Compensation and benefits
    salary_min: Optional[float] = Field(None, description="Minimum salary")
    salary_max: Optional[float] = Field(None, description="Maximum salary")
    salary_currency: Optional[str] = Field("USD", description="Salary currency")
    benefits: Optional[List[str]] = Field(default_factory=list, description="Benefits offered")
    
    # Application details
    application_url: Optional[HttpUrl] = Field(None, description="URL to apply")
    application_deadline: Optional[datetime] = Field(None, description="Application deadline")
    
    # Employment details
    employment_type: Optional[str] = Field(None, description="Full-time, Part-time, Contract, etc.")
    remote_type: Optional[str] = Field(None, description="Remote, Hybrid, On-site")
    experience_level: Optional[str] = Field(None, description="Entry, Mid, Senior, etc.")
    
    # Metadata
    raw_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Original ATS data")
    source_ats: str = Field(..., description="Source ATS system")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def generate_hash(self) -> str:
        """Generate a hash for change detection"""
        # Hash key fields that indicate a job has changed
        hash_data = {
            "title": self.title,
            "description": self.description,
            "requirements": self.requirements,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
        }
        hash_str = json.dumps(hash_data, sort_keys=True, default=str)
        return hashlib.sha256(hash_str.encode()).hexdigest()


class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_call_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
            
            self.last_call_time = asyncio.get_event_loop().time()


class ATSConnector(ABC):
    """Abstract base class for ATS connectors"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        rate_limit: float = 1.0,
        timeout: int = 30,
    ):
        """
        Initialize ATS connector
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for the ATS API
            rate_limit: Maximum API calls per second
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None
        self._processed_jobs: Set[str] = set()
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers=self._get_default_headers(),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.aclose()
    
    @abstractmethod
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for API requests"""
        pass
    
    @abstractmethod
    async def fetch_jobs(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        **filters
    ) -> List[JobListing]:
        """
        Fetch jobs from the ATS
        
        Args:
            limit: Maximum number of jobs to fetch
            offset: Pagination offset
            **filters: ATS-specific filters (department, location, etc.)
        
        Returns:
            List of standardized job listings
        """
        pass
    
    @abstractmethod
    async def fetch_job_details(self, job_id: str) -> JobListing:
        """
        Fetch detailed information for a specific job
        
        Args:
            job_id: ATS-specific job ID
        
        Returns:
            Detailed job listing
        """
        pass
    
    @abstractmethod
    def _parse_job(self, raw_job: Dict[str, Any]) -> JobListing:
        """
        Parse raw ATS job data into standardized format
        
        Args:
            raw_job: Raw job data from ATS API
        
        Returns:
            Standardized job listing
        """
        pass
    
    async def fetch_all_jobs(
        self,
        batch_size: int = 50,
        max_jobs: Optional[int] = None,
        **filters
    ) -> List[JobListing]:
        """
        Fetch all available jobs with pagination
        
        Args:
            batch_size: Number of jobs per batch
            max_jobs: Maximum total jobs to fetch
            **filters: ATS-specific filters
        
        Returns:
            All fetched job listings
        """
        all_jobs = []
        offset = 0
        
        while True:
            # Calculate batch limit
            remaining = max_jobs - len(all_jobs) if max_jobs else batch_size
            batch_limit = min(batch_size, remaining)
            
            # Fetch batch
            batch = await self.fetch_jobs(
                limit=batch_limit,
                offset=offset,
                **filters
            )
            
            if not batch:
                break
            
            all_jobs.extend(batch)
            
            # Check if we've reached the maximum
            if max_jobs and len(all_jobs) >= max_jobs:
                break
            
            # Check if we've fetched all available jobs
            if len(batch) < batch_limit:
                break
            
            offset += batch_size
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        logger.info(f"Fetched {len(all_jobs)} jobs from {self.__class__.__name__}")
        return all_jobs
    
    async def fetch_new_jobs(
        self,
        since: Optional[datetime] = None,
        **filters
    ) -> List[JobListing]:
        """
        Fetch only new jobs since a given date
        
        Args:
            since: Fetch jobs posted after this date
            **filters: Additional filters
        
        Returns:
            List of new job listings
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=7)
        
        all_jobs = await self.fetch_all_jobs(**filters)
        
        new_jobs = [
            job for job in all_jobs
            if job.posted_at > since and job.external_id not in self._processed_jobs
        ]
        
        # Mark jobs as processed
        for job in new_jobs:
            self._processed_jobs.add(job.external_id)
        
        logger.info(f"Found {len(new_jobs)} new jobs since {since}")
        return new_jobs
    
    async def test_connection(self) -> bool:
        """
        Test the connection to the ATS API
        
        Returns:
            True if connection is successful
        """
        try:
            # Try fetching a small batch
            jobs = await self.fetch_jobs(limit=1)
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an API request with rate limiting and error handling
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base_url)
            **kwargs: Additional request parameters
        
        Returns:
            JSON response data
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise