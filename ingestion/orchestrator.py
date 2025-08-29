"""
Job Ingestion Orchestrator
Central coordinator for fetching, normalizing, and storing jobs from multiple ATS sources
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import uuid4

import openai

from api.utils.config import get_settings
from ingestion.connectors.base import ATSConnector, JobListing
from ingestion.connectors.greenhouse import GreenhouseConnector
from ingestion.connectors.lever import LeverConnector
from ingestion.normalizers.normalizer import JobNormalizer
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class JobIngestionOrchestrator:
    """Orchestrates job ingestion from multiple ATS sources"""

    def __init__(self):
        """Initialize orchestrator with connectors and services"""
        self.settings = get_settings()
        self.supabase: Client = create_client(
            self.settings.supabase_url, self.settings.supabase_anon_key
        )
        self.normalizer = JobNormalizer()
        self.connectors: Dict[str, ATSConnector] = {}

        # Initialize OpenAI client for embeddings
        if self.settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(
                api_key=self.settings.openai_api_key
            )
        else:
            self.openai_client = None
            logger.warning(
                "OpenAI API key not configured - embeddings will not be generated"
            )

        # Initialize configured connectors
        self._initialize_connectors()

    def _initialize_connectors(self):
        """Initialize ATS connectors based on configuration"""
        # TODO: Load from config file or environment variables
        # For now, initialize with example connectors

        # Example: Initialize Greenhouse if configured
        if (
            hasattr(self.settings, "greenhouse_api_key")
            and self.settings.greenhouse_api_key
        ):
            self.connectors["greenhouse"] = GreenhouseConnector(
                api_key=self.settings.greenhouse_api_key
            )
            logger.info("Initialized Greenhouse connector")

        # Example: Initialize Lever if configured
        if hasattr(self.settings, "lever_api_key") and self.settings.lever_api_key:
            self.connectors["lever"] = LeverConnector(
                api_key=self.settings.lever_api_key
            )
            logger.info("Initialized Lever connector")

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for job text using OpenAI

        Args:
            text: Combined job text (title + description + requirements)

        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        if not self.openai_client:
            return None

        try:
            # Limit text length to avoid token limits
            text = text[:8000] if len(text) > 8000 else text

            response = await self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=text,
                dimensions=3072,  # Match pgvector dimension
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def ingest_all_sources(
        self,
        limit_per_source: Optional[int] = None,
        normalize: bool = True,
        store: bool = True,
    ) -> Dict[str, List[JobListing]]:
        """
        Ingest jobs from all configured sources

        Args:
            limit_per_source: Maximum jobs to fetch per source
            normalize: Whether to normalize job data
            store: Whether to store jobs in database

        Returns:
            Dictionary mapping source name to list of ingested jobs
        """
        results = {}

        for source_name, connector in self.connectors.items():
            try:
                logger.info(f"Starting ingestion from {source_name}")
                jobs = await self.ingest_from_source(
                    connector,
                    source_name,
                    limit=limit_per_source,
                    normalize=normalize,
                    store=store,
                )
                results[source_name] = jobs
                logger.info(f"Ingested {len(jobs)} jobs from {source_name}")
            except Exception as e:
                logger.error(f"Failed to ingest from {source_name}: {e}")
                results[source_name] = []

        return results

    async def ingest_from_source(
        self,
        connector: ATSConnector,
        source_name: str,
        limit: Optional[int] = None,
        normalize: bool = True,
        store: bool = True,
    ) -> List[JobListing]:
        """
        Ingest jobs from a specific ATS source

        Args:
            connector: ATS connector instance
            source_name: Name of the ATS source
            limit: Maximum number of jobs to fetch
            normalize: Whether to normalize job data
            store: Whether to store jobs in database

        Returns:
            List of ingested job listings
        """
        # Fetch jobs from ATS
        try:
            raw_jobs = await connector.fetch_jobs(limit=limit)
            logger.info(f"Fetched {len(raw_jobs)} raw jobs from {source_name}")
        except Exception as e:
            logger.error(f"Failed to fetch jobs from {source_name}: {e}")
            raise

        # Normalize jobs if requested
        if normalize:
            jobs = []
            for raw_job in raw_jobs:
                try:
                    normalized = self.normalizer.normalize(raw_job)
                    jobs.append(normalized)
                except Exception as e:
                    logger.warning(
                        f"Failed to normalize job {raw_job.external_id}: {e}"
                    )
                    jobs.append(raw_job)
        else:
            jobs = raw_jobs

        # Store jobs if requested
        if store:
            stored_jobs = await self._store_jobs(jobs, source_name)
            return stored_jobs

        return jobs

    async def _store_jobs(
        self, jobs: List[JobListing], source_name: str
    ) -> List[JobListing]:
        """
        Store jobs in Supabase database

        Args:
            jobs: List of job listings to store
            source_name: Name of the ATS source

        Returns:
            List of successfully stored jobs
        """
        stored = []

        for job in jobs:
            try:
                # Check for existing job by job_id
                job_id = f"{source_name}_{job.external_id}"
                existing = (
                    self.supabase.table("job_postings")
                    .select("*")
                    .eq("job_id", job_id)
                    .execute()
                )

                # Extract company domain from URL or use placeholder
                company_domain = job.company_name.lower().replace(" ", "") + ".com"
                if job.application_url:
                    from urllib.parse import urlparse

                    parsed = urlparse(str(job.application_url))
                    if parsed.netloc:
                        company_domain = parsed.netloc

                # Prepare requirements text
                requirements_text = ""
                if job.requirements:
                    requirements_text = (
                        "\n".join(job.requirements)
                        if isinstance(job.requirements, list)
                        else str(job.requirements)
                    )
                if job.responsibilities:
                    resp_text = (
                        "\n".join(job.responsibilities)
                        if isinstance(job.responsibilities, list)
                        else str(job.responsibilities)
                    )
                    requirements_text = (
                        f"{requirements_text}\n\nResponsibilities:\n{resp_text}"
                        if requirements_text
                        else resp_text
                    )

                # Generate embedding for job
                embedding_text = f"{job.title}\n\n{job.description or ''}\n\n{requirements_text or ''}"
                embedding = await self.generate_embedding(embedding_text)
                if embedding:
                    logger.debug(
                        f"Generated embedding for job {job_id} (dim: {len(embedding)})"
                    )
                else:
                    logger.warning(f"No embedding generated for job {job_id}")

                job_data = {
                    "job_id": job_id,
                    "company_name": job.company_name,
                    "company_domain": company_domain,
                    "title": job.title,
                    "location": job.location,
                    "remote_type": job.remote_type.lower() if job.remote_type else None,
                    "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "department": job.department,
                    "employment_type": job.employment_type,
                    "seniority": job.experience_level,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "currency": job.salary_currency,
                    "job_url": (
                        str(job.application_url)
                        if job.application_url
                        else f"https://example.com/jobs/{job_id}"
                    ),
                    "description_text": job.description,
                    "requirements_text": requirements_text,
                    "embedding": embedding,  # Add the embedding
                    "last_seen_at": datetime.now(timezone.utc).isoformat(),
                }

                if existing.data:
                    # Update existing job
                    job_data["last_seen_at"] = datetime.now(timezone.utc).isoformat()
                    result = (
                        self.supabase.table("job_postings")
                        .update(job_data)
                        .eq("job_id", job_id)
                        .execute()
                    )
                    logger.debug(f"Updated job {job_id}")
                else:
                    # Insert new job
                    job_data["first_seen_at"] = datetime.now(timezone.utc).isoformat()
                    result = (
                        self.supabase.table("job_postings").insert(job_data).execute()
                    )
                    logger.debug(f"Inserted new job {job_id}")

                stored.append(job)

            except Exception as e:
                logger.error(f"Failed to store job {job.external_id}: {e}")
                continue

        logger.info(f"Stored {len(stored)}/{len(jobs)} jobs from {source_name}")
        return stored

    async def deduplicate_jobs(self) -> int:
        """
        Remove duplicate jobs across sources

        Returns:
            Number of duplicates removed
        """
        # Get all jobs
        jobs_response = self.supabase.table("job_postings").select("*").execute()
        jobs = jobs_response.data

        # Group by title + company + location
        seen: Set[tuple] = set()
        duplicates = []

        for job in jobs:
            key = (
                job.get("title", "").lower(),
                job.get("company_name", "").lower(),
                job.get("location", "").lower(),
            )

            if key in seen:
                duplicates.append(job["job_id"])
            else:
                seen.add(key)

        # Remove duplicates
        if duplicates:
            for job_id in duplicates:
                self.supabase.table("job_postings").delete().eq(
                    "job_id", job_id
                ).execute()
            logger.info(f"Removed {len(duplicates)} duplicate jobs")

        return len(duplicates)

    async def update_job_embeddings(self, batch_size: int = 10) -> int:
        """
        Generate and update embeddings for jobs without them

        Args:
            batch_size: Number of jobs to process at once

        Returns:
            Number of jobs updated
        """
        # Get jobs without embeddings
        jobs_response = (
            self.supabase.table("job_postings")
            .select("*")
            .is_("embedding", "null")
            .limit(batch_size)
            .execute()
        )

        jobs = jobs_response.data
        updated = 0

        for job in jobs:
            try:
                # Generate embedding from description
                text = f"{job['title']} {job.get('description_text', '')} {job.get('requirements_text', '')}"

                # TODO: Use actual embedding service
                # For now, create a placeholder embedding
                embedding = [0.1] * 3072  # Placeholder

                # Update job with embedding
                self.supabase.table("job_postings").update(
                    {
                        "embedding": embedding,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("job_id", job["job_id"]).execute()

                updated += 1

            except Exception as e:
                logger.error(f"Failed to update embedding for job {job['id']}: {e}")

        logger.info(f"Updated embeddings for {updated} jobs")
        return updated

    async def cleanup_expired_jobs(self) -> int:
        """
        Clean up old jobs (placeholder for now)

        Returns:
            Number of jobs cleaned up
        """
        # TODO: Implement job cleanup logic based on business rules
        # For example, remove jobs older than 90 days
        logger.info("Job cleanup not yet implemented")
        return 0


async def run_ingestion_cycle(
    orchestrator: Optional[JobIngestionOrchestrator] = None,
    limit_per_source: Optional[int] = None,
):
    """
    Run a complete ingestion cycle

    Args:
        orchestrator: Orchestrator instance (creates new if None)
        limit_per_source: Maximum jobs to fetch per source
    """
    if orchestrator is None:
        orchestrator = JobIngestionOrchestrator()

    # Ingest from all sources
    results = await orchestrator.ingest_all_sources(
        limit_per_source=limit_per_source, normalize=True, store=True
    )

    # Log results
    total_jobs = sum(len(jobs) for jobs in results.values())
    logger.info(
        f"Ingestion cycle complete: {total_jobs} total jobs from {len(results)} sources"
    )

    # Clean up duplicates
    duplicates_removed = await orchestrator.deduplicate_jobs()

    # Update embeddings for new jobs
    embeddings_updated = await orchestrator.update_job_embeddings()

    # Clean up expired jobs
    expired_cleaned = await orchestrator.cleanup_expired_jobs()

    logger.info(
        f"Post-processing complete: {duplicates_removed} duplicates removed, "
        f"{embeddings_updated} embeddings updated, {expired_cleaned} expired jobs cleaned"
    )

    return results


if __name__ == "__main__":
    # Run ingestion when module is executed directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_ingestion_cycle(limit_per_source=10))
