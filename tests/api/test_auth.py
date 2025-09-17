"""
Fixed Authentication Tests
Tests for health checks and API authentication
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestHealthCheck:
    """Test basic API health endpoints"""

    def test_api_health_check(self):
        """API health endpoint works without authentication"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "career-jobs-api"

    def test_root_endpoint(self):
        """Root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "Career Jobs App API"
        assert response.json()["status"] == "operational"


class TestAuthenticationEndpoints:
    """Test authentication endpoints require proper headers"""

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_protected_endpoint_without_token(self):
        """Protected endpoints reject requests without service secret"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code in [401, 403]

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_protected_endpoint_with_invalid_token(self):
        """Protected endpoints reject invalid service secrets"""
        headers = {"X-Service-Secret": "invalid-secret"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code in [401, 403]

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_valid_service_secret_accepted(self):
        """Valid service secret with user headers is accepted"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "test-user-id",
            "X-User-Email": "test@example.com",
            "X-User-Token": "user-token",
        }
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-id"
        assert data["email"] == "test@example.com"

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_verify_endpoint(self):
        """Token verification endpoint returns correct data"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "test-user-id",
            "X-User-Email": "test@example.com",
            "X-User-Token": "user-token",
        }
        response = client.get("/api/v1/auth/verify", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == "test-user-id"

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_session_endpoint(self):
        """Session endpoint returns session information"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "test-user-id",
            "X-User-Email": "test@example.com",
            "X-User-Token": "user-token",
        }
        response = client.get("/api/v1/auth/session", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-id"


class TestConfigLoading:
    """Test configuration loading"""

    def test_settings_load(self):
        """Configuration settings load correctly"""
        from api.utils.config import get_settings

        settings = get_settings()
        assert settings.app_name == "Career Jobs App"
        assert settings.jwt_algorithm == "RS256"
        assert settings.jwt_audience == "authenticated"

    def test_required_env_vars(self):
        """Required environment variables are set"""
        from api.utils.config import get_settings

        settings = get_settings()
        assert settings.supabase_url is not None
        assert settings.supabase_anon_key is not None
        assert settings.openai_api_key is not None
