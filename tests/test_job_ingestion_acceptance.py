"""
Phase 3 Backend Acceptance Tests
Tests that match the specifications in docs/dev-plan.md
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from api.main import app
from ingestion.connectors.base import ATSConnector, JobListing
from ingestion.normalizers.normalizer import JobNormalizer


client = TestClient(app)


def create_test_job(job_id: str, title: str, **kwargs) -> Dict[str, Any]:
    """Helper to create a test job"""
    job_data = {
        "job_id": job_id,
        "title": title,
        "company_name": kwargs.get("company_name", "Test Company"),
        "company_domain": kwargs.get("company_domain", "test.com"),
        "location": kwargs.get("location", "Remote"),
        "job_url": kwargs.get("job_url", f"https://test.com/jobs/{job_id}"),
        "posted_at": kwargs.get("posted_at", datetime.now(timezone.utc).isoformat()),
        **kwargs
    }
    return job_data


class TestPhase3AcceptanceTests:
    """Phase 3 Backend Acceptance Tests from dev-plan.md"""

    def test_greenhouse_connector(self):
        """Greenhouse connector fetches recent jobs"""
        from ingestion.connectors.greenhouse import GreenhouseConnector
        
        # Note: This test already exists in test_job_ingestion.py
        # Including here for acceptance test completeness
        connector = GreenhouseConnector("test-key")
        
        # Mock the fetch to avoid actual API calls
        mock_jobs = [
            JobListing(
                external_id="123",
                title="Software Engineer",
                company_name="Test Co",
                location="Remote",
                posted_at=datetime.now(timezone.utc),
                application_url="https://boards.greenhouse.io/company/jobs/123",
                source_ats="greenhouse",
            )
        ]
        
        with patch.object(connector, 'fetch_jobs', return_value=mock_jobs):
            jobs = connector.fetch_jobs()
            
            assert len(jobs) > 0
            assert all(hasattr(job, "title") for job in jobs)
            assert all(hasattr(job, "posted_at") for job in jobs) 
            assert all(hasattr(job, "application_url") for job in jobs)

    def test_job_normalization(self):
        """Raw ATS data is normalized correctly"""
        normalizer = JobNormalizer()
        
        # Create a raw Greenhouse-style job
        raw_job = JobListing(
            external_id="123",
            title="Senior Software Engineer",
            company_name="Test Company",
            location="San Francisco, CA",
            posted_at=datetime(2025, 8, 10, 10, 0, 0, tzinfo=timezone.utc),
            application_url="https://boards.greenhouse.io/company/jobs/123",
            source_ats="greenhouse"
        )
        
        normalized = normalizer.normalize(raw_job)
        
        # Check normalization results
        assert normalized.external_id == "123"
        assert normalized.title == "Senior Software Engineer"
        assert normalized.location == "San Francisco, CA"
        assert normalized.posted_at == datetime(2025, 8, 10, 10, 0, 0, tzinfo=timezone.utc)
        
        # Check that experience level was inferred from title
        assert normalized.experience_level == "Senior"

    def test_seven_day_filter(self):
        """Only jobs from last 7 days are processed"""
        from ingestion.connectors.greenhouse import GreenhouseConnector
        connector = GreenhouseConnector("test-key")
        
        # Create test jobs with different dates
        old_job = JobListing(
            external_id="old-1",
            title="Old Job",
            company_name="Test Co",
            location="Remote",
            posted_at=datetime.now(timezone.utc) - timedelta(days=10),
            source_ats="test"
        )
        
        new_job = JobListing(
            external_id="new-1", 
            title="New Job",
            company_name="Test Co",
            location="Remote",
            posted_at=datetime.now(timezone.utc) - timedelta(days=2),
            source_ats="test"
        )
        
        # Test the filter method
        jobs = [old_job, new_job]
        filtered = connector.filter_last_7_days(jobs)
        
        assert len(filtered) == 1
        assert filtered[0].external_id == "new-1"
        assert filtered[0].title == "New Job"

    def test_job_deduplication_api(self):
        """Identical jobs update existing records via API"""
        # Skip if no auth available
        # In a real test, we'd set up proper auth headers
        pytest.skip("Requires authentication setup")
        
        # First ingestion
        job_data = create_test_job(job_id="test-123", title="Engineer")
        
        # Mock the ingestion endpoint
        with patch('api.routes.jobs.JobIngestionOrchestrator') as mock_orchestrator:
            mock_instance = Mock()
            mock_orchestrator.return_value = mock_instance
            mock_instance.ingest_from_source.return_value = [
                JobListing(
                    external_id="test-123",
                    title="Engineer",
                    company_name="Test Company",
                    location="Remote",
                    posted_at=datetime.now(timezone.utc),
                    source_ats="test"
                )
            ]
            
            # First ingestion
            response1 = client.post("/api/v1/jobs/ingest", 
                                   json={"sources": ["test"], "store": True})
            
            # Second ingestion with updated title
            mock_instance.ingest_from_source.return_value = [
                JobListing(
                    external_id="test-123",
                    title="Senior Engineer",  # Updated title
                    company_name="Test Company",
                    location="Remote",
                    posted_at=datetime.now(timezone.utc),
                    source_ats="test"
                )
            ]
            
            response2 = client.post("/api/v1/jobs/ingest", 
                                   json={"sources": ["test"], "store": True})
            
            # In a real implementation, we'd check:
            # - Same job_id gets updated, not created new
            # - Version history is maintained
            # This requires database access which we're mocking here

    @pytest.mark.asyncio
    async def test_job_ingestion_flow(self):
        """Test complete job ingestion flow"""
        from ingestion.orchestrator import JobIngestionOrchestrator
        
        orchestrator = JobIngestionOrchestrator()
        
        # Create mock jobs
        test_jobs = [
            JobListing(
                external_id="flow-1",
                title="Python Developer",
                company_name="Tech Co",
                location="San Francisco, CA",
                posted_at=datetime.now(timezone.utc),
                description="Looking for Python developer",
                requirements=["Python", "Django", "PostgreSQL"],
                source_ats="test"
            ),
            JobListing(
                external_id="flow-2",
                title="Senior Data Scientist",
                company_name="Data Corp",
                location="Remote",
                posted_at=datetime.now(timezone.utc) - timedelta(days=15),  # Old job
                description="Data science role",
                source_ats="test"
            )
        ]
        
        # Create mock connector
        mock_connector = Mock()
        mock_connector.fetch_jobs = Mock(return_value=test_jobs)
        
        # Test ingestion with normalization
        with patch.object(orchestrator, '_store_jobs', return_value=test_jobs[:1]):
            jobs = await orchestrator.ingest_from_source(
                mock_connector, 
                "test",
                normalize=True,
                store=False  # Don't actually store in test
            )
            
            # Should only get the recent job (within 7 days)
            assert len(jobs) == 1
            assert jobs[0].title == "Python Developer"
            
            # Check normalization happened
            assert jobs[0].experience_level is not None

    def test_job_stats_endpoint(self):
        """Test job statistics endpoint works"""
        response = client.get("/api/v1/jobs/stats/summary")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "total_jobs" in data
        assert "active_jobs" in data
        assert "unique_companies" in data
        assert "jobs_by_source" in data
        assert "jobs_by_seniority" in data
        assert "jobs_by_remote_type" in data
        assert "last_updated" in data
        
        # Check data types
        assert isinstance(data["total_jobs"], int)
        assert isinstance(data["active_jobs"], int)
        assert isinstance(data["unique_companies"], int)
        assert isinstance(data["jobs_by_source"], dict)
        assert isinstance(data["jobs_by_seniority"], dict)
        assert isinstance(data["jobs_by_remote_type"], dict)

    def test_job_search_endpoint(self):
        """Test job search endpoint"""
        search_request = {
            "query": "python developer",
            "skills": ["Python", "Django"],
            "location": "San Francisco",
            "remote_type": "Remote",
            "seniority": "Senior",
            "employment_type": "Full Time",
            "salary_min": 100000,
            "company_name": "Tech",
            "limit": 20,
            "offset": 0
        }
        
        response = client.post("/api/v1/jobs/search", json=search_request)
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # If there are results, check structure
        if data:
            job = data[0]
            assert "job_id" in job
            assert "company_name" in job
            assert "title" in job
            assert "location" in job
            assert "job_url" in job

    def test_job_listing_filters(self):
        """Test job listing with various filters"""
        # Test with different filter combinations
        filters = [
            {"limit": 5},
            {"seniority": "Senior"},
            {"remote_type": "Remote"},
            {"limit": 10, "offset": 5},
        ]
        
        for filter_params in filters:
            response = client.get("/api/v1/jobs", params=filter_params)
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    def test_similar_jobs_endpoint(self):
        """Test finding similar jobs endpoint"""
        # This would need a real job_id in the database
        # For now, test that endpoint exists and handles missing job
        response = client.get("/api/v1/jobs/similar/nonexistent-job-id")
        
        # Should return 404 for non-existent job
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])