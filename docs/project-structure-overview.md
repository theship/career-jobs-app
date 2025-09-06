# Career Jobs App - Project Structure Overview

## Related Documentation
- **Development Plan & Status**: [`dev-plan.md`](./dev-plan.md)
- **Security Implementation**: [`security-overview.md`](./security-overview.md)
- **Quick Start Guide**: [`../README.md`](../README.md)
- **Dev Context**: [`../CLAUDE.md`](../CLAUDE.md)

## Overview

The Career Jobs App is a production-grade system that ingests company-hosted job postings, matches them against user résumés using semantic search and multi-factor scoring, generates company-specific research, and produces personalized pitch recommendations.

## Core Principles

- **Company-only sources**: No job board scraping - only official ATS APIs and company-hosted postings
- **7-day recency**: Focus on fresh opportunities posted in the last 7 days
- **Semantic matching**: Use embeddings and vector similarity for intelligent job-résumé matching
- **Transparent scoring**: Multi-factor algorithm with explainable features
- **Research-backed pitches**: AI-generated company research with verifiable sources
- **Data versioning**: Track changes to both job postings and résumés over time

## High-Level Architecture

```mermaid
flowchart TD
  U[User Dashboard (Supabase Auth)] -->|JWT| API[FastAPI Backend]
  subgraph Ingestion
    C1[Greenhouse]
    C2[Lever]
    C3[Ashby]
    C4[Pinpoint]
    C5[JazzHR]
    C6[Workday sites*]
  end
  C1-->ING[Connector Orchestrator]
  C2-->ING
  C3-->ING
  C4-->ING
  C5-->ING
  C6-->ING
  ING-->RAW[(job_postings_raw)]
  RAW-->ETL[Normalizer]
  ETL-->JOBS[(job_postings)]
  ETL-->JOBS_VER[(job_postings_versions)]
  U-->|upload| RSUM[Resume Upload]
  RSUM-->STOR[(Supabase Storage)]
  RSUM-->EXTRACT[pdfminer + skill extraction]
  EXTRACT-->EMB[Embed (OpenAI)]
  EMB-->RES[(resumes)]
  RES-->RESV[(resume_versions)]
  API-->SCORE[Scoring Engine]
  SCORE-->SCORES[(scores)]
  API-->RESEARCH[Company Research Agent]
  RESEARCH-->R[(company_research)]
  API-->|CSV Export| BROWSER[Browser Download]
  subgraph DB[Supabase Postgres + pgvector + RLS]
    JOBS
    JOBS_VER
    RES
    RESV
    SCORES
    R
  end
  API<-->DB
```

## Technology Stack

### Backend (Implemented)

- **FastAPI**: Python web framework with automatic OpenAPI docs
- **Supabase**: Postgres database with Auth, Storage, and pgvector
- **Redis** (REQUIRED): Caching, rate limiting, replay attack prevention, and security features
- **OpenAI API**: Text embeddings (text-embedding-3-large) and structured outputs
- **pdfminer.six**: PDF text extraction
- **python-docx**: DOCX file support
- **rapidfuzz**: Fuzzy string matching for skill extraction
- **Weights & Biases**: Experiment tracking and hyperparameter optimization (integrated)
- **HMAC Security**: Request signing and validation

### Frontend (Implemented)

- **Next.js 15.5.0**: React framework with App Router (latest stable version)
- **Supabase Auth**: JWT-based authentication with JWKS verification
- **Tailwind CSS**: Dark theme with red accents (as per design brief)
- **TypeScript**: Type-safe development
- **React Hooks**: State management with localStorage caching

### Infrastructure

- **Supabase**: Database, auth, storage, and edge functions
- **Vercel/Railway**: Frontend and backend deployment
- **Email Service**: Resend or SendGrid for notifications

## Data Model

### Core Tables

#### Users and Preferences

```sql
create table app_user (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferred_geolocation text,
  notes text,
  created_at timestamptz default now()
);
```

#### Job Postings (Current + History)

