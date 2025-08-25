"""
Integration tests for Resume Processing Pipeline (Phase 2)
Tests the complete flow from upload to skill extraction
"""

import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from api.main import app
from api.services.auth import JWTAuthService

client = TestClient(app)


class TestResumeUploadIntegration:
    """Integration tests for resume upload and processing"""

    @patch("api.services.auth.get_auth_service")
    @patch("api.services.resume_processor.ResumeProcessor")
    async def test_complete_resume_upload_flow(self, mock_processor_class, mock_get_auth_service):
        """Test complete flow: upload -> text extraction -> skill extraction -> storage"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "aud": "authenticated",
            "role": "authenticated",
        }
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        mock_auth_service.extract_user_email.return_value = "test@example.com"
        mock_auth_service.extract_user_metadata.return_value = {}
        
        # Setup resume processor mock
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        
        # Mock text extraction
        sample_text = """
        John Doe - Senior Software Engineer
        
        Skills: Python (5 years), JavaScript (3 years), Docker, Kubernetes
        
        Experience:
        - Built scalable FastAPI applications
        - Deployed machine learning models with PyTorch
        - Led CI/CD implementation
        """
        mock_processor.extract_text = AsyncMock(return_value=sample_text)
        
        # Mock skill extraction
        mock_skill_result = Mock()
        mock_skill_result.skills = ["Python", "JavaScript", "Docker", "Kubernetes", "FastAPI", "PyTorch", "CI/CD"]
        mock_skill_result.method = "fuzzy_and_embeddings"
        mock_skill_result.confidence_scores = {
            "Python": 1.0,
            "JavaScript": 1.0,
            "Docker": 1.0,
            "Kubernetes": 1.0,
            "FastAPI": 0.9,
            "PyTorch": 0.9,
            "CI/CD": 0.85
        }
        mock_skill_result.evidence_spans = {
            "Python": [{"start": 45, "end": 51}],
            "JavaScript": [{"start": 63, "end": 73}],
        }
        mock_skill_result.coverage = 85.0
        mock_skill_result.years_experience = {
            "Python": 5.0,
            "JavaScript": 3.0
        }
        mock_skill_result.dict = Mock(return_value={
            "skills": mock_skill_result.skills,
            "method": mock_skill_result.method,
            "confidence_scores": mock_skill_result.confidence_scores,
            "evidence_spans": mock_skill_result.evidence_spans,
            "coverage": mock_skill_result.coverage,
            "years_experience": mock_skill_result.years_experience
        })
        mock_processor.extract_skills = AsyncMock(return_value=mock_skill_result)
        
        # Mock embedding generation
        mock_processor.generate_embedding = AsyncMock(return_value=[0.1] * 3072)
        
        # Mock Supabase storage
        with patch("api.routes.resumes.get_supabase_client") as mock_get_supabase:
            mock_supabase = Mock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock storage upload
            mock_storage = Mock()
            mock_supabase.storage = mock_storage
            mock_bucket = Mock()
            mock_storage.from_.return_value = mock_bucket
            mock_bucket.upload = Mock(return_value={"path": "test-user-id/resume.pdf"})
            
            # Mock database insert
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value = Mock(
                data=[{
                    "id": "resume-123",
                    "user_id": "test-user-id",
                    "name": "resume.pdf",
                    "file_path": "test-user-id/resume.pdf",
                    "text_content": sample_text,
                    "skills": mock_skill_result.skills,
                    "skills_metadata": {
                        "confidence_scores": mock_skill_result.confidence_scores,
                        "years_experience": mock_skill_result.years_experience,
                        "coverage": mock_skill_result.coverage,
                        "method": mock_skill_result.method
                    },
                    "embedding": [0.1] * 3072,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }]
            )
            
            # Create test file
            file_content = b"PDF content here"
            files = {
                "file": ("resume.pdf", file_content, "application/pdf")
            }
            
            # Make request
            headers = {"Authorization": "Bearer test-token"}
            response = client.post(
                "/api/v1/resumes/upload",
                files=files,
                headers=headers
            )
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["resume"]["id"] == "resume-123"
            assert data["resume"]["name"] == "resume.pdf"
            assert len(data["resume"]["skills"]) == 7
            assert data["skills"]["coverage"] == 85.0
            assert data["skills"]["years_experience"]["Python"] == 5.0
            assert data["message"] == "Resume uploaded and processed successfully"

    @patch("api.services.auth.get_auth_service")
    def test_upload_invalid_file_type(self, mock_get_auth_service):
        """Test that invalid file types are rejected"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {"sub": "test-user-id", "aud": "authenticated"}
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        
        # Create invalid file
        files = {
            "file": ("resume.exe", b"Invalid content", "application/x-msdownload")
        }
        
        headers = {"Authorization": "Bearer test-token"}
        response = client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    @patch("api.services.auth.get_auth_service")
    def test_upload_oversized_file(self, mock_get_auth_service):
        """Test that oversized files are rejected"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {"sub": "test-user-id", "aud": "authenticated"}
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        
        # Create oversized file (> 10MB)
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {
            "file": ("resume.pdf", large_content, "application/pdf")
        }
        
        headers = {"Authorization": "Bearer test-token"}
        response = client.post(
            "/api/v1/resumes/upload",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]


class TestResumeListAndRetrieve:
    """Test listing and retrieving resumes"""
    
    @patch("api.services.auth.get_auth_service")
    def test_list_user_resumes(self, mock_get_auth_service):
        """Test listing all resumes for a user"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {"sub": "test-user-id", "aud": "authenticated"}
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        
        with patch("api.routes.resumes.get_supabase_client") as mock_get_supabase:
            mock_supabase = Mock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock database query
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value = Mock(
                data=[
                    {
                        "id": "resume-1",
                        "name": "resume1.pdf",
                        "created_at": "2024-01-01T00:00:00Z",
                        "skills": ["Python", "Django"]
                    },
                    {
                        "id": "resume-2", 
                        "name": "resume2.pdf",
                        "created_at": "2024-01-02T00:00:00Z",
                        "skills": ["JavaScript", "React"]
                    }
                ]
            )
            
            headers = {"Authorization": "Bearer test-token"}
            response = client.get("/api/v1/resumes", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "resume-1"
            assert data[1]["id"] == "resume-2"

    @patch("api.services.auth.get_auth_service")
    def test_get_single_resume(self, mock_get_auth_service):
        """Test retrieving a single resume by ID"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {"sub": "test-user-id", "aud": "authenticated"}
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        
        with patch("api.routes.resumes.get_supabase_client") as mock_get_supabase:
            mock_supabase = Mock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock database query
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = Mock(
                data=[{
                    "id": "resume-123",
                    "user_id": "test-user-id",
                    "name": "resume.pdf",
                    "text_content": "Resume content",
                    "skills": ["Python", "FastAPI"],
                    "skills_metadata": {
                        "confidence_scores": {"Python": 1.0, "FastAPI": 0.9},
                        "coverage": 75.0
                    }
                }]
            )
            
            headers = {"Authorization": "Bearer test-token"}
            response = client.get("/api/v1/resumes/resume-123", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "resume-123"
            assert data["skills"] == ["Python", "FastAPI"]
            assert data["skills_metadata"]["coverage"] == 75.0

    @patch("api.services.auth.get_auth_service")
    def test_delete_resume(self, mock_get_auth_service):
        """Test deleting a resume"""
        # Setup auth mock
        mock_auth_service = Mock(spec=JWTAuthService)
        mock_get_auth_service.return_value = mock_auth_service
        
        test_payload = {"sub": "test-user-id", "aud": "authenticated"}
        mock_auth_service.verify_token.return_value = test_payload
        mock_auth_service.extract_user_id.return_value = "test-user-id"
        
        with patch("api.routes.resumes.get_supabase_client") as mock_get_supabase:
            mock_supabase = Mock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock storage delete
            mock_storage = Mock()
            mock_supabase.storage = mock_storage
            mock_bucket = Mock()
            mock_storage.from_.return_value = mock_bucket
            mock_bucket.remove.return_value = {"message": "Deleted"}
            
            # Mock database delete
            mock_table = Mock()
            mock_supabase.table.return_value = mock_table
            mock_table.delete.return_value.eq.return_value.eq.return_value.execute.return_value = Mock(
                data=[{"id": "resume-123"}]
            )
            
            headers = {"Authorization": "Bearer test-token"}
            response = client.delete("/api/v1/resumes/resume-123", headers=headers)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Resume deleted successfully"