# Testing Notes

## Current Test Status (Updated 2025-08-26)

### Overall Progress

- **Phase 1 (Foundation & Authentication)**: ✅ COMPLETE
- **Phase 2 (Resume Processing)**: ✅ COMPLETE  
- **Phase 3 (Job Ingestion)**: ✅ COMPLETE
- **Phase 4 (Scoring Engine)**: ✅ COMPLETE
- **Phase 5 (AI Research & Pitch)**: ✅ COMPLETE (without Weave)
- **Phase 6 (Export System)**: 🔄 TODO
- **Phase 7 (Frontend UI)**: 🔄 TODO

### Test Summary: 77/77 Tests Passing ✅

All tests are now passing including Phase 5 AI Research & Pitch Generation tests.

## Phase 1 Test Status

### Test Results Summary (2025-08-25)

#### ✅ All Authentication Tests Passing (12/12)

- **Health Check Tests**: API health endpoint and root endpoint work correctly
- **JWT Auth Tests**: Proper mocking with Mock(spec=JWTAuthService) fixed all issues
- **Configuration Tests**: Settings load properly with Pydantic v2 compatibility
- **Environment Variables**: All required environment variables are detected
- **Token Verification**: Valid, expired, and wrong audience tokens handled correctly
- **Protected Endpoints**: Authentication properly enforced

### Key Fixes Applied

1. **JWT Mocking Fix**: Used `Mock(spec=JWTAuthService)` to properly mock the auth service
2. **Test Reorganization**: Created new test file with proper mocking structure
3. **Datetime Updates**: Fixed deprecation warnings by using `timezone.utc`

### Config Fixes Applied

- Fixed `BaseSettings` import to use `pydantic_settings` (Pydantic v2 compatibility)
- Updated Settings class to use `model_config` instead of nested `Config` class
- Added `extra="ignore"` to handle additional environment variables (WANDB_*, etc.)
- Changed `datetime.utcnow()` deprecation warnings (Python 3.13) - to be fixed in future update

### Running Tests

```bash
# Run all auth tests
pytest tests/api/test_auth.py -v

# Run only passing tests
pytest tests/api/test_auth.py::TestHealthCheck -v
pytest tests/api/test_auth.py::TestConfigLoading -v

# Run with coverage
pytest tests/api/test_auth.py --cov=api --cov-report=term-missing
```

### Future Improvements

1. **Integration Tests**: Add integration tests with real Supabase test project
2. **JWT Mock Library**: Use a library like `python-jose` to create properly formatted test JWTs
3. **E2E Tests**: Add end-to-end tests that test the full auth flow
4. **Update datetime usage**: Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` for Python 3.13

## Phase 2 Test Status

### Resume Processing Tests (Completed 2025-08-25)

#### ✅ All Resume Tests Passing (11/11)

- **PDF/DOCX/TXT extraction**: All file types handled correctly
- **Text extraction**: Document parsing works for all formats
- **Skill extraction**: Multi-stage pipeline with fuzzy matching working
- **Years experience**: Regex patterns fixed to handle "3+ years" format
- **Span finding**: Character offset detection accurate
- **Embedding generation**: OpenAI integration properly mocked
- **Skills vocabulary**: CSV loading and alias mapping functional
- **Unsupported file types**: Proper error handling with async mocks
- **Integration test**: Complete upload flow tested

### CI/CD Updates (2025-08-25)

#### Fixed Issues

- ✅ **Test file discovery**: Removed `test_*.py` patterns from `.gitignore`
- ✅ **Python formatting**: Applied Black and isort to all Python files
- ✅ **CodeRabbit config**: Fixed YAML parsing error (path_filters format)
- ✅ **Workflow triggers**: Removed workflow files from path triggers
- ✅ **Test collection**: Tests now properly discovered in CI

#### Current CI Status

- **Python CI**: Linting passes, tests run with known failures
- **Next.js CI**: Configured but skips when no dashboard changes
- **CodeRabbit**: Successfully reviewing PRs with fixed config

## Phase 3 Test Status

### Job Ingestion Tests (Completed 2025-08-26)

#### ✅ All Job Ingestion Tests Passing (17/17)

- **Job Normalization**: Title normalization, experience level inference working
- **Employment Type**: Full Time, Contract, Internship normalization functional
- **Remote Type**: Remote, Hybrid, On Site detection accurate
- **Skill Extraction**: Extracts skills from job descriptions and requirements
- **Salary Normalization**: Swaps reversed min/max, removes unrealistic values
- **Greenhouse Connector**: Fetches and parses jobs correctly with mocking
- **Lever Connector**: Handles Lever API format properly
- **Orchestration**: Ingestion, deduplication, and embedding updates work
- **Schema Compliance**: All field names match database schema (job_id, seniority, description_text, etc.)

### Key Fixes Applied

1. **Schema Alignment**: Fixed all database field references (id → job_id, experience_level → seniority)
2. **Async Handling**: Properly mocked async methods with AsyncMock
3. **Test Data**: Updated mock data to match actual schema structure
4. **Cleanup Method**: Updated cleanup_expired_jobs to return 0 (placeholder implementation)

### Running Phase 3 Tests

```bash
# Run all job ingestion tests
pytest tests/test_job_ingestion.py -v

