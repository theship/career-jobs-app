# Career Jobs App - Development Plan

## 📊 Quick Status Summary (Updated 2025-08-25)

### Project Progress
- **Phase 1: Foundation & Authentication** ✅ COMPLETE (100%)
- **Phase 2: Resume Processing Pipeline** ✅ COMPLETE (100%)
- **Phase 3: Job Ingestion System** ✅ COMPLETE (100%)
- **Phase 4: Scoring Engine** 📋 NOT STARTED
- **Phase 5: AI Research & Pitch** 📋 NOT STARTED
- **Phase 6: Export & Integration** 📋 NOT STARTED

### Current State
- **Test Status:** 23/23 tests passing ✅
- **Backend API:** FastAPI running at http://localhost:8000 ✅
- **Frontend:** Next.js at http://localhost:3001 (boilerplate UI only) ⚠️
- **Database:** Supabase configured with pgvector ✅
- **Authentication:** JWT/JWKS verification working ✅

## Overview

This document outlines the phased development approach for the Career Jobs App, including acceptance criteria, testing strategies, and milestone definitions. Phase 0–6. Stack: Supabase (Postgres + Auth + Storage + RLS + pgvector), FastAPI, Next.js, OpenAI embeddings, W&B + Weave later for experiments/observability. JWT verification is JWKS‑based.

## Source Coverage Matrix (what maps where)

| Source item                         | Doc section(s)                                                               | Notes                              |
| ----------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------- |
| Supabase Signing Keys + JWKS URL    | dev‑plan.md Phase 0 & Phase 1 (Auth)                                         | JWKS is normative; no HS256 secret |
| pgvector + pgcrypto in `extensions` | dev‑plan.md Phase 0; IMPLEMENTATION\_TODOS Critical DB                       | Clarifies schema location          |
| Minimal schema + RLS                | dev‑plan.md Phase 1 DB; project‑structure‑overview\.md Data Model            | Owner‑only policies                |
| FE auth flow + `/login`             | dev‑plan.md Phase 1 Frontend; TODOs Frontend                                 | Session + Bearer to backend        |
| Backend acceptance tests            | dev‑plan.md Phase 1 Tests; TODOs Testing                                     | Health/reject/accept/me            |
| Skills vocabulary CSV               | dev‑plan.md Phase 2 “Skills Vocabulary”; project‑structure‑overview\.md tree | `skill,category,aliases,tags`      |
| W\&B + Weave (later phases)         | dev‑plan.md Phases 4–5 retained                                              | No changes                         |

## Agent Assistant Prompts

* **STRICT\_NO\_ERASURE:** *Do not delete or rewrite existing sections unless the diff explicitly shows line‑anchored replacements. If something must be removed, emit a justification and a reversible patch.*
* **DIFF‑ONLY OUTPUT:** *Produce unified diffs with anchors (±10 lines) for each file changed. No free‑hand rewrites.*
* **COVERAGE MATRIX:** *List every requirement and where it appears in the updated docs.*
* **DOC MANIFEST:** *Show per‑file line counts and SHA256 checksums after changes.*
* **FAIL‑CLOSED:** *If any referenced section is missing, stop and report missing anchors rather than guessing.*

## Development Environment Commands

### Quick Start
```bash
# Start backend (from project root)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend (in separate terminal)
cd dashboard && npm run dev

# Run tests
pytest tests/ -v --cov=api
```

### Key Commands for Development
```bash
# Backend development
pip install -r requirements.txt
python -m pytest tests/ -v

# Frontend development  
cd dashboard
npm install
npm run dev

# Linting and formatting
black api/
isort api/
```

## 🔑 Environment Variables Needed