```sql
create table job_postings (
  job_id text primary key,
  company_name text not null,
  company_domain text not null,
  title text not null,
  location text,
  remote_type text, -- onsite|hybrid|remote
  posted_at timestamptz,
  updated_at timestamptz,
  department text,
  employment_type text,
  seniority text,
  salary_min numeric,
  salary_max numeric,
  currency text,
  job_url text not null,
  description_text text,
  requirements_text text,
  embedding vector(3072), -- text-embedding-3-large
  first_seen_at timestamptz default now(),
  last_seen_at timestamptz default now()
);

-- Type-2 history tracking
create table job_postings_versions (
  version_id bigserial primary key,
  job_id text not null,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  record jsonb not null
);
```

#### Résumés and Versions

```sql
create table resumes (
  resume_id bigserial primary key,
  user_id uuid not null references app_user(user_id),
  filename text not null,
  storage_path text not null,
  sha256 bytea not null,
  text_content text,
  embedding vector(3072),
  created_at timestamptz default now()
);

create table resume_versions (
  version_id bigserial primary key,
  resume_id bigint not null references resumes(resume_id),
  created_at timestamptz default now(),
  storage_path text not null,
  sha256 bytea not null
);

-- Skills extracted from resumes
create table resume_skills (
  id bigserial primary key,
  resume_id bigint not null references resumes(resume_id),
  skill_name text not null,
  confidence numeric not null default 1.0,
  created_at timestamptz default now(),
  unique(resume_id, skill_name)
);

-- User custom skills vocabulary
create table user_skills_vocab (
  id bigserial primary key,
  user_id uuid not null references app_user(user_id),
  vocab_data jsonb not null,
  skills_count integer,
  uploaded_at timestamptz default now(),
  unique(user_id)
);
```

#### Scoring and Research

```sql
create table scores (
  score_id bigserial primary key,
  user_id uuid not null references app_user(user_id),
  resume_id bigint not null references resumes(resume_id),
  job_id text not null references job_postings(job_id),
  cosine_sim numeric not null,
  skill_overlap numeric not null,
  seniority_fit numeric not null,
  geodist_km numeric,
  recency_bonus numeric not null,
  total_score numeric not null,
  created_at timestamptz default now()
);

create table company_research (
  company_domain text primary key,
  researched_at timestamptz not null default now(),
  research jsonb not null -- conforms to CompanyResearch schema
);
```

## Job Ingestion Connectors

### Supported ATS Systems

- **Greenhouse**: Job Board API (`boards/{board_id}/jobs`)
- **Lever**: Postings API and XML feeds
- **Ashby**: Public Job Postings API
- **Pinpoint**: JSON endpoint (`{company}.pinpointhq.com/postings.json`)
- **JazzHR**: JSON feed API
- **Workday**: Best-effort from `myworkdayjobs.com` sites (no uniform API)

### Connector Interface

```python
from abc import ABC, abstractmethod
from datetime import datetime, timezone

class JobConnector(ABC):
    def __init__(self, company_domain: str):
        self.company_domain = company_domain

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Fetch raw job postings from ATS"""
        pass

    def filter_last_7_days(self, jobs: list[dict], *, now=None) -> list[dict]:
        """Filter to jobs posted in last 7 days"""
        now = now or datetime.now(timezone.utc)
        cutoff = now.timestamp() - 7*24*3600
        def ts(job):
            return job.get("posted_at_ts") or job.get("first_seen_ts", 0)
        return [j for j in jobs if ts(j) >= cutoff]
```

## Scoring Algorithm

### Multi-Factor Scoring

```python
total_score = 0.50 * cosine_similarity +
              0.20 * skill_overlap +
              0.10 * seniority_fit +
              0.10 * geo_factor +
              0.10 * recency_bonus
```

### Feature Definitions

- **Cosine Similarity**: Vector similarity between job description and résumé embeddings
- **Skill Overlap**: Jaccard similarity of normalized skills
- **Seniority Fit**: Match between résumé level and job requirements
- **Geo Factor**: Distance-based scoring (neutral for remote roles)
- **Recency Bonus**: Exponential decay from posting date

