"""
Shared test fixtures and configuration
"""

import os
from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Set test environment variables
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use database 15 for tests


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


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = False
    mock_client.setex.return_value = True
    mock_client.ttl.return_value = -2
    mock_client.keys.return_value = []
    mock_client.info.return_value = {
        "redis_version": "7.0.0",
        "redis_mode": "standalone",
        "used_memory": 1048576,
    }
    return mock_client


@pytest.fixture(autouse=True)
def mock_redis_for_all_tests(monkeypatch):
    """Automatically mock Redis for all tests unless using real Redis"""
    if os.getenv("USE_REAL_REDIS") != "true":
        with patch("api.utils.redis_client.get_redis_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.get.return_value = None
            mock_client.set.return_value = True
            mock_client.delete.return_value = 1
            mock_client.exists.return_value = False
            mock_client.setex.return_value = True
            mock_client.ttl.return_value = -2
            mock_client.keys.return_value = []
            mock_client.info.return_value = {
                "redis_version": "7.0.0",
                "redis_mode": "standalone",
                "used_memory": 1048576,
            }
            mock_get_client.return_value = mock_client
            yield mock_client
    else:
        # Use real Redis for integration tests
        yield
