# Career Jobs App - Project Structure Overview

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
  API-->|CSV| OUT1[(download)]
  API-->|Drive| OUT2[(Google Drive)]
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

### Backend
- **FastAPI**: Python web framework with automatic OpenAPI docs
- **Supabase**: Postgres database with Auth, Storage, and pgvector
- **OpenAI API**: Text embeddings and structured outputs
- **pdfminer.six**: PDF text extraction
- **rapidfuzz**: Fuzzy string matching for skill extraction
- **onnxruntime**: Optional offline NER model support
- **Weights & Biases**: Experiment tracking, hyperparameter optimization, dataset lineage
- **Weave**: LLM observability, evaluation, and quality monitoring

### Frontend
- **Next.js** (recommended): React framework with SSR support
- **Supabase Auth**: JWT-based authentication
- **Tailwind CSS**: Utility-first styling

### Infrastructure
- **Supabase**: Database, auth, storage, and edge functions
- **Vercel/Railway**: Frontend and backend deployment
- **Google Drive API**: Export functionality

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
POST /resumes              - Upload and process résumé
GET  /jobs/recent         - Last 7 days of job postings
POST /scores/run          - Generate scores for résumé vs jobs
GET  /research/{domain}   - Company research data
POST /pitch/generate      - Create personalized pitch
GET  /export/csv          - Download ranked results
POST /export/drive        - Upload to Google Drive
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

### Data Protection
- Row-Level Security (RLS) for multi-tenant isolation
- JWT verification via JWKS (no hardcoded secrets)
- File storage with SHA256 integrity checks
- User-namespaced storage paths

### API Security
- Rate limiting per user
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

### Planned Application Structure
Based on successful AIEWF patterns from civic-steward-visionboard:

```text
career-jobs-app/
├── [AIEWF files above...]
├── api/                   # 🔨 TO BE CREATED - FastAPI backend
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── models/           # Database models and schemas
│   │   ├── __init__.py
│   │   ├── jobs.py       # Job posting models
│   │   ├── resumes.py    # Resume models  
│   │   ├── scores.py     # Scoring models
│   │   └── research.py   # Company research models
│   ├── routes/           # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py       # Authentication routes
│   │   ├── jobs.py       # Job CRUD and search
│   │   ├── resumes.py    # Resume upload and processing
│   │   ├── scoring.py    # Job scoring and ranking
│   │   └── export.py     # CSV/Drive export
│   ├── services/         # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py       # JWT verification
│   │   ├── embeddings.py # OpenAI embedding service
│   │   ├── skill_extractor.py # Multi-stage skill extraction (dict/fuzzy/LLM)
│   │   ├── storage.py    # File storage service
│   │   └── research.py   # Company research service
│   ├── utils/            # Shared utilities
│   │   ├── __init__.py
│   │   ├── db.py         # Database connection
│   │   ├── cache.py      # Redis/memory caching
│   │   └── validators.py # Input validation
│   └── static/           # Static assets (favicons, etc.)
├── scoring_engine/        # 🔨 TO BE CREATED - Core matching logic
│   ├── __init__.py
│   ├── similarity.py     # Vector similarity calculations
│   ├── skills_matcher.py # Skill overlap analysis
│   ├── geo_scorer.py     # Geographic scoring
│   └── ranker.py         # Final ranking algorithm
├── ingestion/            # 🔨 TO BE CREATED - Job data ingestion
│   ├── __init__.py
│   ├── connectors/       # ATS-specific connectors
│   │   ├── __init__.py
│   │   ├── base.py       # Base connector class
│   │   ├── greenhouse.py # Greenhouse API
│   │   ├── lever.py      # Lever API
│   │   └── ashby.py      # Ashby API
│   ├── normalizers/      # Data transformation
│   │   ├── __init__.py
│   │   └── job_normalizer.py
│   └── orchestrator.py   # Ingestion scheduling/management
├── config/
│   └── skills_vocab.csv  # canonical skills list (see dev-plan.md / Phase 2)
├── dashboard/            # 🔨 TO BE CREATED - Next.js frontend
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/          # Next.js 13+ app directory
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx  # Dashboard home
│   │   │   ├── login/
│   │   │   ├── jobs/     # Job browsing/matching
│   │   │   └── profile/  # User profile/resume
│   │   ├── components/   # React components
│   │   │   ├── ui/       # Reusable UI components
│   │   │   ├── forms/    # Form components
│   │   │   └── layout/   # Layout components
│   │   ├── lib/          # Frontend utilities
│   │   │   ├── supabase.ts
│   │   │   ├── api.ts    # API client
│   │   │   └── utils.ts
│   │   └── types/        # TypeScript definitions
│   └── public/           # Static assets
├── config/               # 🔨 TO BE CREATED - Configuration management
│   ├── settings.yaml     # Application settings
│   ├── ats_sources.yaml  # ATS connector configurations
│   ├── prompts/          # AI prompt templates
│   │   ├── company_research.txt
│   │   ├── pitch_generation.txt
│   │   └── skill_extraction.txt
│   └── schemas/          # JSON schemas for validation
│       ├── job_posting.json
│       ├── resume.json
│       └── company_research.json
├── data/                 # 🔨 TO BE CREATED - Data management
│   ├── raw/              # Raw ATS data
│   ├── processed/        # Normalized job data
│   ├── embeddings/       # Cached embedding vectors
│   ├── research/         # Cached company research data
│   └── exports/          # Generated CSV exports
├── experiments/          # 🔨 TO BE CREATED - W&B experiment configs
│   ├── scoring_sweeps.yaml
│   ├── evaluation_datasets/
│   └── sweep_configs/
├── evals/                # 🔨 TO BE CREATED - Weave evaluations
│   ├── __init__.py
│   ├── research_eval.py  # Company research evaluation
│   ├── pitch_eval.py     # Pitch generation evaluation
│   ├── datasets/         # Evaluation datasets
│   └── scorers/          # Custom scoring functions
├── scripts/              # 🔨 TO BE CREATED - Utility scripts
│   ├── __init__.py
│   ├── seed_data.py      # Development data seeding
│   ├── migrate_data.py   # Data migration utilities
│   ├── generate_embeddings.py # Batch embedding generation
│   ├── run_experiments.py # W&B experiment runner
│   ├── run_evaluations.py # Weave evaluation runner
│   └── backup_data.py    # Data backup utilities
├── tests/                # 🔨 TO BE CREATED - Comprehensive testing
│   ├── __init__.py
│   ├── api/              # API endpoint tests
│   ├── scoring_engine/   # Scoring algorithm tests
│   ├── ingestion/        # Data ingestion tests
│   ├── integration/      # End-to-end tests
│   └── fixtures/         # Test data and fixtures
├── requirements.txt      # Python dependencies
├── package.json          # Node.js dependencies (for tools)
└── pytest.ini           # Python test configuration
```

