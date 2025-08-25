"""Tests for resume processing pipeline."""

import io
from unittest.mock import AsyncMock, Mock, patch

import pytest

from api.models.resumes import SkillExtractionResult
from api.services.resume_processor import ResumeProcessor


@pytest.fixture
def resume_processor():
    """Create a resume processor instance."""
    with patch("api.services.resume_processor.settings") as mock_settings:
        mock_settings.CONFIG_DIR = "/tmp/config"
        mock_settings.openai_api_key = "test-key"
        processor = ResumeProcessor()
        return processor


@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
    John Doe
    Software Engineer
    
    SKILLS:
    - Python (5 years)
    - JavaScript, React
    - Docker, Kubernetes
    - Machine Learning with PyTorch
    - RESTful API development
    
    EXPERIENCE:
    Senior Software Engineer at TechCorp
    - Developed scalable microservices using Python and FastAPI
    - Implemented CI/CD pipelines with Docker and GitHub Actions
    - Led agile team of 5 engineers
    """


@pytest.mark.asyncio
async def test_skill_extraction_fuzzy_matching(resume_processor, sample_resume_text):
    """Test skill extraction using fuzzy matching."""
    # Mock the vocabulary
    resume_processor.skills_vocab = {
        "python": {
            "canonical": "Python",
            "category": "Languages",
            "aliases": ["py"],
            "tags": [],
        },
        "javascript": {
            "canonical": "JavaScript",
            "category": "Languages",
            "aliases": ["js"],
            "tags": [],
        },
        "react": {
            "canonical": "React",
            "category": "Frameworks",
            "aliases": [],
            "tags": [],
        },
        "docker": {
            "canonical": "Docker",
            "category": "DevOps",
            "aliases": [],
            "tags": [],
        },
        "kubernetes": {
            "canonical": "Kubernetes",
            "category": "DevOps",
            "aliases": ["k8s"],
            "tags": [],
        },
        "machine learning": {
            "canonical": "Machine Learning",
            "category": "AI",
            "aliases": ["ml"],
            "tags": [],
        },
        "pytorch": {
            "canonical": "PyTorch",
            "category": "AI",
            "aliases": [],
            "tags": [],
        },
        "fastapi": {
            "canonical": "FastAPI",
            "category": "Frameworks",
            "aliases": [],
            "tags": [],
        },
        "ci/cd": {
            "canonical": "CI/CD",
            "category": "DevOps",
            "aliases": [],
            "tags": [],
        },
        "agile": {
            "canonical": "Agile",
            "category": "Methodology",
            "aliases": [],
            "tags": [],
        },
    }

    # Test extraction
    result = await resume_processor.extract_skills(sample_resume_text)

    assert isinstance(result, SkillExtractionResult)
    assert len(result.skills) > 0
    assert "Python" in result.skills
    assert "JavaScript" in result.skills
    assert "Docker" in result.skills
    assert result.method in ["fuzzy_matching", "fuzzy_and_embeddings", "full_pipeline"]
    assert result.coverage > 0
    assert isinstance(result.confidence_scores, dict)
    assert isinstance(result.evidence_spans, dict)


def test_extract_years_experience(resume_processor):
    """Test extracting years of experience for skills."""
    text = "I have 5 years of Python experience and 3+ years working with React"

    years_python = resume_processor._extract_years_for_skill(text, "Python")
    years_react = resume_processor._extract_years_for_skill(text, "React")

    assert years_python == 5.0
    assert years_react == 3.0


def test_find_spans(resume_processor):
    """Test finding character spans for skills."""
    text = "I am proficient in Python and Python is my favorite language"
    spans = resume_processor._find_spans(text, "Python")

    assert len(spans) == 2
    assert spans[0]["start"] == 19
    assert spans[0]["end"] == 25
    assert spans[1]["start"] == 30
    assert spans[1]["end"] == 36


@pytest.mark.asyncio
async def test_pdf_text_extraction(resume_processor):
    """Test PDF text extraction."""
    # Create a mock PDF file
    mock_file = Mock()
    mock_file.filename = "resume.pdf"
    mock_file.read = AsyncMock(return_value=b"Mock PDF content")
    mock_file.seek = AsyncMock()

    with patch("api.services.resume_processor.extract_text") as mock_extract:
        mock_extract.return_value = "Extracted text from PDF"

        text = await resume_processor.extract_text(mock_file)

        assert text == "Extracted text from PDF"
        mock_file.seek.assert_called_with(0)


@pytest.mark.asyncio
async def test_docx_text_extraction(resume_processor):
    """Test DOCX text extraction."""
    mock_file = Mock()
    mock_file.filename = "resume.docx"
    mock_file.read = AsyncMock(return_value=b"Mock DOCX content")
    mock_file.seek = AsyncMock()

    with patch("api.services.resume_processor.Document") as mock_doc:
        mock_document = Mock()
        mock_document.paragraphs = [
            Mock(text="First paragraph"),
            Mock(text="Second paragraph"),
            Mock(text=""),  # Empty paragraph should be skipped
        ]
        mock_document.tables = []
        mock_doc.return_value = mock_document

        text = await resume_processor.extract_text(mock_file)

        assert "First paragraph" in text
        assert "Second paragraph" in text
        mock_file.seek.assert_called_with(0)


@pytest.mark.asyncio
async def test_txt_text_extraction(resume_processor):
    """Test plain text extraction."""
    mock_file = Mock()
    mock_file.filename = "resume.txt"
    mock_file.read = AsyncMock(return_value=b"Plain text resume content")
    mock_file.seek = AsyncMock()

    text = await resume_processor.extract_text(mock_file)

    assert text == "Plain text resume content"
    mock_file.seek.assert_called_with(0)


@pytest.mark.asyncio
async def test_unsupported_file_type(resume_processor):
    """Test handling of unsupported file types."""
    mock_file = Mock()
    mock_file.filename = "resume.xyz"
    mock_file.read = AsyncMock(return_value=b"Content")
    mock_file.seek = AsyncMock()  # Add async seek mock

    with pytest.raises(ValueError) as exc_info:
        await resume_processor.extract_text(mock_file)

    assert "Unsupported file type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_embedding(resume_processor):
    """Test embedding generation."""
    with patch.object(
        resume_processor.openai_client.embeddings, "create"
    ) as mock_create:
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3] * 1024)]  # 3072 dimensions
        mock_create.return_value = mock_response

        embedding = await resume_processor.generate_embedding("Test text")

        assert len(embedding) == 3072
        assert all(isinstance(x, float) for x in embedding)
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_skills_vocabulary_loading(resume_processor):
    """Test loading skills vocabulary from CSV."""
    csv_content = """skill,category,aliases,tags
