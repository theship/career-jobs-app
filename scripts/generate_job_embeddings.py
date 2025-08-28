#!/usr/bin/env python3
"""
Generate embeddings for existing jobs in the database that don't have them.
This script is used to backfill embeddings for jobs that were ingested before
embedding generation was added to the pipeline.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import openai
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def generate_embedding(client: openai.AsyncOpenAI, text: str) -> list[float]:
    """Generate embedding for text using OpenAI API"""
    try:
        # Limit text length to avoid token limits
        text = text[:8000] if len(text) > 8000 else text
        
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            dimensions=3072  # Match pgvector dimension
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


async def process_job(job: dict, openai_client: openai.AsyncOpenAI, supabase) -> bool:
    """Process a single job to generate and store embedding"""
    job_id = job["job_id"]
    
    try:
        # Combine title, description, and requirements for embedding
        title = job.get("title", "")
        description = job.get("description_text", "")
        requirements = job.get("requirements_text", "")
        
        embedding_text = f"{title}\n\n{description}\n\n{requirements}"
        
        # Generate embedding
        logger.info(f"Generating embedding for job {job_id}: {title}")
        embedding = await generate_embedding(openai_client, embedding_text)
        
        if not embedding:
            logger.warning(f"Failed to generate embedding for job {job_id}")
            return False
        
        # Update job with embedding
        result = supabase.table("job_postings").update({
            "embedding": embedding,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("job_id", job_id).execute()
        
        if result.data:
            logger.info(f"✅ Updated embedding for job {job_id}")
            return True
        else:
            logger.error(f"❌ Failed to update job {job_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        return False


async def main():
    """Main function to process all jobs without embeddings"""
    
    # Initialize clients
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not all([supabase_url, supabase_key, openai_api_key]):
        logger.error("Missing required environment variables")
        logger.error("Required: SUPABASE_URL, SUPABASE_ANON_KEY/SERVICE_KEY, OPENAI_API_KEY")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
    
    # Get all jobs without embeddings
    logger.info("Fetching jobs without embeddings...")
    
    # First, let's check total jobs
    total_response = supabase.table("job_postings").select("job_id", count="exact").execute()
    total_jobs = total_response.count
    logger.info(f"Total jobs in database: {total_jobs}")
    
    # Get jobs without embeddings (embedding is null)
    # Note: We can't directly query for null embeddings, so we'll fetch all and filter
    all_jobs_response = supabase.table("job_postings").select(
        "job_id, title, description_text, requirements_text, embedding"
    ).execute()
    
    jobs_without_embeddings = [
        job for job in all_jobs_response.data 
        if not job.get("embedding")
    ]
    
    logger.info(f"Found {len(jobs_without_embeddings)} jobs without embeddings")
    
    if not jobs_without_embeddings:
        logger.info("All jobs already have embeddings!")
        return
    
    # Process jobs with rate limiting
    batch_size = 5  # Process 5 jobs at a time to avoid rate limits
    success_count = 0
    failure_count = 0
    
    for i in range(0, len(jobs_without_embeddings), batch_size):
        batch = jobs_without_embeddings[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} ({i+1}-{min(i+batch_size, len(jobs_without_embeddings))} of {len(jobs_without_embeddings)})")
        
        # Process batch concurrently
        tasks = [process_job(job, openai_client, supabase) for job in batch]
        results = await asyncio.gather(*tasks)
        
        success_count += sum(results)
        failure_count += len(results) - sum(results)
        
        # Rate limiting - wait between batches
        if i + batch_size < len(jobs_without_embeddings):
            await asyncio.sleep(1)  # Wait 1 second between batches
    
    # Summary
    logger.info("=" * 50)
    logger.info(f"Processing complete!")
    logger.info(f"✅ Successfully updated: {success_count} jobs")
    logger.info(f"❌ Failed: {failure_count} jobs")
    logger.info(f"📊 Total jobs with embeddings now: {total_jobs - len(jobs_without_embeddings) + success_count}/{total_jobs}")


if __name__ == "__main__":
    asyncio.run(main())