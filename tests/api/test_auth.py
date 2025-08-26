"""
Fixed Authentication Tests - Phase 1
Tests for JWT verification, health checks, and API authentication
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app
from api.services.auth import JWTAuthService

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


class TestJWTAuthService:
    """Test the JWT Auth Service directly"""

    @patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co"})
    def test_verify_valid_token(self):
        """Test verifying a valid token"""
        test_payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }

        with patch("api.services.auth.PyJWKClient") as mock_jwk_client_class:
            # Mock the JWKS client instance
            mock_jwk_instance = Mock()
            mock_jwk_client_class.return_value = mock_jwk_instance

            # Mock the signing key
            mock_signing_key = Mock()
            mock_signing_key.key = "test-key"
            mock_jwk_instance.get_signing_key_from_jwt.return_value = mock_signing_key

            # Mock jwt.decode
            with patch("api.services.auth.jwt.decode", return_value=test_payload):
                service = JWTAuthService()
                result = service.verify_token("test-token")

                assert result == test_payload
                assert result["sub"] == "test-user-id"

    @patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co"})
    def test_verify_expired_token(self):
        """Test verifying an expired token"""
        with patch("api.services.auth.PyJWKClient") as mock_jwk_client_class:
            mock_jwk_instance = Mock()
            mock_jwk_client_class.return_value = mock_jwk_instance

            mock_signing_key = Mock()
            mock_signing_key.key = "test-key"
            mock_jwk_instance.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch(
                "api.services.auth.jwt.decode",
                side_effect=jwt.ExpiredSignatureError(),
            ):
                service = JWTAuthService()

                with pytest.raises(HTTPException) as exc_info:
                    service.verify_token("expired-token")

                assert exc_info.value.status_code == 401
                assert "expired" in exc_info.value.detail.lower()

    @patch.dict("os.environ", {"SUPABASE_URL": "https://test.supabase.co"})
    def test_verify_wrong_audience_token(self):
        """Test verifying a token with wrong audience"""
        with patch("api.services.auth.PyJWKClient") as mock_jwk_client_class:
            mock_jwk_instance = Mock()
            mock_jwk_client_class.return_value = mock_jwk_instance

            mock_signing_key = Mock()
            mock_signing_key.key = "test-key"
            mock_jwk_instance.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch(
                "api.services.auth.jwt.decode",
                side_effect=jwt.InvalidAudienceError(),
            ):
                service = JWTAuthService()

                with pytest.raises(HTTPException) as exc_info:
                    service.verify_token("wrong-audience-token")

                assert exc_info.value.status_code == 401
                assert "audience" in exc_info.value.detail.lower()


class TestAuthenticationEndpoints:
    """Test authentication endpoints with proper mocking"""

    def test_protected_endpoint_without_token(self):
        """Protected endpoints reject requests without token"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # No Authorization header

    def test_protected_endpoint_with_invalid_token(self):
        """Protected endpoints reject invalid tokens"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @patch("api.services.auth.get_auth_service")
    def test_valid_token_accepted(self, mock_get_auth_service):
        """Valid Supabase JWT tokens are accepted"""
        # Create mock auth service
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service

        # Mock the verify_token method
        test_payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        mock_auth_service.extract_user_email.return_value = "test@example.com"
        mock_auth_service.extract_user_metadata.return_value = {}

        headers = {"Authorization": "Bearer valid-test-token"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-id"
        assert data["email"] == "test@example.com"

    @patch("api.services.auth.get_auth_service")
    def test_verify_endpoint(self, mock_get_auth_service):
        """Token verification endpoint returns correct data"""
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service

        test_payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        mock_auth_service.extract_user_email.return_value = None
        mock_auth_service.extract_user_metadata.return_value = {}

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/auth/verify", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] == True
        assert data["user_id"] == "test-user-id"
        assert "expires_at" in data

    @patch("api.services.auth.get_auth_service")
    def test_session_endpoint(self, mock_get_auth_service):
        """Session endpoint returns session information"""
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service

        test_payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "role": "authenticated",
            "session_id": "test-session-123",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
        }
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        mock_auth_service.extract_user_email.return_value = None
        mock_auth_service.extract_user_metadata.return_value = {}

        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/auth/session", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["user_id"] == "test-user-id"
        assert data["role"] == "authenticated"


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
