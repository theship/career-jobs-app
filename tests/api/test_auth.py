"""
Authentication Tests - Phase 1
Tests for JWT verification, health checks, and API authentication
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.auth import get_auth_service

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


class TestAuthentication:
    """Test JWT authentication and protected endpoints"""

    def test_protected_endpoint_without_token(self):
        """Protected endpoints reject requests without token"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403  # No Authorization header

    def test_protected_endpoint_with_invalid_token(self):
        """Protected endpoints reject invalid tokens"""
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @patch("api.services.auth.PyJWKClient")
    def test_valid_token_accepted(self, mock_jwk_client):
        """Valid Supabase JWT tokens are accepted"""
        # Mock the JWKS client
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = (
            mock_signing_key
        )

        # Create a test token payload
        test_payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
        }

        # Mock jwt.decode to return our test payload
        with patch("jwt.decode", return_value=test_payload):
            headers = {"Authorization": "Bearer valid-test-token"}
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "test-user-id"
            assert data["email"] == "test@example.com"

    @patch("api.services.auth.PyJWKClient")
    def test_expired_token_rejected(self, mock_jwk_client):
        """Expired tokens are rejected"""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = (
            mock_signing_key
        )

        # Mock jwt.decode to raise ExpiredSignatureError
        with patch("jwt.decode", side_effect=jwt.ExpiredSignatureError()):
            headers = {"Authorization": "Bearer expired-token"}
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()

    @patch("api.services.auth.PyJWKClient")
    def test_wrong_audience_rejected(self, mock_jwk_client):
        """Tokens with wrong audience are rejected"""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = (
            mock_signing_key
        )

        # Mock jwt.decode to raise InvalidAudienceError
        with patch("jwt.decode", side_effect=jwt.InvalidAudienceError()):
            headers = {"Authorization": "Bearer wrong-audience-token"}
            response = client.get("/api/v1/auth/me", headers=headers)

            assert response.status_code == 401
            assert "audience" in response.json()["detail"].lower()


class TestAuthEndpoints:
    """Test specific auth endpoints"""

    @patch("api.services.auth.PyJWKClient")
    def test_verify_endpoint(self, mock_jwk_client):
        """Token verification endpoint returns correct data"""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = (
            mock_signing_key
        )

        test_payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
        }

        with patch("jwt.decode", return_value=test_payload):
            headers = {"Authorization": "Bearer test-token"}
            response = client.get("/api/v1/auth/verify", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == True
            assert data["user_id"] == "test-user-id"
            assert "expires_at" in data

    @patch("api.services.auth.PyJWKClient")
    def test_session_endpoint(self, mock_jwk_client):
        """Session endpoint returns session information"""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = (
            mock_signing_key
        )

        test_payload = {
            "sub": "test-user-id",
            "aud": "authenticated",
            "role": "authenticated",
            "session_id": "test-session-123",
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
        }

        with patch("jwt.decode", return_value=test_payload):
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
