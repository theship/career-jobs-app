# Career Jobs App - Implementation TODO List

**For next Claude Code instance in Daytona sandbox**

## 🎯 Phase 1: Foundation & Authentication (START HERE)

### Critical Priority - Database Setup
1. ✅ **Set up Supabase project with pgvector extension** [DONE]
   - Create new Supabase project [DONE]
   - Enable pgvector extension in SQL editor: `CREATE EXTENSION IF NOT EXISTS vector;` [DONE]
   - Enable pgcrypto extension: `CREATE EXTENSION IF NOT EXISTS pgcrypto;` [DONE]
   - Enable `pgvector` and `pgcrypto` in the **extensions** schema (Supabase → Database → Extensions) [DONE]
   - Enable **JWT Signing Keys** (Supabase → Auth → JWT); note JWKS URL for backend [DONE]
   - Added  project URL and anon/service_role keys in root .env file for config  [DONE]

2. **Create database schema and migrations for core tables**
   - Implement all tables from `docs/project-structure-overview.md` (lines 85-173)
   - Core tables: `app_user`, `job_postings`, `job_postings_versions`, `resumes`, `resume_versions`, `scores`, `company_research`
   - Add pgvector columns for embeddings: `embedding vector(3072)`
   - Create SCD-2 versioning triggers for job_postings

3. **Implement Row-Level Security (RLS) policies**
   - Enable RLS on user-scoped tables: `resumes`, `resume_versions`, `scores`
   - Create policies for user data isolation (examples in docs/project-structure-overview.md lines 290-297)

### High Priority - Project Structure
4. **Create `/api` FastAPI project structure**
   ```
   api/
   ├── __init__.py
   ├── main.py
   ├── models/ (jobs.py, resumes.py, scores.py, research.py)
   ├── routes/ (auth.py, jobs.py, resumes.py, scoring.py, export.py)  
   ├── services/ (auth.py, embeddings.py, storage.py, research.py)
   ├── utils/ (db.py, cache.py, validators.py)
   └── static/
   ```

5. **Set up `/config` directory with settings and schemas**
   ```
   config/
   ├── settings.yaml
   ├── ats_sources.yaml
   ├── prompts/ (company_research.txt, pitch_generation.txt)
   └── schemas/ (job_posting.json, resume.json, company_research.json)
   ```

6. **Initialize other core directories**
   ```
   scoring_engine/ (similarity.py, skills_matcher.py, geo_scorer.py, ranker.py)
   ingestion/ (connectors/, normalizers/, orchestrator.py)
   data/ (raw/, processed/, embeddings/, exports/)
   tests/ (api/, scoring_engine/, ingestion/, fixtures/)
   scripts/ (seed_data.py, generate_embeddings.py)
   ```

### Medium Priority - Authentication
7. **Configure Supabase Auth project settings**
   - Set up email auth providers
   - Configure redirect URLs for development
   - Set JWT expiration and security settings

8. **Implement JWT authentication middleware in `/api/services/auth.py`**
   - JWKS verification from Supabase (see example in docs/project-structure-overview.md)
   - Implement JWT auth middleware in `/api/services/auth.py` using **JWKS**.
      -- JWKS: `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` (RS256/ES256)
      -- Ensure `aud=authenticated`; cache keys; no legacy HS256 secret
   - FastAPI dependency for protected routes
   - User extraction from JWT tokens