```bash
# Backend (.env)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ... 
SUPABASE_SERVICE_ROLE_KEY=eyJ...
OPENAI_API_KEY=sk-...

# Frontend (dashboard/.env.local)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

## Development Phases

### Phase 1: Foundation & Authentication (Weeks 1-2) ✅ COMPLETE

#### Objectives
* ✅ Set up core infrastructure
* ✅ Implement user authentication  
* ⚠️ Create basic database schema (partial - tables created, migrations pending)
* ✅ Establish development workflow

#### Tasks

1. **Database Setup**
   * Configure Supabase project with pgvector extension
   * Create core tables with RLS policies
   * Set up database migrations in Supabase Dashboard

2. **Project Structure Setup**
   * Create `/api` directory with FastAPI structure (models, routes, services, utils)
   * Set up `/config` directory with settings.yaml and JSON schemas
   * Create `/dashboard` directory for Next.js frontend  **IMPORTANT** see docs/preferred-UI-styling/ for styling
   * Initialize `/scripts` for utility scripts

3. **Authentication System**
   * Configure Supabase Auth project settings
   -Implement JWT verification in `/api/services/auth.py` using **JWT Signing Keys (JWKS)**.
    -- Enable **Signing Keys** in Supabase (Auth → JWT).
    -- Verify via JWKS at `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` (RS256/ES256, `aud=authenticated`).
    -- Cache JWKS for a few minutes; no legacy HS256 shared secret in backend.
   * Create user registration/login flows in `/dashboard/src/app/login`
     **IMPORTANT**: Follow the design system in `docs/FRONTEND_DESIGN_BRIEF.md`
     * Dark theme with black backgrounds and red accents
     * See `docs/preferred-UI-styling/` for reference screenshots
   * Set up Supabase client in `/dashboard/src/lib/supabase.ts`

#### Backend Acceptance Tests

```python
# tests/api/test_auth.py
def test_api_health_check():
    """API health endpoint works without authentication"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_supabase_jwt_verification():
    """FastAPI verifies Supabase JWT tokens correctly"""
    # Without token
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    
    # With valid Supabase JWT token (generated by frontend)
    supabase_jwt = get_valid_supabase_jwt()  # Helper function
    headers = {"Authorization": f"Bearer {supabase_jwt}"}
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["user_id"] == extract_user_id_from_jwt(supabase_jwt)

def test_config_loading():
    """Configuration files load correctly"""
    from api.utils.config import load_settings
    settings = load_settings()
    assert settings.supabase_url is not None
    assert settings.openai_api_key is not None

def test_row_level_security():
    """User can only access their own data through API"""
    user1_headers = {"Authorization": f"Bearer {user1_jwt}"}
    user2_headers = {"Authorization": f"Bearer {user2_jwt}"}
    
    # This test will be relevant once we implement resume endpoints
    # Placeholder for Phase 2 testing
    pass
```

#### Frontend Acceptance Tests

```typescript
// dashboard/src/__tests__/auth.test.tsx
describe('Authentication Flow', () => {
  it('should allow user registration with Supabase Auth', async () => {
    render(<RegisterPage />)
    
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/password/i), 'secure123')
    await user.click(screen.getByRole('button', { name: /register/i }))
    
    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument()
    })
  })

  it('should redirect unauthenticated users to login', async () => {
    render(<DashboardPage />)
    
    await waitFor(() => {
      expect(window.location.pathname).toBe('/login')
    })
  })

  it('should persist login state using Supabase session', async () => {
    // Mock Supabase session
    const mockSession = { user: { id: '123', email: 'test@example.com' }}
    mockSupabaseAuth.getSession.mockResolvedValue({ data: { session: mockSession }})
    
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
    })
  })

  it('should make authenticated API calls to backend', async () => {
    const mockUser = { id: '123', email: 'test@example.com' }
    mockSupabaseAuth.getUser.mockResolvedValue({ data: { user: mockUser }})
    
    render(<DashboardPage />)
    
    await waitFor(() => {
      // Should call /api/v1/me with Authorization header
      expect(fetch).toHaveBeenCalledWith('/api/v1/me', {
        headers: { Authorization: 'Bearer mock-jwt-token' }
      })
    })
  })
})
```

### Phase 2: Resume Processing Pipeline (Weeks 3-4) ✅ COMPLETE

**Implementation Note**: The skill extraction and embedding generation functionality are integrated into `/api/services/resume_processor.py` rather than separate files. This provides a more cohesive implementation while maintaining all the planned functionality.

#### Objectives
* ✅ Implement resume upload and storage
* ✅ Extract and process resume text
* ✅ Generate embeddings for semantic matching
* ✅ Handle resume versioning

#### Skills Vocabulary
* File: `config/skills_vocab.csv`
* Columns: `skill,category,aliases,tags`
  * `skill`: canonical label (e.g., Python)
  * `category`: language|framework|db|cloud|tool
  * `aliases`: optional `|`-separated variants (e.g., PyTorch|torch)
  * `tags`: optional `|`-separated facets (e.g., backend|data)
* Loader: `scoring_engine/skills_matcher.py` consumes this at startup to normalize tokens; pipelines must treat this as the source of truth.

#### Tasks

1. **Resume API Endpoints**
   * Create `/api/routes/resumes.py` with upload, list, and retrieve endpoints
   * Implement `/api/models/resumes.py` with Supabase integration
   * Add resume processing service in `/api/services/resume_processor.py` (includes skill extraction and embedding generation)

2. **File Processing Pipeline**
   * Supabase Storage integration in `/api/services/storage.py`
   * PDF text extraction using pdfminer.six
   * Multi-stage skill extraction integrated in `/api/services/resume_processor.py`:
     * Stage 1: Dictionary/fuzzy matching with rapidfuzz (fast, cheap)
     * Stage 2: Retrieve candidates via embeddings (if coverage < 70%)
     * Stage 3: OpenAI function calling with closed-world constraint
     * Stage 4: Validate and merge with Pydantic schemas
   * SHA256 hashing for deduplication and versioning

3. **Embedding Generation System**
   * OpenAI API integration in `/api/services/resume_processor.py` (generate_embedding method)
   * Skill extraction features:
     * Evidence spans (character offsets) for UI highlighting
     * Confidence scores (0-1) for each extracted skill
     * Years of experience extraction when mentioned
     * Strict gating to skills vocabulary (no hallucinated skills)
   * Batch processing script in `/scripts/generate_embeddings.py`
   * Caching system in `/data/embeddings/` directory
   * Error handling and retry logic with exponential backoff

4. **Skill Extraction Configuration**
   * Schema definition in `/config/schemas/skills.json`:
     * skill_id (required, must exist in vocabulary)
     * evidence_span [start, end] character offsets
     * confidence (0-1 float)
     * extraction_method (dictionary|fuzzy|llm|onnx)
   * Prompt template in `/config/prompts/skill_extraction.txt`
   * Skills vocabulary remains at `/config/skills_vocab.csv`

5. **Quality Metrics & Validation**
   * Extraction metrics tracked per resume:
     * Coverage percentage of expected skills
     * Average confidence scores
     * Method distribution (dict vs fuzzy vs LLM)
   * Optional ONNX model for offline/low-latency mode
   * Metrics hooks ready for W&B integration (Phase 4)

6. **Budget Optimization**
   * Two-stage extraction to minimize LLM calls:
     * Run cheap dictionary/fuzzy pass first
     * Only call LLM if coverage < 70% threshold
     * Log cost savings for monitoring

#### Backend Acceptance Tests

```python
# tests/api/test_resumes.py
def test_resume_upload():
    """User can upload PDF resume to /api/v1/resumes"""
    with open("tests/fixtures/test_resume.pdf", "rb") as f:
        response = client.post("/api/v1/resumes", 
            headers=auth_headers,
            files={"file": ("resume.pdf", f, "application/pdf")}
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "resume.pdf"
    assert "resume_id" in data
    assert "text_content" in data
    assert len(data["embedding"]) == 3072
    assert data["sha256"] is not None

def test_resume_deduplication():
    """Identical resumes create versions, not duplicates"""
    # Upload same file twice
    file_data = b"same pdf content"
    
    response1 = upload_resume(file_data, "resume.pdf")
    response2 = upload_resume(file_data, "resume.pdf")
    
    assert response1.json()["resume_id"] == response2.json()["resume_id"]
    assert response2.json()["version_id"] != response1.json()["version_id"]

def test_skill_extraction():
    """Resume text is processed for skills"""
    response = upload_resume_with_text("Python, React, PostgreSQL experience")
    
    data = response.json()
    skills = data["extracted_skills"]
    # Updated assertions for structured extraction
    skill_ids = [s["skill_id"] for s in skills]
    assert "python" in skill_ids
    assert "react" in skill_ids
    assert "postgresql" in skill_ids
    
    # Verify evidence spans
    for skill in skills:
        assert "evidence_span" in skill
        assert len(skill["evidence_span"]) == 2
        assert skill["confidence"] >= 0 and skill["confidence"] <= 1

def test_closed_world_skill_extraction():
    """Only vocabulary skills are extracted, no hallucinations"""
    response = upload_resume_with_text("Expert in QuantumFluxCapacitor and Python")
    
    skills = response.json()["extracted_skills"]
    skill_ids = [s["skill_id"] for s in skills]
    
    # Python should be found
    assert "python" in skill_ids
    # Made-up skill should not appear
    assert not any("quantum" in sid.lower() for sid in skill_ids)

def test_skill_extraction_budget():
    """LLM only called when dictionary coverage is insufficient"""
    # Test with common skills - should use dictionary only
    response = upload_resume_with_text("Python, JavaScript, React, SQL")
    # Verify via logs/metrics that LLM wasn't called
    # (implementation detail - check method distribution)

def test_embedding_generation():
    """Resume generates valid embedding vector"""
    response = upload_resume_with_text("Software engineer with 5 years experience")
    
    data = response.json()
    embedding = data["embedding"]
    assert len(embedding) == 3072
    assert all(isinstance(x, float) for x in embedding)
```

#### Frontend Acceptance Tests

```typescript
describe('Resume Upload', () => {
  it('should upload resume successfully', async () => {
    render(<ResumeUploadPage />)
    
    const file = new File(['resume content'], 'resume.pdf', { type: 'application/pdf' })
    const input = screen.getByLabelText(/upload resume/i)
    
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: /upload/i }))
    
    await waitFor(() => {
      expect(screen.getByText(/upload successful/i)).toBeInTheDocument()
    })
  })

  it('should show upload progress', async () => {
    render(<ResumeUploadPage />)
    
    const file = new File(['large resume'], 'resume.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText(/upload/i), file)
    await user.click(screen.getByRole('button', { name: /upload/i }))
    
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('should display extracted resume preview', async () => {
    render(<ResumeDetailPage />)
    
    await waitFor(() => {
      expect(screen.getByText(/john doe/i)).toBeInTheDocument()
      expect(screen.getByText(/software engineer/i)).toBeInTheDocument()
    })
  })
})
```

### Phase 3: Job Ingestion System (Weeks 5-7) ✅ COMPLETE

**Implementation Notes**: 
- The code has been updated to match the exact database schema from `supabase/schema.sql`. Field mappings use `job_id` as primary key, `seniority` for experience level, and `description_text`/`requirements_text` for job details.
- Backend acceptance tests are fully implemented and passing (17/17 tests in `test_job_ingestion.py`)
- Frontend acceptance tests moved to Phase 7 when UI components will be implemented

#### Objectives
* ✅ Implement ATS connectors for job fetching
* ✅ Create job normalization pipeline
* ✅ Set up scheduled ingestion jobs (via script)
* ✅ Handle job versioning and deduplication

#### Tasks

1. **ATS Connector System**
   * ✅ Implement base connector in `/ingestion/connectors/base.py`
   * ✅ Create specific connectors: `/ingestion/connectors/greenhouse.py`, `lever.py`
   * ⚠️ `ashby.py` (not implemented - can add later)
   * ✅ Error handling and rate limiting with exponential backoff

2. **Data Processing Pipeline**
   * ✅ Job normalizer in `/ingestion/normalizers/normalizer.py`
   * ✅ Store jobs directly in Supabase database
   * ✅ Generate placeholder embeddings (OpenAI integration in Phase 4)

3. **Orchestration System**
   * ✅ Ingestion orchestrator in `/ingestion/orchestrator.py`
   * ✅ Command-line script in `/scripts/run_ingestion.py`
   * ✅ Job ingestion API endpoints in `/api/routes/jobs.py`
   * ✅ Monitoring and logging with structured output

#### Backend Acceptance Tests

```python
def test_greenhouse_connector():
    """Greenhouse connector fetches recent jobs"""
    connector = GreenhouseConnector("example.com")
    jobs = connector.fetch()
    
    assert len(jobs) > 0
    assert all("title" in job for job in jobs)
    assert all("posted_at" in job for job in jobs)
    assert all("job_url" in job for job in jobs)

def test_job_normalization():
    """Raw ATS data is normalized correctly"""
    raw_greenhouse_job = {
        "id": "123",
        "title": "Senior Software Engineer",
        "location": {"name": "San Francisco, CA"},
        "created_at": "2025-08-10T10:00:00Z",
        "absolute_url": "https://boards.greenhouse.io/company/jobs/123"
    }
    
    normalized = normalize_greenhouse_job(raw_greenhouse_job)
    
    assert normalized["job_id"] == "greenhouse-123"
    assert normalized["title"] == "Senior Software Engineer"
    assert normalized["location"] == "San Francisco, CA"
    assert normalized["posted_at"] == "2025-08-10T10:00:00Z"

def test_seven_day_filter():
    """Only jobs from last 7 days are processed"""
    old_job = {"posted_at": "2025-08-01T10:00:00Z"}
    new_job = {"posted_at": "2025-08-10T10:00:00Z"}
    
    connector = BaseConnector("test.com")
    filtered = connector.filter_last_7_days([old_job, new_job])
    
    assert len(filtered) == 1
    assert filtered[0] == new_job

def test_job_deduplication():
    """Identical jobs update existing records"""
    # First ingestion
    job_data = create_test_job(job_id="test-123", title="Engineer")
    response1 = client.post("/jobs/ingest", json=job_data)
    
    # Second ingestion with updated title
    updated_job = {**job_data, "title": "Senior Engineer"}
    response2 = client.post("/jobs/ingest", json=updated_job)
    
    # Should update existing record
    job = client.get("/jobs/test-123").json()
    assert job["title"] == "Senior Engineer"
    
    # Should create version history
    versions = client.get("/jobs/test-123/versions").json()
    assert len(versions) == 2
```

**Note**: Frontend acceptance tests for job listings have been moved to Phase 7 (Frontend UI Implementation) as they require actual UI components to be built first.

### Phase 4: Scoring Engine (Weeks 8-9)

#### Objectives
* Implement multi-factor scoring algorithm
* Create job ranking system
* Optimize vector similarity queries
* Add score explanations
* **Set up experiment tracking and optimization**

#### Tasks

1. **Core Scoring Engine**
   * Implement similarity calculation in `/scoring_engine/similarity.py`
   * Build skills matcher in `/scoring_engine/skills_matcher.py`
   * Create geographic scorer in `/scoring_engine/geo_scorer.py`
   * Develop final ranker in `/scoring_engine/ranker.py`

2. **API Integration & Performance**
   * Add scoring endpoints in `/api/routes/scoring.py`
   * Implement caching layer in `/api/utils/cache.py`
   * Vector index optimization for pgvector queries
   * Batch processing for large result sets

3. **Explainable AI Features**
   * Score breakdown service in `/api/services/score_explainer.py`
   * Feature importance calculation
   * Matching highlights in frontend components
   * Export score explanations in CSV format

4. **W&B Experiment Tracking**
   * Set up W&B project for experiment tracking
   * Create experiment service in `/api/services/experiments.py`
   * Implement scoring weight optimization with W&B Sweeps
   * Add dataset lineage tracking with W&B Artifacts
   * Create evaluation datasets in `/experiments/evaluation_datasets/`

#### Backend Acceptance Tests

```python
def test_job_ranking():
    """Jobs are ranked by relevance to resume"""
    # Upload resume
    resume_id = upload_test_resume("Python developer with 3 years experience")
    
    # Create test jobs
    python_job = create_job(title="Python Developer", skills=["python", "django"])
    java_job = create_job(title="Java Developer", skills=["java", "spring"])
    
    # Run scoring
    response = client.post(f"/scores/run", json={"resume_id": resume_id})
    scores = response.json()["results"]
    
    # Python job should rank higher
    python_score = next(s for s in scores if s["job_id"] == python_job["job_id"])
    java_score = next(s for s in scores if s["job_id"] == java_job["job_id"])
    
    assert python_score["total_score"] > java_score["total_score"]

def test_score_breakdown():
    """Score includes detailed factor breakdown"""
    resume_id = upload_test_resume("Senior Python developer in SF")
    job_id = create_job(title="Senior Python Engineer", location="San Francisco")
    
    response = client.post(f"/scores/run", json={"resume_id": resume_id})
    score = response.json()["results"][0]
    
    assert "cosine_sim" in score
    assert "skill_overlap" in score
    assert "seniority_fit" in score
    assert "geodist_km" in score
    assert "recency_bonus" in score
    assert score["total_score"] == (
        0.5 * score["cosine_sim"] +
        0.2 * score["skill_overlap"] +
        0.1 * score["seniority_fit"] +
        0.1 * (1.0 if score["geodist_km"] < 50 else 0.5) +
        0.1 * score["recency_bonus"]
    )

def test_vector_similarity_performance():
    """Vector similarity queries complete within SLA"""
    resume_id = upload_test_resume("Test resume")
    
    # Create 1000 test jobs
    for i in range(1000):
        create_job(title=f"Job {i}", description=f"Description {i}")
    
    start_time = time.time()
    response = client.post(f"/scores/run", json={"resume_id": resume_id})
    duration = time.time() - start_time
    
    assert duration < 2.0  # Under 2 seconds for 1000 jobs
    assert len(response.json()["results"]) <= 100  # Limited results

def test_wandb_experiment_tracking():
    """W&B experiment tracking works for scoring runs"""
    import wandb
    
    # Mock W&B run
    with wandb.init(project="job-ranker", mode="disabled"):
        resume_id = upload_test_resume("Test resume")
        response = client.post(f"/scores/run", json={
            "resume_id": resume_id,
            "experiment_config": {
                "cosine_weight": 0.5,
                "skill_weight": 0.2,
                "seniority_weight": 0.1
            }
        })
        
        assert response.status_code == 200
        # Should log metrics to W&B (tested in integration)

def test_scoring_weight_optimization():
    """Scoring weights can be optimized via sweep configuration"""
    sweep_config = {
        "method": "bayes",
        "parameters": {
            "cosine_weight": {"min": 0.3, "max": 0.7},
            "skill_weight": {"min": 0.1, "max": 0.3},
            "seniority_weight": {"min": 0.05, "max": 0.15}
        }
    }
    
    # Test that sweep config is valid
    assert "method" in sweep_config
    assert "parameters" in sweep_config
    assert sum(p["max"] for p in sweep_config["parameters"].values()) <= 1.0
```

#### Frontend Acceptance Tests

```typescript
describe('Job Scoring', () => {
  it('should display ranked job matches', async () => {
    render(<JobMatchesPage />)
    
    await waitFor(() => {
      const scores = screen.getAllByTestId('match-score')
      const values = scores.map(el => parseFloat(el.textContent || '0'))
      
      // Should be sorted descending
      expect(values).toEqual([...values].sort((a, b) => b - a))
    })
  })

  it('should show score breakdown on hover', async () => {
    render(<JobMatchesPage />)
    
    const scoreElement = screen.getByTestId('match-score')
    await user.hover(scoreElement)
    
    await waitFor(() => {
      expect(screen.getByText(/similarity: 0.85/i)).toBeInTheDocument()
      expect(screen.getByText(/skills: 0.70/i)).toBeInTheDocument()
      expect(screen.getByText(/seniority: 0.90/i)).toBeInTheDocument()
    })
  })

  it('should highlight matching skills', async () => {
    render(<JobDetailPage jobId="test-job" />)
    
    await waitFor(() => {
      expect(screen.getByText('Python')).toHaveClass('highlight-skill-match')
      expect(screen.getByText('React')).toHaveClass('highlight-skill-match')
    })
  })
})
```

### Phase 5: AI Research & Pitch Generation (Weeks 10-11)

#### Status: ✅ COMPLETE (Tasks 1-3), 🔄 DEFERRED (Task 4 - Weave/W&B)

#### Objectives
* ✅ Implement company research agent
* ✅ Create pitch generation system
* ✅ Ensure structured outputs and citations
* ✅ Add research caching and validation
* 🔄 **Set up LLM observability and evaluation** (Deferred)

#### Tasks

1. **AI Research System** ✅
   * Company research service in `/api/services/research.py`
   * Research prompts in `/config/prompts/company_research.txt`
   * JSON schema validation in `/config/schemas/company_research.json`
   * Structured OpenAI outputs with retry logic

2. **Pitch Generation Engine** ✅
   * Pitch generator service in `/api/services/pitch_generator.py`
   * Pitch prompts in `/config/prompts/pitch_generation.txt`
   * Template-based personalization system
   * Integration with research and scoring data

3. **Quality Assurance & Caching** ✅
   * Research caching in `/data/research/` with TTL management
   * Citation validation and fact-checking
   * Quality scoring for generated content
   * API endpoints in `/api/routes/research.py` and `/api/routes/pitch.py`

4. **Weave LLM Observability & Evaluation** 🔄 DEFERRED
   * Instrument LLM calls with `@weave.op` decorators
   * Create evaluation datasets in `/evals/datasets/`
   * Implement custom scorers in `/evals/research_eval.py` and `/evals/pitch_eval.py`
   * Set up side-by-side prompt comparisons and regression checks
   * Add cost, latency, and hallucination monitoring

#### Backend Acceptance Tests

```python
def test_company_research():
    """Company research returns structured data with sources"""
    response = client.post("/research/generate", json={"company_domain": "stripe.com"})
    research = response.json()
    
    # Validate schema compliance
    assert "company_domain" in research
    assert "competitors" in research
    assert "excellence" in research
    assert "shortcomings" in research
    assert "aspirations" in research
    
    # Validate sources
    for competitor in research["competitors"]:
        assert "name" in competitor
        assert "url" in competitor
        assert competitor["url"].startswith("http")
    
    for aspiration in research["aspirations"]:
        assert "statement" in aspiration
        assert "source_url" in aspiration

def test_pitch_generation():
    """Pitch generation creates personalized content"""
    resume_id = upload_test_resume("Senior engineer with fintech experience")
    job_id = create_job(company_domain="stripe.com", title="Staff Engineer")
    
    response = client.post("/pitch/generate", json={
        "resume_id": resume_id,
        "job_id": job_id
    })
    
    pitch = response.json()
    assert "headline" in pitch
    assert "opening" in pitch
    assert "two_minute_pitch" in pitch
    assert "bullet_points" in pitch
    
    # Should mention relevant experience
    assert "fintech" in pitch["two_minute_pitch"].lower()
    assert len(pitch["headline"]) <= 140

def test_research_caching():
    """Company research is cached to avoid redundant API calls"""
    # First request
    start_time = time.time()
    response1 = client.post("/research/generate", json={"company_domain": "stripe.com"})
    first_duration = time.time() - start_time
    
    # Second request (should be cached)
    start_time = time.time()
    response2 = client.post("/research/generate", json={"company_domain": "stripe.com"})
    second_duration = time.time() - start_time
    
    assert response1.json() == response2.json()
    assert second_duration < first_duration / 2  # Significantly faster

def test_weave_tracing():
    """Weave traces capture LLM calls for debugging"""
    import weave
    
    with weave.init(project_name="company-research"):
        response = client.post("/research/generate", json={"company_domain": "stripe.com"})
        
        assert response.status_code == 200
        # Weave should capture trace with inputs/outputs/costs
        # (verified in Weave UI during development)

def test_research_evaluation():
    """Research evaluation with custom scorers works"""
    from evals.research_eval import run_eval
    
    # Run evaluation on test dataset
    results = run_eval()
    
    assert "competitor_coverage" in results.summary
    assert "has_excellence" in results.summary
    assert "has_shortcomings" in results.summary
    assert results.summary["competitor_coverage"] > 0.7  # Quality threshold

def test_hallucination_detection():
    """Research output is checked for hallucinations"""
    response = client.post("/research/generate", json={"company_domain": "stripe.com"})
    research = response.json()
    
    # All URLs should be valid and reachable
    for competitor in research["competitors"]:
        assert competitor["url"].startswith("http")
        # Additional validation in production: URL reachability
    
    for aspiration in research["aspirations"]:
        assert aspiration["source_url"].startswith("http")
        # Additional validation: source verification
```

#### Frontend Acceptance Tests

```typescript
describe('AI Research & Pitches', () => {
  it('should display company research', async () => {
    render(<CompanyResearchPage companyDomain="stripe.com" />)
    
    await waitFor(() => {
      expect(screen.getByText(/competitors/i)).toBeInTheDocument()
      expect(screen.getByText(/strengths/i)).toBeInTheDocument()
      expect(screen.getByText(/opportunities/i)).toBeInTheDocument()
    })
  })

  it('should generate personalized pitch', async () => {
    render(<PitchGeneratorPage jobId="test-job" resumeId={123} />)
    
    await user.click(screen.getByRole('button', { name: /generate pitch/i }))
    
    await waitFor(() => {
      expect(screen.getByTestId('pitch-headline')).toBeInTheDocument()
      expect(screen.getByTestId('pitch-content')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /copy pitch/i })).toBeInTheDocument()
    })
  })

  it('should show research sources', async () => {
    render(<CompanyResearchPage companyDomain="stripe.com" />)
    
    const sourceLink = screen.getByRole('link', { name: /source/i })
    expect(sourceLink).toHaveAttribute('href', expect.stringMatching(/^https?:\/\//))
    expect(sourceLink).toHaveAttribute('target', '_blank')
  })
})
```

### Phase 6: Export & Reporting (Weeks 12-13)

#### Objectives
* Display job matches in sortable/filterable table UI
* Implement CSV export from matches table
* Add user-customizable skills vocabulary
* Create email notifications for new matches

#### Tasks

1. **Matches Table UI**
   * Sortable columns for all match data (score, company, title, location, date)
   * Filter by score threshold, location, posted date
   * Pagination for large result sets
   * Color-coded match scores (high/medium/low)

2. **CSV Export**
   * Download button exports visible table data
   * Include all scoring factors in export
   * Browser-native download (no external services)
   * Export history tracking

3. **Custom Skills Vocabulary**
   * Upload CSV with user's skill terminology
   * Required columns: skill, category, aliases, tags
   * Override default skills extraction
   * Replace on re-upload (interim solution)

4. **Notifications**
   * Email alerts for new high-scoring matches
   * Weekly digest reports
   * User notification preferences

#### Backend Acceptance Tests

```python
def test_csv_export():
    """User can export job matches as CSV from the API"""
    resume_id = upload_test_resume("Test resume")
    run_scoring(resume_id)
    
    response = client.get("/api/v1/scores/export?resume_id={resume_id}", 
                         headers=auth_headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
    assert "company,title,location,total_score" in response.text
    assert response.headers["content-disposition"].startswith("attachment")

def test_custom_skills_vocab_upload():
    """User can upload custom skills vocabulary CSV"""
    csv_content = """skill,category,aliases,tags
