"""
Tests for Job Ingestion System (Phase 3)
Tests for ATS connectors, normalization, and orchestration
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ingestion.connectors.base import JobListing
from ingestion.connectors.greenhouse import GreenhouseConnector
from ingestion.connectors.lever import LeverConnector
from ingestion.normalizers.normalizer import JobNormalizer
from ingestion.orchestrator import JobIngestionOrchestrator


class TestJobNormalizer:
    """Test job normalization functionality"""

    def test_normalize_title(self):
        """Test job title normalization"""
        normalizer = JobNormalizer()

        # Test abbreviation expansion
        assert (
            normalizer.normalize_title("Sr Software Eng") == "Senior Software Engineer"
        )
        assert normalizer.normalize_title("Jr Dev") == "Junior Developer"
        assert (
            normalizer.normalize_title("VP of Engineering")
            == "Vice President of Engineering"
        )

        # Test cleaning
        assert (
            normalizer.normalize_title("  Software   Engineer  ") == "Software Engineer"
        )
        assert normalizer.normalize_title("Software@Engineer#") == "SoftwareEngineer"

    def test_normalize_experience_level(self):
        """Test experience level normalization"""
        normalizer = JobNormalizer()

        assert normalizer.normalize_experience_level("senior") == "Senior"
        assert normalizer.normalize_experience_level("jr") == "Entry"
        assert normalizer.normalize_experience_level("mid-level") == "Mid"
        assert normalizer.normalize_experience_level("10+ years") == "Staff"
        assert normalizer.normalize_experience_level("director") == "Executive"
        assert normalizer.normalize_experience_level("") == "Not Specified"

    def test_infer_experience_from_title(self):
        """Test inferring experience level from job title"""
        normalizer = JobNormalizer()

        assert normalizer.infer_experience_level("Senior Software Engineer") == "Senior"
        assert normalizer.infer_experience_level("Junior Developer") == "Entry"
        assert normalizer.infer_experience_level("Staff Engineer") == "Staff"
        assert normalizer.infer_experience_level("VP Engineering") == "Executive"
        assert normalizer.infer_experience_level("Software Engineer") == "Mid"

    def test_normalize_employment_type(self):
        """Test employment type normalization"""
        normalizer = JobNormalizer()

        assert normalizer.normalize_employment_type("full-time") == "Full Time"
        assert normalizer.normalize_employment_type("FT") == "Full Time"
        assert normalizer.normalize_employment_type("contract") == "Contract"
        assert normalizer.normalize_employment_type("intern") == "Internship"
        assert normalizer.normalize_employment_type("") == "Full Time"

    def test_normalize_remote_type(self):
        """Test remote type normalization"""
        normalizer = JobNormalizer()

        assert normalizer.normalize_remote_type("remote") == "Remote"
        assert normalizer.normalize_remote_type("wfh") == "Remote"
        assert normalizer.normalize_remote_type("hybrid") == "Hybrid"
        assert normalizer.normalize_remote_type("on-site") == "On Site"
        assert normalizer.normalize_remote_type("") == "Not Specified"

    def test_extract_skills(self):
        """Test skill extraction from job description"""
        normalizer = JobNormalizer()

        job = JobListing(
            external_id="test-1",
            title="Software Engineer",
            company_name="Test Co",
            location="Remote",
            posted_at=datetime.now(timezone.utc),
            description="Looking for Python and JavaScript developer with React experience",
            requirements=[
                "5 years Python",
                "Experience with Docker and Kubernetes",
            ],
            source_ats="test",
        )

        normalized = normalizer.normalize(job)

        assert "Python" in normalized.skills
        assert "JavaScript" in normalized.skills
        assert "React" in normalized.skills
        assert "Docker" in normalized.skills
        assert "Kubernetes" in normalized.skills

    def test_normalize_salary(self):
        """Test salary normalization"""
        normalizer = JobNormalizer()

        # Test swapping reversed min/max
        job = JobListing(
            external_id="test-1",
            title="Engineer",
            company_name="Test",
            location="Remote",
            posted_at=datetime.now(timezone.utc),
            salary_min=150000,
            salary_max=100000,
            source_ats="test",
        )
        normalized = normalizer.normalize(job)
        assert normalized.salary_min == 100000
        assert normalized.salary_max == 150000

        # Test removing unrealistic salaries
        job.salary_max = 10000000  # 10 million
        job.salary_min = 5000  # 5k
        normalized = normalizer.normalize(job)
        assert normalized.salary_max is None
        assert normalized.salary_min is None

    def test_clean_skills(self):
        """Test skill list cleaning and deduplication"""
        normalizer = JobNormalizer()

        skills = [
            "python",
            "Python",
            "PYTHON",
            "javascript",
            "JavaScript",
            "",
            None,
            "React",
        ]
        cleaned = normalizer.clean_skills(skills)

        assert len(cleaned) == 3  # Python, JavaScript, React (deduplicated)
        assert "Python" in cleaned
        assert "JavaScript" in cleaned
        assert "React" in cleaned


class TestGreenhouseConnector:
    """Test Greenhouse ATS connector"""

    @pytest.mark.asyncio
    async def test_fetch_jobs(self):
        """Test fetching jobs from Greenhouse API"""
        connector = GreenhouseConnector("test-api-key")

        # Mock the API response
        mock_response = {
            "jobs": [
                {
                    "id": 123,
                    "title": "Software Engineer",
                    "location": {"name": "San Francisco, CA"},
                    "departments": [{"name": "Engineering"}],
                    "updated_at": "2025-01-15T10:00:00Z",
                    "absolute_url": "https://boards.greenhouse.io/company/jobs/123",
                }
            ]
        }

        with patch.object(
            connector,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            jobs = await connector.fetch_jobs(limit=10)

            assert len(jobs) == 1
            assert jobs[0].external_id == "123"
            assert jobs[0].title == "Software Engineer"
            assert jobs[0].location == "San Francisco, CA"
            assert jobs[0].department == "Engineering"

    @pytest.mark.asyncio
    async def test_parse_job(self):
        """Test parsing Greenhouse job data"""
        connector = GreenhouseConnector("test-api-key")

        raw_job = {
            "id": 456,
            "title": "Senior Backend Engineer",
            "location": {"name": "Remote"},
            "departments": [{"name": "Backend"}],
            "offices": [{"name": "HQ"}],
            "updated_at": "2025-01-20T15:30:00Z",
            "created_at": "2025-01-10T10:00:00Z",
            "content": "<p>We are looking for a senior backend engineer...</p>",
            "absolute_url": "https://boards.greenhouse.io/company/jobs/456",
        }

        job = connector._parse_job(raw_job)

        assert job.external_id == "456"
        assert job.title == "Senior Backend Engineer"
        assert job.location == "Remote"
        assert job.department == "Backend"
        assert "senior backend engineer" in job.description.lower()
        assert job.source_ats == "greenhouse"


class TestLeverConnector:
    """Test Lever ATS connector"""

    @pytest.mark.asyncio
    async def test_fetch_jobs(self):
        """Test fetching jobs from Lever API"""
        connector = LeverConnector("test-api-key")

        # Mock the API response
        mock_response = {
            "data": [
                {
                    "id": "abc-123",
                    "text": "Full Stack Developer",
                    "categories": {
                        "location": "New York, NY",
                        "team": "Product",
                        "commitment": "Full-time",
                    },
                    "createdAt": 1705315200000,  # milliseconds since epoch
                    "hostedUrl": "https://jobs.lever.co/company/abc-123",
                }
            ]
        }

        with patch.object(
            connector,
            "_make_request",
            new=AsyncMock(return_value=mock_response),
        ):
            jobs = await connector.fetch_jobs(limit=10)

            assert len(jobs) == 1
            assert jobs[0].external_id == "abc-123"
            assert jobs[0].title == "Full Stack Developer"
            assert jobs[0].location == "New York, NY"
            assert jobs[0].employment_type == "Full-time"

    def test_determine_remote_type(self):
        """Test determining remote type from Lever data"""
        connector = LeverConnector("test-api-key")

        assert connector._determine_remote_type("Remote", "") == "Remote"
        assert connector._determine_remote_type("San Francisco", "Hybrid") == "Hybrid"
        assert connector._determine_remote_type("Office - NYC", "") == "On-site"
        assert connector._determine_remote_type("Distributed team", "") == "Remote"

    def test_extract_skills_from_lists(self):
        """Test extracting skills from Lever job lists"""
        connector = LeverConnector("test-api-key")

        items = [
            "5+ years experience with Python and Django",
            "Strong knowledge of JavaScript and React",
            "Experience with AWS and Docker",
            "Agile development methodology",
        ]

        skills = connector._extract_skills_from_lists(items)

        assert "Python" in skills
        assert "Django" in skills
        assert "JavaScript" in skills
        assert "React" in skills
        assert "AWS" in skills
        assert "Docker" in skills
        assert "Agile" in skills


class TestJobIngestionOrchestrator:
    """Test job ingestion orchestration"""

    @pytest.mark.asyncio
    async def test_ingest_from_source(self):
        """Test ingesting from a single source"""
        orchestrator = JobIngestionOrchestrator()

        # Create mock connector
        mock_connector = Mock(spec=GreenhouseConnector)
        mock_jobs = [
            JobListing(
                external_id="job-1",
                title="Software Engineer",
                company_name="Test Co",
                location="Remote",
                posted_at=datetime.now(timezone.utc),
                source_ats="greenhouse",
            )
        ]
        mock_connector.fetch_jobs = AsyncMock(return_value=mock_jobs)

        # Mock Supabase
        with patch.object(orchestrator, "supabase") as mock_supabase:
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
                []
            )
            mock_table.insert.return_value.execute.return_value.data = [
                {"job_id": "new-job-id"}
            ]

            jobs = await orchestrator.ingest_from_source(
                mock_connector,
                "greenhouse",
                limit=10,
                normalize=True,
                store=True,
            )

            assert len(jobs) == 1
            assert jobs[0].title == "Software Engineer"
            mock_connector.fetch_jobs.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_deduplicate_jobs(self):
        """Test job deduplication"""
        orchestrator = JobIngestionOrchestrator()

        # Mock Supabase with duplicate jobs
        with patch.object(orchestrator, "supabase") as mock_supabase:
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table

            # Mock jobs with duplicates
            mock_jobs = [
                {
                    "job_id": "1",
                    "title": "Engineer",
                    "company_name": "Company A",
                    "location": "NYC",
                },
                {
                    "job_id": "2",
                    "title": "Engineer",
                    "company_name": "Company A",
                    "location": "NYC",
                },  # Duplicate
                {
                    "job_id": "3",
                    "title": "Developer",
                    "company_name": "Company B",
                    "location": "Remote",
                },
            ]
            mock_table.select.return_value.execute.return_value.data = mock_jobs
            mock_table.delete.return_value.eq.return_value.execute.return_value = Mock()

            duplicates_removed = await orchestrator.deduplicate_jobs()

            assert duplicates_removed == 1
            # Verify delete was called for duplicate
            mock_table.delete.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_jobs(self):
        """Test cleaning up expired jobs"""
        orchestrator = JobIngestionOrchestrator()

        # Current implementation is a placeholder that returns 0
        cleaned = await orchestrator.cleanup_expired_jobs()

        assert cleaned == 0  # Placeholder implementation

    @pytest.mark.asyncio
    async def test_update_job_embeddings(self):
        """Test updating job embeddings"""
        orchestrator = JobIngestionOrchestrator()

        with patch.object(orchestrator, "supabase") as mock_supabase:
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table

            # Mock jobs without embeddings
            mock_jobs = [
                {
                    "job_id": "1",
                    "title": "Engineer",
                    "description_text": "Build software",
                    "requirements_text": "Python required",
                },
                {
                    "job_id": "2",
                    "title": "Designer",
                    "description_text": "Create designs",
                    "requirements_text": "Figma required",
                },
            ]
            mock_table.select.return_value.is_.return_value.limit.return_value.execute.return_value.data = (
                mock_jobs
            )
            mock_table.update.return_value.eq.return_value.execute.return_value = Mock()

            updated = await orchestrator.update_job_embeddings(batch_size=2)

            assert updated == 2
            assert mock_table.update.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