## AI-Powered Research & Pitches

### Company Research Schema

```json
{
  "company_domain": "string",
  "competitors": [{"name": "string", "url": "uri"}],
  "comparison": [{"topic": "string", "direction": "↑|↓|=", "evidence_url": "uri"}],
  "excellence": ["string"],
  "shortcomings": ["string"],
  "aspirations": [{"statement": "string", "source_url": "uri"}]
}
```

### Pitch Generation

- Uses structured OpenAI outputs to ensure schema compliance
- Combines résumé strengths + company research + role requirements
- Produces 90-second pitch with headline, opening, and bullet points

## API Design

### Authentication

- Supabase Auth with JWT tokens
- JWKS-based verification (supports key rotation)
- Row-Level Security (RLS) for data isolation

### Key Endpoints

```http
# Authentication
GET  /api/v1/auth/me         - Get current user
GET  /api/v1/auth/session    - Check session status

# Resumes
POST /api/v1/resumes/upload  - Upload and process résumé
GET  /api/v1/resumes/        - List user resumes
PUT  /api/v1/resumes/{id}    - Update resume
DELETE /api/v1/resumes/{id}  - Delete resume
POST /api/v1/resumes/skills-vocab - Upload custom skills vocabulary
GET  /api/v1/resumes/skills-vocab - Get user's custom vocabulary

# Jobs
GET  /api/v1/jobs            - List job postings
POST /api/v1/jobs/search     - Search jobs
POST /api/v1/jobs/ingest     - Ingest new jobs from ATS
GET  /api/v1/jobs/{id}       - Get job details

# Scoring
POST /api/v1/scores/run      - Generate scores for résumé vs jobs
GET  /api/v1/scores/breakdown/{job_id} - Detailed score breakdown
POST /api/v1/scores/optimize-weights - Optimize scoring weights

# Research (Phase 5)
POST /api/v1/research/generate        - Generate company research
GET  /api/v1/research/{domain}        - Get cached research
GET  /api/v1/research/quality/{domain} - Research quality scores
POST /api/v1/research/cache/clear     - Clear research cache

# Pitch Generation (Phase 5)
POST /api/v1/pitch/generate      - Create personalized pitch
POST /api/v1/pitch/email-template - Generate email from pitch
POST /api/v1/pitch/interview-prep - Interview preparation guide
GET  /api/v1/pitch/quality/{id}  - Pitch quality assessment

# Export
GET  /api/v1/scores/export       - Download scores as CSV
```

### Response Format

```json
{
  "spec_version": "1.0",
  "user_id": "uuid",
  "resume_id": 123,
  "generated_at": "2025-08-11T20:04:00Z",
  "ranked_jobs": [{
    "job": {
      "job_id": "greenhouse-abc-123",
      "company_name": "ExampleCo",
      "title": "Staff Technical Writer",
      "location": "Remote - US",
      "job_url": "https://boards.greenhouse.io/..."
    },
    "scores": {
      "cosine_sim": 0.83,
      "skill_overlap": 0.67,
      "total_score": 0.83
    },
    "pitch": {
      "headline": "Close your AI infra doc gap in 90 days",
      "two_minute_pitch": "..."
    }
  }]
}
```

## Security Considerations

### Required Security Infrastructure

- **Redis**: REQUIRED for complete security implementation
  - Replay attack prevention via nonce tracking
  - Distributed rate limiting across multiple workers
  - Per-user API quota enforcement
  - Secure session management

### Data Protection

- Row-Level Security (RLS) for multi-tenant isolation
- JWT verification via JWKS (no hardcoded secrets)
- HMAC request signing for API authentication
- File storage with SHA256 integrity checks
- User-namespaced storage paths

### API Security

- Rate limiting per user (REQUIRES Redis for distribution)
- Input validation with Pydantic models
- Structured AI outputs to prevent injection
- Source URL verification for research claims

### Compliance

- Respect robots.txt and ATS terms of service
- No aggressive scraping - prefer official APIs
- Secure handling of uploaded documents
- User data export capabilities

