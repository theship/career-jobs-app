#!/usr/bin/env python
"""
Load sample job data into the database for testing
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import openai
from dotenv import load_dotenv

from supabase import create_client

load_dotenv()

# Sample job data
SAMPLE_JOBS = [
    {
        "job_id": "job_001",
        "company_name": "TechCorp Inc",
        "company_domain": "techcorp.com",
        "title": "Senior Software Engineer",
        "location": "San Francisco, CA",
        "remote_type": "hybrid",
        "posted_at": (datetime.now() - timedelta(days=2)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "department": "Engineering",
        "employment_type": "full_time",
        "seniority": "senior",
        "salary_min": 150000,
        "salary_max": 200000,
        "currency": "USD",
        "job_url": "https://techcorp.com/jobs/senior-software-engineer",
        "description_text": """
        We are looking for a Senior Software Engineer to join our growing team.
        You will be responsible for designing and implementing scalable web applications.

        Key Responsibilities:
        - Design and develop high-quality software solutions
        - Lead technical discussions and code reviews
        - Mentor junior engineers
        - Work with Python, React, PostgreSQL, and AWS
        """,
        "requirements_text": """
        - 5+ years of software engineering experience
        - Strong proficiency in Python and JavaScript
        - Experience with React and modern web frameworks
        - Knowledge of PostgreSQL and database design
        - AWS or cloud platform experience
        - Excellent communication skills
        """,
    },
    {
        "job_id": "job_002",
        "company_name": "DataSystems Ltd",
        "company_domain": "datasystems.io",
        "title": "Machine Learning Engineer",
        "location": "New York, NY",
        "remote_type": "remote",
        "posted_at": (datetime.now() - timedelta(days=3)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "department": "Data Science",
        "employment_type": "full_time",
        "seniority": "mid",
        "salary_min": 130000,
        "salary_max": 170000,
        "currency": "USD",
        "job_url": "https://datasystems.io/careers/ml-engineer",
        "description_text": """
        Join our ML team to build cutting-edge machine learning models and systems.

        What you'll do:
        - Develop and deploy ML models at scale
        - Work with TensorFlow, PyTorch, and scikit-learn
        - Build data pipelines and feature engineering systems
        - Collaborate with data scientists and engineers
        """,
        "requirements_text": """
        - 3+ years of ML engineering experience
        - Strong Python programming skills
        - Experience with TensorFlow or PyTorch
        - Knowledge of ML algorithms and statistics
        - Experience with Docker and Kubernetes
        - SQL and data processing skills
        """,
    },
    {
        "job_id": "job_003",
        "company_name": "WebDev Studios",
        "company_domain": "webdevstudios.com",
        "title": "Full Stack Developer",
        "location": "Austin, TX",
        "remote_type": "onsite",
        "posted_at": (datetime.now() - timedelta(days=5)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "department": "Engineering",
        "employment_type": "full_time",
        "seniority": "junior",
        "salary_min": 80000,
        "salary_max": 110000,
        "currency": "USD",
        "job_url": "https://webdevstudios.com/jobs/fullstack",
        "description_text": """
        Looking for a Full Stack Developer to build modern web applications.

        Responsibilities:
        - Develop frontend interfaces with React
        - Build REST APIs with Node.js
        - Work with MongoDB and PostgreSQL
        - Participate in agile development
        """,
        "requirements_text": """
        - 2+ years of web development experience
        - JavaScript, HTML, CSS proficiency
        - React and Node.js experience
        - Database knowledge (SQL/NoSQL)
        - Git version control
        - Team collaboration skills
        """,
    },
    {
        "job_id": "job_004",
        "company_name": "CloudTech Solutions",
        "company_domain": "cloudtech.com",
        "title": "DevOps Engineer",
        "location": "Seattle, WA",
        "remote_type": "remote",
        "posted_at": (datetime.now() - timedelta(days=1)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "department": "Operations",
        "employment_type": "full_time",
        "seniority": "senior",
        "salary_min": 140000,
        "salary_max": 180000,
        "currency": "USD",
        "job_url": "https://cloudtech.com/careers/devops",
        "description_text": """
        We need a DevOps Engineer to manage our cloud infrastructure.

        Key Areas:
        - Manage AWS infrastructure with Terraform
        - Build CI/CD pipelines with Jenkins/GitHub Actions
        - Implement monitoring with Prometheus and Grafana
        - Container orchestration with Kubernetes
        """,
        "requirements_text": """
        - 5+ years DevOps experience
        - Strong AWS knowledge
        - Terraform and IaC experience
        - Kubernetes and Docker expertise
        - Python or Go programming
        - Security best practices
        """,
    },
    {
        "job_id": "job_005",
        "company_name": "AI Innovations",
        "company_domain": "aiinnovations.ai",
        "title": "Data Scientist",
        "location": "Boston, MA",
        "remote_type": "hybrid",
        "posted_at": (datetime.now() - timedelta(days=4)).isoformat(),
        "updated_at": datetime.now().isoformat(),
        "department": "Data Science",
        "employment_type": "full_time",
        "seniority": "mid",
        "salary_min": 120000,
        "salary_max": 160000,
        "currency": "USD",
        "job_url": "https://aiinnovations.ai/jobs/data-scientist",
        "description_text": """
        Join our data science team to solve complex business problems.

        Your role:
        - Build predictive models and analytics
        - Work with Python, R, and SQL
        - Create data visualizations and dashboards
        - Present findings to stakeholders
        """,
        "requirements_text": """
        - MS in Data Science or related field
        - 3+ years data science experience
        - Python and R proficiency
        - Statistical analysis expertise
        - Machine learning knowledge
        - Strong communication skills
        """,
    },
]


def generate_embedding(text: str, openai_client) -> list:
    """Generate embedding for job text using OpenAI API"""
    try:
        # Limit text length to avoid token limits
        text = text[:8000] if len(text) > 8000 else text

        response = openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            dimensions=3072,  # Match pgvector dimension
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Warning: Failed to generate embedding: {e}")
        return None


def main():
    # Initialize Supabase client
    supabase = create_client(
        os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_ANON_KEY", "")
    )

    if not os.environ.get("SUPABASE_URL"):
        print("Error: SUPABASE_URL not set in environment")
        return

    # Initialize OpenAI client for embeddings (optional)
    openai_client = None
    if os.environ.get("OPENAI_API_KEY"):
        openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        print("OpenAI client initialized - will generate embeddings")
    else:
        print(
            "Warning: OPENAI_API_KEY not set - "
            "jobs will be loaded without embeddings"
        )

    print("Loading sample jobs into database...")

    for job in SAMPLE_JOBS:
        try:
            # Check if job already exists
            existing = (
                supabase.table("job_postings")
                .select("job_id")
                .eq("job_id", job["job_id"])
                .execute()
            )

            if existing.data:
                print(f"Job {job['job_id']} already exists, skipping...")
                continue

            # Generate embedding if OpenAI client is available
            if openai_client:
                embedding_text = (
                    f"{job['title']}\n\n{job.get('description_text', '')}\n\n"
                    f"{job.get('requirements_text', '')}"
                )
                embedding = generate_embedding(embedding_text, openai_client)
                if embedding:
                    job["embedding"] = embedding
                    print(f"  Generated embedding for {job['title']}")

            # Insert job
            supabase.table("job_postings").insert(job).execute()
            print(f"✓ Loaded job: {job['title']} at {job['company_name']}")

        except Exception as e:
            print(f"✗ Failed to load job {job['job_id']}: {e}")

    # Get count of jobs
    count_result = supabase.table("job_postings").select("*", count="exact").execute()
    print(f"\nTotal jobs in database: {count_result.count}")


if __name__ == "__main__":
    main()