9. **Set up `/dashboard` Next.js frontend structure**
   ```
   dashboard/
   ├── src/
   │   ├── app/ (layout.tsx, page.tsx, login/, jobs/, profile/)
   │   ├── components/ (ui/, forms/, layout/)
   │   ├── lib/ (supabase.ts, api.ts, utils.ts)
   │   └── types/
   ├── package.json
   └── next.config.ts
   ```
   **IMPORTANT**: Follow the design system in `docs/FRONTEND_DESIGN_BRIEF.md`:
   - Dark mode first with pure black backgrounds
   - Mellow red accent color (#EF4444) for CTAs
   - Subtle gradients and glow effects
   - Card-based layouts with generous spacing
   - See `docs/preferred-UI-styling/` for reference screenshots

10. **Create Supabase client in `/dashboard/src/lib/supabase.ts`**
    - Initialize Supabase client with project URL and anon key
    - Set up auth helpers and session management

### Testing Priority
11. **Write initial authentication acceptance tests**
    - Backend tests: API health check, JWT verification, config loading (see docs/dev-plan.md lines 35-72)
    - Frontend tests: Registration, login redirect, session persistence (see docs/dev-plan.md lines 74-124)

## 📋 Phase 1 Success Criteria
- ✅ User can register/login via Supabase Auth in Next.js frontend
- ✅ JWT tokens properly protect FastAPI backend endpoints
- ✅ RLS policies prevent cross-user data access in database
- ✅ All authentication acceptance tests pass
- ✅ OpenAPI docs auto-generate at `/docs` endpoint
- ✅ Health check endpoint returns 200

## 🔄 After Phase 1 Complete

### Phase 2 prep

- Add `config/skills_vocab.csv` (columns: `skill,category,aliases,tags`) [DONE]
- Implement loader in `scoring_engine/skills_matcher.py` (normalize with aliases; tolerate empty cells)
- Seed small CSV (~50–150 rows) and a test ensuring "PyTorch"→"Python|PyTorch" normalization

### Phase 2: Resume Processing Pipeline (Weeks 3-4)
- Resume upload API endpoints (`/api/routes/resumes.py`)
- File processing with pdfminer.six for PDF text extraction
- **NEW: Multi-stage skill extraction** replacing spaCy:
  * Dictionary/fuzzy matching with rapidfuzz (Stage 1)
  * Embedding-based candidate retrieval (Stage 2) 
  * OpenAI function calling with closed-world constraint (Stage 3)
  * Pydantic validation and merging (Stage 4)
- **Skill extraction features**:
  * Evidence spans (character offsets) for UI highlighting
  * Confidence scores (0-1) for quality assessment
  * Years of experience extraction
  * Strict vocabulary gating (no hallucinated skills)
  * Budget optimization (LLM only if coverage < 70%)
- **Required configuration files**:
  * `/config/schemas/skills.json` - Pydantic validation schema
  * `/config/prompts/skill_extraction.txt` - LLM instruction template
  * `/config/skills_vocab.csv` - Already created, source of truth
- **Quality tracking**:
  * Extraction metrics per resume (coverage, confidence, method)
  * Optional ONNX model support for offline mode
  * Metrics hooks for W&B Phase 4 integration
- OpenAI embeddings integration
- Supabase Storage integration

### Phase 3: Job Ingestion System (Weeks 5-7)  
- ATS connector implementations (Greenhouse, Lever, Ashby)
- Job normalization pipeline
- Data orchestration and scheduling

### Phase 4: Scoring Engine (Weeks 8-9)
- Core scoring algorithms in `/scoring_engine/`
- Vector similarity with pgvector
- Multi-factor ranking system
- **W&B experiment tracking and scoring weight optimization**

### Phase 5: AI Research & Pitch Generation (Weeks 10-11)
- Company research with structured OpenAI outputs
- Personalized pitch generation
- Prompt template system
- **Weave LLM observability, evaluation, and quality monitoring**

### Phase 6: Export & Integration (Weeks 12-13)
- CSV export functionality
- Google Drive integration
- Email notifications

## 🛠️ Development Environment Commands

### Start Development Session
```bash
# In local terminal (Cursor)
make dev    # Starts Daytona sandbox

# In Daytona web terminal
claude      # Start Claude Code session
git pull    # Sync latest changes
```

### Key Development Commands in Daytona
```bash
# Backend development
cd api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend development  
cd dashboard
npm install
npm run dev

# Database operations (if using local Supabase)
supabase start
supabase db reset
supabase db push
```

### Testing Commands
```bash
# Backend tests
pytest tests/ -v --cov=api

# Frontend tests
cd dashboard
npm test
npm run test:e2e

# Linting
black api/
eslint dashboard/src
```

## 📚 Reference Documentation
- **Project Structure**: `docs/project-structure-overview.md`
- **Development Plan**: `docs/dev-plan.md` 
- **AIEWF Workflow**: `CLAUDE.md`
- **Architecture Diagrams**: `docs/project-structure-overview.md` (lines 18-60)

## 🔑 Environment Variables Needed
```bash
# In Daytona sandbox (injected via .daytona.yml)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ... 
SUPABASE_SERVICE_ROLE_KEY=eyJ...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-... (already injected)

# Phase 4+: W&B and Weave (add to .daytona.yml when needed)
WANDB_API_KEY=...        # For experiment tracking
WEAVE_PROJECT=career-jobs-app  # For LLM evaluation

# Frontend (.env.local)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

## 🚨 Critical Notes for Next Claude Code Session

1. **Start with Phase 1 tasks ONLY** - Don't jump ahead to resume processing or scoring
2. **Follow the exact directory structure** from civic-steward-visionboard pattern
3. **Use configuration-driven approach** - settings in `/config`, not hardcoded
4. **Test as you build** - Write tests for each component before moving on
5. **Document API endpoints** - FastAPI will auto-generate OpenAPI docs
6. **Use Supabase RLS** - Never bypass Row-Level Security policies
7. **Git commit regularly** - Use the collaborative attribution format

## 📝 Status Tracking
- [ ] Phase 1: Foundation & Authentication  
- [ ] Phase 2: Resume Processing Pipeline
- [ ] Phase 3: Job Ingestion System
- [ ] Phase 4: Scoring Engine  
- [ ] Phase 5: AI Research & Pitch Generation
- [ ] Phase 6: Export & Integration

---

**🤖 Generated by Claude Code (Claude <noreply@anthropic.com>) and Human - a true collaborative effort! 🤖🧑‍💻**