## Project Structure

### Current Structure (AIEWF Setup)

```text
career-jobs-app/
├── .daytona.yml           # Daytona sandbox configuration
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore patterns + Claude/Daytona exclusions
├── Brewfile               # macOS dependencies (daytona, jq, gh, etc.)
├── Dockerfile.dev         # Development container image
├── Makefile               # Commands: dev, stop, prune, setup, lint-sh
├── README.md              # Quick start guide for hybrid workflow
├── CLAUDE.md              # AI development context and workflow notes
├── docs/
│   ├── dev-overview.md    # Detailed AIEWF documentation
│   ├── dev-plan.md        # Phased development plan with acceptance tests
│   └── project-structure-overview.md  # This file
└── scripts/               # AIEWF automation scripts
    ├── bootstrap.sh       # Initial setup script
    ├── coderabbit-smoke.js# CodeRabbit integration testing
    └── dev.sh             # Sandbox creation/resumption logic
```

### Actual Implementation Structure

Current implementation as of 2025-09-05:

```text
career-jobs-app/
├── [AIEWF files above...]
├── api/                   # ✅ IMPLEMENTED - FastAPI backend
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── models/           # Database models and schemas
│   │   ├── __init__.py
│   │   ├── resumes.py    # Resume models  
│   │   ├── security.py   # Security models (HMAC, rate limits)
│   │   └── users.py      # User models
│   ├── routes/           # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py       # Authentication routes
│   │   ├── jobs.py       # Job CRUD and search
│   │   ├── pitch.py      # Pitch generation endpoints
│   │   ├── pitch_history.py # Pitch history management
│   │   ├── research.py   # Company research endpoints
│   │   ├── resumes.py    # Resume upload and processing
│   │   └── scoring.py    # Job scoring, ranking, and CSV export
│   ├── services/         # Business logic layer
│   │   ├── __init__.py
│   │   ├── activity_logger.py # User activity tracking
│   │   ├── auth.py       # JWT/JWKS verification
│   │   ├── cache.py      # Redis caching implementation
│   │   ├── experiments.py # W&B experiment tracking
│   │   ├── pitch_generator.py # Pitch generation service
│   │   ├── research.py   # Company research service
│   │   ├── resume_processor.py # Resume processing & embeddings
│   │   ├── score_explainer.py # Score explanation service
│   │   └── storage.py    # Supabase storage service
│   ├── utils/            # Shared utilities
│   │   ├── __init__.py
│   │   ├── advanced_rate_limit.py # Advanced rate limiting
│   │   ├── config.py     # Application configuration
│   │   ├── database.py   # Supabase client connections
│   │   ├── hmac_security.py # HMAC request signing
│   │   ├── redis_client.py # Redis connection manager
│   │   ├── security.py   # Security utilities
│   │   └── vector_utils.py # Vector operations
│   └── static/           # (empty - no static assets yet)
├── scoring_engine/        # ✅ IMPLEMENTED - Core matching logic
│   ├── __init__.py
│   ├── similarity.py     # Vector similarity calculations
│   ├── skills_matcher.py # Skill overlap analysis
│   ├── geo_scorer.py     # Geographic scoring
│   └── ranker.py         # Final ranking algorithm
├── ingestion/            # ✅ IMPLEMENTED - Job data ingestion
│   ├── __init__.py
│   ├── connectors/       # ATS-specific connectors
│   │   ├── __init__.py
│   │   ├── base.py       # Base connector class
│   │   ├── greenhouse.py # Greenhouse API (authenticated)
│   │   ├── lever.py      # Lever API (authenticated)
│   │   ├── greenhouse_public.py # ✅ Public API (no auth needed)
│   │   ├── lever_public.py      # ✅ Public API (no auth needed)
│   │   └── ashby.py      # Ashby API (planned)
│   ├── normalizers/      # Data transformation
│   │   ├── __init__.py
│   │   └── normalizer.py # Job data normalizer
│   └── orchestrator.py   # Ingestion scheduling/management
├── dashboard/            # ✅ IMPLEMENTED - Next.js 15.5.0 frontend
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/          # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx  # Landing page
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx
│   │   │   ├── jobs/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── matches/
│   │   │   │   └── page.tsx
│   │   │   ├── profile/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── JobDetail/
│   │   │   │   ├── JobInfo.tsx
│   │   │   │   ├── MatchScore.tsx
│   │   │   │   └── PitchGenerator.tsx
│   │   │   ├── ui/
│   │   │   │   └── Modal.tsx
│   │   │   ├── MatchesTable.tsx
│   │   │   ├── ResumeUploadProgress.tsx
│   │   │   ├── SkillsVocabUpload.tsx
│   │   │   └── SkillsVocabularyUpload.tsx
│   │   ├── contexts/
│   │   │   └── NotificationContext.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts
│   │   │   ├── clear-sensitive-data.ts
│   │   │   ├── supabase.ts
│   │   │   └── utils.ts
│   │   ├── services/      # Service layer architecture
│   │   │   ├── auth.ts
│   │   │   ├── base.ts
│   │   │   ├── index.ts
│   │   │   ├── jobs.ts
│   │   │   ├── pitch.ts
│   │   │   ├── resume.ts
│   │   │   └── scoring.ts
│   │   └── types/
│   │       └── index.ts
│   └── public/           # Static assets
├── config/               # ✅ IMPLEMENTED - Configuration management
│   ├── ats_sources.yaml  # ATS connector configuration
│   ├── settings.yaml     # Application settings
│   ├── skills_vocab.csv  # Canonical skills list
│   ├── target_companies.csv # ✅ Company list for public API ingestion
│   ├── prompts/          # AI prompt templates
│   │   ├── company_research.txt
│   │   ├── pitch_generation.txt
│   │   └── skill_extraction.txt
│   └── schemas/          # JSON schemas for validation
│       └── company_research.json
├── data/                 # Data directories (created at runtime)
│   ├── embeddings/       # Cached embedding vectors
│   ├── exports/          # Generated CSV exports
│   └── research/         # Cached company research data
├── scripts/              # ✅ IMPLEMENTED - Utility scripts
│   ├── create_test_resume.py    # Test resume generator
│   ├── generate_job_embeddings.py # Batch embedding generation
│   ├── load_sample_jobs.py      # Sample data loader
│   ├── run_ingestion.py         # Manual ingestion trigger
│   ├── setup_test_user.py       # Test user setup
│   └── validate_dependencies.py # Dependency validator
├── tests/                # ✅ IMPLEMENTED - Comprehensive testing (77 tests)
│   ├── __init__.py
│   ├── conftest.py       # Pytest configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── test_auth.py  # Authentication tests
│   │   └── test_resume_integration.py
│   ├── test_ai_research.py      # AI research & pitch tests
│   ├── test_job_ingestion.py    # Job ingestion tests
│   ├── test_job_ingestion_acceptance.py
│   ├── test_resume_processing.py # Resume processing tests
│   └── test_scoring_engine.py   # Scoring engine tests
├── requirements.txt      # Python dependencies
├── package.json          # Node.js dependencies (for tools)
└── pytest.ini           # Python test configuration
```

