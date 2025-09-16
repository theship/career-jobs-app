"""
Tests for Company Management API
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from api.main import app
from api.routes.companies import detect_ats_system, ATSDetectionResponse

client = TestClient(app)


class TestATSDetection:
    """Test ATS auto-detection functionality"""

    @pytest.mark.asyncio
    async def test_detect_lever_ats(self):
        """Test detecting Lever ATS"""
        with patch("api.routes.companies.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}
            
            mock_async_client = AsyncMock()
            mock_async_client.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            result = await detect_ats_system("Spotify")
            
            assert result.detected_ats == "lever"
            assert result.company_id == "spotify"
            assert result.confidence == 0.9
            assert "lever.co" in result.job_board_url

    @pytest.mark.asyncio
    async def test_detect_greenhouse_ats(self):
        """Test detecting Greenhouse ATS"""
        with patch("api.routes.companies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            
            # First call (Lever) fails
            lever_response = Mock()
            lever_response.status_code = 404
            
            # Second call (Greenhouse) succeeds
            greenhouse_response = Mock()
            greenhouse_response.status_code = 200
            greenhouse_response.json.return_value = {"jobs": []}
            
            mock_async_client.get.side_effect = [lever_response, greenhouse_response]
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            result = await detect_ats_system("Airbnb")
            
            assert result.detected_ats == "greenhouse"
            assert result.company_id == "airbnb"
            assert result.confidence == 0.9
            assert "greenhouse.io" in result.job_board_url

    @pytest.mark.asyncio
    async def test_detect_no_ats(self):
        """Test when no ATS is detected"""
        with patch("api.routes.companies.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            
            # All calls fail
            mock_response = Mock()
            mock_response.status_code = 404
            mock_async_client.get.return_value = mock_response
            
            mock_client.return_value.__aenter__.return_value = mock_async_client
            
            result = await detect_ats_system("Unknown Company")
            
            assert result.detected_ats is None
            assert result.company_id == "unknowncompany"
            assert result.confidence == 0.0
            assert result.job_board_url is None


class TestCompanyManagementAPI:
    """Test company management endpoints"""

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_add_company_requires_auth(self):
        """Adding company requires authentication"""
        response = client.post(
            "/api/v1/companies/add",
            json={"company_name": "Test Company"}
        )
        assert response.status_code in [401, 403]

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_add_company_with_auth(self):
        """Add company with valid authentication"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "user-123",
            "X-User-Email": "test@example.com",
            "X-User-Token": "token"
        }
        
        with patch("api.routes.companies.detect_ats_system") as mock_detect:
            # Mock ATS detection
            mock_detect.return_value = ATSDetectionResponse(
                company_name="Test Company",
                detected_ats="lever",
                company_id="testcompany",
                confidence=0.9,
                job_board_url="https://jobs.lever.co/testcompany"
            )
            
            with patch("api.routes.companies.CompanyManager") as mock_manager:
                mock_instance = Mock()
                mock_instance.get_all_companies = AsyncMock(return_value=[])
                mock_instance.add_company = AsyncMock(return_value={
                    "id": "123",
                    "display_name": "Test Company",
                    "company_id": "testcompany",
                    "ats_system": "lever",
                    "active": True
                })
                mock_manager.return_value = mock_instance
                
                response = client.post(
                    "/api/v1/companies/add",
                    json={"company_name": "Test Company"},
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["company_name"] == "Test Company"
                assert data["ats_system"] == "lever"
                assert "lever.co" in data["job_board_url"]

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_get_watchlist(self):
        """Get user's company watchlist"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "user-123",
            "X-User-Email": "test@example.com",
            "X-User-Token": "token"
        }
        
        with patch("api.routes.companies.CompanyManager") as mock_manager:
            mock_instance = Mock()
            mock_instance.get_all_companies = AsyncMock(return_value=[
                {
                    "id": "1",
                    "display_name": "Spotify",
                    "company_id": "spotify",
                    "ats_system": "lever",
                    "active": True,
                    "last_successful_fetch": "2024-01-01T00:00:00Z"
                },
                {
                    "id": "2",
                    "display_name": "Airbnb",
                    "company_id": "airbnb",
                    "ats_system": "greenhouse",
                    "active": True,
                    "last_successful_fetch": None
                }
            ])
            mock_manager.return_value = mock_instance
            
            response = client.get("/api/v1/companies/my-watchlist", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["company_name"] == "Spotify"
            assert data[1]["company_name"] == "Airbnb"

    @patch.dict("os.environ", {"SERVICE_SECRET": "test-secret"})
    def test_remove_from_watchlist(self):
        """Remove company from watchlist"""
        headers = {
            "X-Service-Secret": "test-secret",
            "X-User-Id": "user-123",
            "X-User-Email": "test@example.com",
            "X-User-Token": "token"
        }
        
        with patch("api.routes.companies.CompanyManager") as mock_manager:
            mock_instance = Mock()
            mock_instance.update_company = AsyncMock()
            mock_manager.return_value = mock_instance
            
            response = client.delete("/api/v1/companies/company-123", headers=headers)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Company removed from watchlist"