# Run acceptance tests
pytest tests/test_job_ingestion_acceptance.py -v

# Run with coverage
pytest tests/test_job_ingestion.py --cov=ingestion --cov-report=term-missing
```

### API Endpoints Tested

- `GET /api/v1/jobs` - List jobs with filters
- `GET /api/v1/jobs/{job_id}` - Get specific job
- `POST /api/v1/jobs/search` - Search jobs with advanced filters
- `GET /api/v1/jobs/similar/{job_id}` - Find similar jobs
- `GET /api/v1/jobs/stats/summary` - Job statistics
- `POST /api/v1/jobs/ingest` - Trigger ingestion (requires auth)

## Phase 4 Test Status

### Scoring Engine Tests (Completed 2025-08-26)

#### ✅ All Tests Passing (25/25)

- **Vector Similarity**: Cosine, Euclidean, dot product calculations
- **Skills Matching**: Exact, alias, and fuzzy matching with weighted scoring  
- **Geographic Scoring**: Distance-based scoring with remote/hybrid support
- **Job Ranking**: Multi-factor algorithm combining all scoring components
- **W&B Integration**: Experiment tracking and weight optimization
- **Score Explainer**: Human-readable insights and export functionality
- **API Endpoints**: `/scores/run`, `/scores/breakdown`, `/scores/export`, `/scores/optimize-weights`

### Key Features Implemented

1. **Multi-factor Scoring Algorithm**
   - Cosine similarity (50% weight)
   - Skills overlap (20% weight)
   - Seniority fit (10% weight)
   - Geographic score (10% weight)
   - Recency bonus (10% weight)

2. **Skills Matching Features**
   - Skill normalization and alias mapping
   - Fuzzy matching with configurable threshold
   - Weighted scoring for required vs preferred skills

3. **Geographic Scoring**
   - Geocoding support via Nominatim
   - Distance-based scoring with thresholds
   - Remote/hybrid position handling

4. **Experiment Tracking**
   - W&B integration for tracking scoring runs
   - Sweep configuration for weight optimization
   - Artifact storage for weights and datasets

### Running Phase 4 Tests

```bash
# Run scoring engine tests
pytest tests/test_scoring_engine.py -v

# Run with coverage
pytest tests/test_scoring_engine.py --cov=scoring_engine --cov=api/services --cov=api/routes/scoring --cov-report=term-missing
```

### API Endpoints to Test

- `POST /api/v1/scores/run` - Run batch scoring for resume
- `GET /api/v1/scores/breakdown/{job_id}` - Get detailed score breakdown
- `POST /api/v1/scores/export` - Export scores as CSV/JSON
- `POST /api/v1/scores/optimize-weights` - Create W&B optimization sweep

## Phase 5 Test Status

### AI Research & Pitch Generation Tests (Completed 2025-08-26)

#### ✅ All Tests Passing (12/12)

- **Company Research**: Structured data generation with JSON schema validation
- **Research Caching**: TTL-based caching to avoid redundant API calls
- **Pitch Generation**: Personalized content based on resume, job, and company data
- **Quality Scoring**: Scoring algorithms for both research and pitch quality
- **Email Templates**: Generation of email subject and body from pitch
- **Interview Prep**: Creation of interview preparation materials
- **URL Validation**: Basic hallucination detection via URL format checking

### Key Features Implemented

1. **Company Research Service**
   - OpenAI integration for structured data generation
   - JSON schema validation for output consistency
   - Caching with configurable TTL (default 1 week)
   - Quality scoring with improvement suggestions

2. **Pitch Generation Service**
   - Personalized pitches based on multiple data sources
   - Email template generation
   - Interview preparation materials
   - Quality scoring and validation

3. **API Endpoints**
   - `/api/v1/research/generate` - Generate company research
   - `/api/v1/research/{company_domain}` - Get cached research
   - `/api/v1/pitch/generate` - Generate personalized pitch
   - `/api/v1/pitch/email-template` - Create email from pitch
   - `/api/v1/pitch/interview-prep` - Generate interview materials

### What's NOT Implemented (Deferred)

- **Weave LLM Observability**: Tracing, evaluation datasets, custom scorers
- **W&B Integration**: Experiment tracking for LLM calls
- **Advanced Hallucination Detection**: URL reachability checks, fact verification

### Running Phase 5 Tests

```bash
# Run AI research tests
pytest tests/test_ai_research.py -v

# Run with coverage
pytest tests/test_ai_research.py --cov=api/services --cov=api/routes --cov-report=term-missing
```

## Phase 6-7 Testing Plans

- **Phase 6 Export System**: Test CSV generation, Google Drive integration, batch exports
- **Phase 7 Frontend**: Add React Testing Library tests, Playwright E2E tests, implement UI components
