"""
Test Helper Functions
"""

import os
from typing import Dict


def get_test_auth_headers(
    user_id: str = "test-user", email: str = "test@example.com"
) -> Dict[str, str]:
    """
    Get authentication headers for testing.
    These headers simulate a request from the Next.js frontend with SERVICE_SECRET.
    """
    return {
        "X-Service-Secret": os.getenv("SERVICE_SECRET", "test-secret"),
        "X-User-Id": user_id,
        "X-User-Email": email,
        "X-User-Token": "test-token",
    }


def mock_supabase_response(data=None, error=None):
    """Create a mock Supabase response."""

    class MockResponse:
        def __init__(self, data, error):
            self.data = data if data is not None else []
            self.error = error

        def execute(self):
            return self

    return MockResponse(data, error)


def mock_redis_client():
    """Create a mock Redis client for testing."""

    class MockRedis:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def set(self, key, value, ex=None):
            self.data[key] = value
            return True

        def setex(self, key, ttl, value):
            self.data[key] = value
            return True

        def incr(self, key):
            if key not in self.data:
                self.data[key] = 0
            self.data[key] += 1
            return self.data[key]

        def ttl(self, key):
            return 3600  # Mock TTL

        def ping(self):
            return True

    return MockRedis()