### Structure Design Philosophy

#### Key Architectural Patterns

**1. Domain-Driven Top-Level Organization**

- `api/` - FastAPI backend with clear separation of concerns
- `scoring_engine/` - Core business logic for job matching
- `ingestion/` - Data ingestion pipeline for ATS systems
- `dashboard/` - Next.js frontend with App Router

**2. Configuration-Driven Development**

- `config/` directory with YAML files for settings
- Prompt templates in `config/prompts/`
- JSON schemas for validation
- Skills vocabulary CSV for customization

**3. Data Management**

- Structured `data/` directories created at runtime
- Caching strategy for embeddings and research
- Export functionality for CSV downloads

**4. Service-Oriented Architecture**

- Clear separation between models, routes, and services
- Dedicated utilities for security, caching, and database
- Business logic isolated in domain engines

**5. Experiment Tracking**

- W&B integration for scoring algorithm optimization
- Experiment service for tracking and dataset management
- Configurable scoring weights and thresholds

#### AIEWF Component Details

##### Development Environment Files

- **`.daytona.yml`**: Sandbox configuration with security policies, resource limits, and API key injection
- **`Dockerfile.dev`**: Pre-built development container with Node.js, Python, and development tools
- **`.env.example`**: Template for required environment variables (`DAYTONA_API_KEY`, `GH_PAT`, `ANTHROPIC_API_KEY`)
- **`Brewfile`**: macOS dependency management via Homebrew (daytona CLI, jq, gh, shellcheck)