Python,Languages,py|python3,backend|scripting
JavaScript,Languages,JS,frontend|web
"""

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value = io.StringIO(csv_content)

        with patch("os.path.exists", return_value=True):
            vocab = resume_processor._load_skills_vocabulary()

            assert "python" in vocab
            assert vocab["python"]["canonical"] == "Python"
            assert vocab["python"]["category"] == "Languages"
            assert "py" in vocab["python"]["aliases"]
            assert "backend" in vocab["python"]["tags"]

            # Check alias mapping
            assert "py" in vocab
            assert vocab["py"]["canonical"] == "Python"


def test_skills_vocabulary_missing_file(resume_processor):
    """Test handling of missing vocabulary file."""
    with patch("os.path.exists", return_value=False):
        vocab = resume_processor._load_skills_vocabulary()
        assert vocab == {}


@pytest.mark.asyncio
async def test_multi_stage_pipeline_integration(resume_processor, sample_resume_text):
    """Test the complete multi-stage skill extraction pipeline."""
    # Mock OpenAI calls
    with patch.object(
        resume_processor.openai_client.embeddings, "create"
    ) as mock_embed:
        with patch.object(
            resume_processor.openai_client.chat.completions, "create"
        ) as mock_chat:
            # Mock embedding response
            mock_embed_response = Mock()
            mock_embed_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_embed.return_value = mock_embed_response

            # Mock chat completion response
            mock_chat_response = Mock()
            mock_chat_response.choices = [
                Mock(
                    message=Mock(
                        function_call=Mock(
                            arguments='{"skills": [{"skill": "Python", "confidence": 1.0, "years_experience": 5}]}'
                        )
                    )
                )
            ]
            mock_chat.return_value = mock_chat_response

            # Set up vocabulary
            resume_processor.skills_vocab = {
                "python": {
                    "canonical": "Python",
                    "category": "Languages",
                    "aliases": [],
                    "tags": [],
                },
            }

            result = await resume_processor.extract_skills(sample_resume_text)

            assert isinstance(result, SkillExtractionResult)
            assert len(result.skills) > 0
            assert result.coverage >= 0
            assert result.coverage <= 100