### Structure Design Philosophy

#### Key Improvements from Civic-Steward Pattern

**1. Domain-Driven Top-Level Organization**
- `api/` - FastAPI backend (not nested under `/backend`)
- `scoring_engine/` - Core business logic (like `alignment_engine/`)
- `ingestion/` - Data ingestion pipeline
- `dashboard/` - Next.js frontend (like `dashboard/`)

**2. Configuration-Driven Development**
- `config/` directory with YAML files for settings
- Prompt templates in `config/prompts/`
- JSON schemas for validation
- ATS source configurations

**3. Comprehensive Data Management**
- Structured `data/` directory with processing stages
- Separation of raw, processed, and cached data
- Dedicated export directory

**4. Service-Oriented Architecture**
- Clear separation between models, routes, and services
- Dedicated utilities and caching layer
- Business logic isolated in domain engines

**5. Experiment Tracking & LLM Observability**
- W&B for scoring algorithm optimization and dataset lineage
- Weave for LLM call tracing, evaluation, and quality monitoring
- Automated regression detection and performance optimization

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
- **`seed_data.py`**: Development data seeding for testing
- **`migrate_data.py`**: Data migration utilities
- **`generate_embeddings.py`**: Batch embedding generation for performance
- **`run_experiments.py`**: W&B experiment orchestration and sweep management
- **`run_evaluations.py`**: Weave evaluation runner for LLM quality checks
- **`backup_data.py`**: Data backup and recovery utilities

##### Experiment Tracking (`/experiments` - W&B)
- **`scoring_sweeps.yaml`**: Bayesian optimization config for scoring weights
- **`evaluation_datasets/`**: Curated datasets for model performance testing
- **`sweep_configs/`**: Various sweep configurations for different optimization goals

##### LLM Evaluation (`/evals` - Weave)
- **`research_eval.py`**: Company research quality evaluation with custom scorers
- **`pitch_eval.py`**: Pitch generation quality and personalization evaluation  
- **`datasets/`**: Ground truth datasets for LLM evaluation
- **`scorers/`**: Custom scoring functions for hallucination, accuracy, and relevance

##### Makefile Targets
```bash
make setup    # Install development tools via bootstrap.sh
make dev      # Start/resume Daytona sandbox with dev.sh
make stop     # Stop all running sandboxes
make prune    # Delete archived sandboxes to free disk space
make lint-sh  # Shellcheck validation for shell scripts
make sweep    # Run W&B scoring weight optimization sweep
make eval     # Run Weave LLM evaluation suite
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
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend  
cd frontend
npm install
npm run dev

# Database
supabase start
supabase db reset
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