##### Automation Scripts (`/scripts` - AIEWF)

- **`bootstrap.sh`**: One-time setup script for installing development dependencies
- **`dev.sh`**: Core script that handles sandbox creation, resumption, and state management
- **`coderabbit-smoke.js`**: Integration testing for CodeRabbit PR review automation

##### Utility Scripts (`/scripts` - Application)

The following scripts are implemented:
- **`create_test_resume.py`**: Generate test resumes for development
- **`generate_job_embeddings.py`**: Batch embedding generation for jobs
- **`load_sample_jobs.py`**: Load sample job data for testing
- **`run_ingestion.py`**: Manual trigger for job ingestion
- **`setup_test_user.py`**: Create test users in the system
- **`validate_dependencies.py`**: Check all required services are running

##### Makefile Targets

```bash
make setup    # Install development tools via bootstrap.sh
make dev      # Start/resume Daytona sandbox with dev.sh
make stop     # Stop all running sandboxes
make prune    # Delete archived sandboxes to free disk space
make lint-sh  # Shellcheck validation for shell scripts
```

##### Hybrid Development Workflow

This project uses a **hybrid Cursor + Daytona + Claude Code** approach:

1. **Cursor IDE (Local)**: Code exploration, git management, Claude Code integration
2. **Daytona Sandbox (Remote)**: Secure development environment with isolated execution
3. **Claude Code CLI**: AI-powered development assistant available in both environments
4. **CodeRabbit**: Automated PR reviews with security-first analysis

The AIEWF setup ensures:

- ✅ Secure API key management via environment injection
- ✅ Isolated development environment with network policies  
- ✅ Automated sandbox lifecycle management
- ✅ Integration with AI development tools
- ✅ CodeRabbit-enforced code quality standards

## Performance Considerations

### Database Optimization

- HNSW index on embedding columns for fast similarity search
- Composite indexes on frequently queried columns
- Partitioning for time-series data (job_postings_versions)

### Caching Strategy

- Embedding caching by content hash to avoid duplicate API calls
- Company research caching (TTL: 24 hours)
- Redis for session and rate limiting data

### Cost Management

- Monthly OpenAI API spend caps
- Batch processing for embeddings
- Efficient vector similarity queries with limits

## Monitoring & Observability

### Metrics

- API request latency and error rates
- Job ingestion success/failure rates
- Embedding generation costs
- User engagement metrics

### Logging

- Structured JSON logs
- API request/response correlation IDs
- ATS connector health checks
- AI model performance metrics

## Development Workflow

### Local Development

```bash
# Start Redis (REQUIRED)
redis-server  # or docker run -d -p 6379:6379 redis:7-alpine

# Backend
cd api
pip install -r requirements.txt
python -m uvicorn api.main:app --reload

# Frontend  
cd dashboard
npm install
npm run dev

# Database
supabase start
supabase db reset

# Verify all services
python scripts/validate_dependencies.py  # Checks Redis, Supabase, etc.
```

### Testing Strategy

- Unit tests for scoring algorithms
- Integration tests for ATS connectors
- End-to-end tests for user workflows
- Load testing for embedding operations

### CI/CD Pipeline

- Automated testing on PR creation
- Database migration validation
- Security scanning
- Deployment to staging/production

This architecture provides a solid foundation for a scalable, secure, and intelligent job matching platform that goes beyond simple keyword matching to deliver personalized, research-backed career opportunities.
