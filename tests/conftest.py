"""
Shared test fixtures and configuration
"""

import pytest
import os
from typing import Generator
from unittest.mock import MagicMock
from datetime import datetime, timedelta

# Set test environment variables
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing"""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = []
    return mock_client


@pytest.fixture
def valid_jwt_payload():
    """Valid JWT payload for testing"""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "user_metadata": {"full_name": "Test User"},
        "session_id": "session-123",
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }


@pytest.fixture
def test_user_data():
    """Test user data"""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "full_name": "Test User",
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True,
        "email_verified": True,
    }
