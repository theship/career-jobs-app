#!/usr/bin/env python3
"""
Create a test resume in the database for testing purposes
"""

import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.utils.database import get_supabase_client  # noqa: E402
from supabase import create_client  # noqa: E402


def create_test_resume():
    # Use service role key to bypass RLS for testing
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")  # This bypasses RLS

    if supabase_service_key:
        # Use service key if available
        supabase = create_client(supabase_url, supabase_service_key)
    else:
        # Fall back to regular client
        supabase = get_supabase_client()

    # Test user ID (same as our test token)
    test_user_id = "00000000-0000-0000-0000-000000000001"

    # Generate a proper SHA256 hash for the test content
    test_content = "test_resume_content"
    sha256_hash = hashlib.sha256(test_content.encode()).hexdigest()

    # Create a test resume
    resume_data = {
        "user_id": test_user_id,
        "filename": "test_resume.pdf",
        "storage_path": "uploads/test_resume.pdf",  # Required field
        "sha256": f"\\x{sha256_hash}",  # Required field as bytea
        "text_content": """John Smith
Senior Software Engineer
john.smith@email.com | (555) 123-4567

SUMMARY
Experienced software engineer with 8+ years developing scalable web applications.
Expertise in Python, JavaScript, React, Node.js, AWS, and Docker.

EXPERIENCE
Senior Software Engineer - Tech Company (2020-Present)
- Led development of microservices architecture serving 1M+ users
- Implemented CI/CD pipelines reducing deployment time by 60%
- Mentored junior developers and conducted code reviews

Software Engineer - Startup Inc (2016-2020)
- Built RESTful APIs and React frontend components
- Optimized database queries improving response time by 40%
- Collaborated with product team on feature planning

SKILLS
Languages: Python, JavaScript, TypeScript, Java, Go
Frameworks: React, Node.js, Django, Flask, FastAPI
Databases: PostgreSQL, MongoDB, Redis
Cloud: AWS, GCP, Docker, Kubernetes
Tools: Git, Jenkins, Terraform, DataDog

EDUCATION
BS Computer Science - State University (2016)
""",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Insert the resume
        response = supabase.table("resumes").insert(resume_data).execute()

        if response.data:
            resume_id = response.data[0]["resume_id"]
            print(f"✅ Created test resume with ID: {resume_id}")
            print(f"   User ID: {test_user_id}")
            print("   Filename: test_resume.pdf")
            print(f"   Text content: {len(resume_data['text_content'])} characters")
            return resume_id
        else:
            print("❌ Failed to create resume - no data returned")
            return None

    except Exception as e:
        print(f"❌ Error creating resume: {e}")
        return None


if __name__ == "__main__":
    resume_id = create_test_resume()

    if resume_id:
        print("\n📝 Test resume created successfully!")
        print(f"You can now use resume_id='{resume_id}' for testing")
    else:
        print("\n❌ Failed to create test resume")
