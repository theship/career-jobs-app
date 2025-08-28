#!/usr/bin/env python3
"""
Setup test user in the database for testing purposes
"""

import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.utils.database import get_supabase_client  # noqa: E402


def setup_test_user():
    supabase = get_supabase_client()

    # Test user ID (same as our test token)
    test_user_id = "00000000-0000-0000-0000-000000000001"

    # Check if user exists
    try:
        existing = (
            supabase.table("app_user").select("*").eq("user_id", test_user_id).execute()
        )
        if existing.data and len(existing.data) > 0:
            print(f"✅ Test user already exists: {test_user_id}")
            return test_user_id
    except Exception as e:
        print(f"Checking existing user: {e}")

    # Create test user in app_user table
    user_data = {
        "user_id": test_user_id,
        "preferred_geolocation": "San Francisco, CA",
        "notes": "Test user for development",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = supabase.table("app_user").insert(user_data).execute()
        if response.data:
            print(f"✅ Created test user: {test_user_id}")
            print("   Location: San Francisco, CA")
            return test_user_id
        else:
            print("❌ Failed to create user - no data returned")
            return None
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None


def create_test_resume(user_id):
    """Create a test resume for the given user"""
    supabase = get_supabase_client()

    # Generate a proper SHA256 hash for the test content
    test_content = "test_resume_content"
    sha256_hash = hashlib.sha256(test_content.encode()).hexdigest()

    # Create a test resume
    resume_data = {
        "user_id": user_id,
        "filename": "test_resume.pdf",
        "storage_path": "uploads/test_resume.pdf",
        "sha256": f"\\x{sha256_hash}",
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
            print(f"   User ID: {user_id}")
            print("   Filename: test_resume.pdf")
            return resume_id
        else:
            print("❌ Failed to create resume - no data returned")
            return None

    except Exception as e:
        print(f"❌ Error creating resume: {e}")
        return None


if __name__ == "__main__":
    print("Setting up test data...")
    print("-" * 40)

    # First ensure test user exists
    user_id = setup_test_user()

    if user_id:
        print("\n📝 Creating test resume...")
        resume_id = create_test_resume(user_id)

        if resume_id:
            print("\n✅ Test data setup complete!")
            print(f"   User ID: {user_id}")
            print(f"   Resume ID: {resume_id}")
            print("\nYou can now test the scoring flow with this data.")
        else:
            print("\n❌ Failed to create test resume")
    else:
        print("\n❌ Failed to setup test user")