Python,Programming,py|python3,backend
Kubernetes,DevOps,k8s|k8,container"""
    
    response = client.post("/api/v1/resumes/skills-vocab",
                          files={"file": ("skills.csv", csv_content)},
                          headers=auth_headers)
    
    assert response.status_code == 200
    
    # Process resume with custom vocab
    resume_id = upload_test_resume("Has experience with k8s and py")
    skills = extract_skills(resume_id)
    
    assert "Kubernetes" in skills  # Matched via alias "k8s"
    assert "Python" in skills  # Matched via alias "py"

def test_email_notifications():
    """Users receive email alerts for new high-scoring matches"""
    user_id = create_test_user(email="test@example.com")
    resume_id = upload_resume_for_user(user_id)
    
    # Create high-scoring job (>0.7 score)
    job_id = create_job(title="Perfect Match Job")
    
    # Trigger scoring
    run_scoring(resume_id)
    
    # Check email was sent
    emails = get_sent_emails()
    user_emails = [e for e in emails if e["to"] == "test@example.com"]
    assert len(user_emails) > 0
    assert "new job match" in user_emails[0]["subject"].lower()
```

#### Frontend Acceptance Tests

```typescript
describe('Matches Table', () => {
  it('displays sortable table of job matches', async () => {
    render(<MatchesPage />)
    
    // Table headers are clickable for sorting
    const scoreHeader = screen.getByText('Match Score')
    fireEvent.click(scoreHeader)
    
    // Verify sorted by score descending
    const scores = screen.getAllByTestId('match-score')
    expect(scores[0]).toHaveTextContent('95%')
  })
  
  it('allows CSV download of visible matches', async () => {
    render(<MatchesPage />)
    
    const downloadBtn = screen.getByText('Download CSV')
    fireEvent.click(downloadBtn)
    
    // Verify download initiated
    expect(mockDownload).toHaveBeenCalledWith(
      expect.stringContaining('company,title,location,total_score'),
      expect.stringContaining('.csv')
    )
  })
})
```

## Testing Strategy

### Unit Tests (`/tests`)
* **Coverage Target**: 90%+ for core business logic
* **Structure**:
  * `/tests/api/` - API endpoint tests
  * `/tests/scoring_engine/` - Scoring algorithm tests  
  * `/tests/ingestion/` - Data ingestion tests
  * `/tests/fixtures/` - Test data and fixtures
* **Tools**: pytest, pytest-cov, factory-boy for fixtures
* **Focus Areas**: Scoring algorithms, data normalization, API serialization

### Integration Tests (`/tests/integration`)
* **Database**: Test RLS policies, triggers, and pgvector queries
* **External APIs**: Mock ATS and OpenAI responses with VCR.py
* **Auth Flow**: Supabase JWT verification and user permissions
* **Data Pipeline**: End-to-end ingestion → processing → scoring flow

### Frontend Tests (`/dashboard/src/__tests__`)
* **Component Tests**: React Testing Library for UI components
* **Integration**: API calls and Supabase Auth integration
* **E2E Tests**: Playwright for critical user journeys
* **Structure**:
  * `/__tests__/components/` - Component unit tests
  * `/__tests__/pages/` - Page integration tests
  * `/e2e/` - End-to-end test scenarios

### Performance Tests
* **Load Testing**: 100 concurrent users, 1000+ job database
* **Vector Queries**: <2s response time for pgvector similarity search
* **Memory Usage**: <512MB per FastAPI worker process
* **Embedding Generation**: Batch processing benchmarks

## Quality Gates

### Code Quality
* **Linting**: ESLint, Black, isort
* **Type Checking**: TypeScript strict mode, mypy
* **Security**: Bandit, npm audit, Supabase security checks

### Performance Benchmarks
* **API Response Time**: p95 < 500ms for CRUD operations
* **Vector Search**: p95 < 2s for similarity queries  
* **File Upload**: Support 10MB PDFs with <30s processing

### Security Requirements
* **Authentication**: Multi-factor authentication support
* **Data Encryption**: TLS 1.3, encrypted storage at rest
* **Privacy**: GDPR compliance, data export/deletion

## Deployment Strategy

### Staging Environment
* **Database**: Supabase staging project with test data
* **Frontend**: Vercel preview deployments
* **Backend**: Railway staging environment
* **Testing**: Automated E2E test suite

### Production Deployment
* **Blue-Green**: Zero-downtime deployments
* **Database Migrations**: Automated with rollback capability
* **Monitoring**: Error tracking, performance metrics
* **Backups**: Daily database backups with 30-day retention

## Success Metrics

### Technical Metrics
* **API Uptime**: 99.9%
* **Response Time**: p95 < 500ms
* **Error Rate**: <0.1% for critical paths
* **Test Coverage**: >90% for backend, >85% for frontend

### Business Metrics
* **User Engagement**: 70% of users upload resume within 7 days
* **Match Quality**: Average score >0.7 for top 10 results
* **Export Usage**: 40% of users export results within 30 days
* **Research Accuracy**: 90% of research claims have valid citations

## Risk Mitigation

### Technical Risks
* **API Rate Limits**: Implement exponential backoff and request queuing
* **Vector Search Performance**: Monitor query times, add indexes proactively
* **OpenAI Costs**: Set spending limits, cache embeddings aggressively

### Business Risks
* **ATS API Changes**: Version all connector interfaces, monitor for breaking changes
* **Data Quality**: Implement validation rules, manual review processes
* **User Privacy**: Regular security audits, minimize data collection

### Phase 7: Frontend UI Implementation (Weeks 14-15)

#### Objectives
* Implement actual UI components for job listings
* Create interactive dashboards
* Build responsive layouts
* Add user interaction features

#### Tasks

1. **Job Listing Components**
   * Create `/dashboard/src/components/JobListingsPage.tsx`
   * Implement job card components
   * Add filtering and sorting UI
   * Create job detail views

2. **Dashboard Pages**
   * Build main dashboard with metrics
   * Create resume management interface
   * Implement scoring visualization
   * Add export functionality UI

#### Frontend Acceptance Tests (from Phase 3)

```typescript
describe('Job Listings', () => {
  it('should display recent job postings', async () => {
    render(<JobListingsPage />)
    
    await waitFor(() => {
      expect(screen.getByText(/senior software engineer/i)).toBeInTheDocument()
      expect(screen.getByText(/posted 2 days ago/i)).toBeInTheDocument()
    })
  })

  it('should filter by company', async () => {
    render(<JobListingsPage />)
    
    await user.selectOptions(screen.getByLabelText(/company/i), 'ExampleCorp')
    
    await waitFor(() => {
      const jobs = screen.getAllByTestId('job-card')
      expect(jobs.every(job => 
        job.textContent?.includes('ExampleCorp')
      )).toBe(true)
    })
  })

  it('should show job details on click', async () => {
    render(<JobListingsPage />)
    
    await user.click(screen.getByText(/senior software engineer/i))
    
    await waitFor(() => {
      expect(screen.getByText(/job description/i)).toBeInTheDocument()
      expect(screen.getByText(/apply now/i)).toBeInTheDocument()
    })
  })
})
```

## Next Steps

After completing Phase 7, consider these enhancements:

### Advanced Features
* **Skills Assessment**: Interactive skill validation
* **Interview Prep**: AI-powered interview questions
* **Salary Analytics**: Market rate analysis
* **Application Tracking**: Status monitoring across platforms

### Scalability Improvements
* **Microservices**: Split monolith into focused services
* **Event Streaming**: Real-time job updates via WebSockets
* **Geographic Expansion**: Multi-region deployment
* **Enterprise Features**: Team accounts, admin dashboards

This development plan provides a structured approach to building a production-ready career jobs platform with robust testing, clear acceptance criteria, and measurable success metrics.
