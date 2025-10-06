# Career Jobs App — Dev Quickstart

This repo is an experimen tools to create a fullstack appt using several AI, specifically ChatGPT to product requirements, Claude Code for the majority of implementation, Cursor and Daytona environments, and CodeRabbit for PR reviews. A final deploy pipeline wasn't part of this project, as the next project will be to design a development system using multiple AI subagents...


For full project architecture see **[`./docs/project-structure-overview.md`](./docs/project-structure-overview.md)**.  
For development planning and progress see **[`./docs/dev-plan.md`](./docs/dev-plan.md)**.  
For AIEWF workflow details see **[`./docs/dev-overview.md`](./docs/dev-overview.md)**.  

This README is the **short, practical guide** for getting the application running.

---

## First‑time setup (per machine)

### 1) Local setup
```bash
git clone git@github.com:theship/career-jobs-app.git
cd career-jobs-app
cp .env.example .env    # add API keys (see below)

# Install Redis (REQUIRED for security features)
# macOS:
brew install redis
brew services start redis

# Ubuntu/Debian:
# sudo apt-get install redis-server
# sudo systemctl start redis

# Docker alternative:
# docker run -d -p 6379:6379 --name redis redis:7-alpine

# Verify Redis is running
redis-cli ping  # Should return "PONG"

# Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# For AIEWF workflow (optional):
source .env
daytona login --api-key $DAYTONA_API_KEY
make setup              # installs daytona, jq, gh, shellcheck, node/pnpm (macOS: via Brewfile)
```

### Required Environment Variables
Add these to your `.env` file:
```bash
# Backend (.env)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
OPENAI_API_KEY=sk-...
REDIS_URL=redis://localhost:6379/0  # Required for security features
HMAC_SECRET=your-secret-key-here    # For request signing

# For AIEWF workflow (optional)
DAYTONA_API_KEY=your-daytona-key
GH_PAT=your-github-pat
ANTHROPIC_API_KEY=your-anthropic-key
```

### 2) Start Daytona sandbox and install Claude Code
```bash
make dev    # opens Web Terminal at https://22222-<id>.proxy.daytona.work
```

In the **Web Terminal** (first time per sandbox):
```bash
# Install Claude Code (secure method)
curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh
# Optionally verify checksum here, then:
sh /tmp/claude-install.sh

# API key is automatically available via sandbox environment
# No need to export manually - it's injected via .daytona.yml
```

Now you're ready for daily dev.

---

## Daily workflow

### 1) Code exploration with Cursor IDE (local)

Open the project in **Cursor IDE**:
```text
~/career-jobs-app/         ← Open this folder in Cursor
│   src/…
│   scripts/…
│   .daytona.yml
└─  .env
```

**Use Claude Code in Cursor for:**
- Code exploration and understanding: `Cmd/Ctrl + L` (Ask Claude about selected code)
- Planning changes with full codebase context
- Git operations: branches, commits, PRs through Cursor's UI
- Adding context to memory: `Cmd/Ctrl + Shift + P` → "Add to CLAUDE.md"
- Understanding codebase structure: `Cmd/Ctrl + Shift + P` → "Claude: Understand codebase"

### 2) Development work in Daytona sandbox

Start or resume your sandbox:
```bash
make dev    # opens Web Terminal at https://22222-<id>.proxy.daytona.work
```

In the **Web Terminal**, use **Claude Code for development work**:
```bash
# Start Claude Code session
claude

# In Claude Code (development work):
test -n "$GH_PAT" || echo "Warning: GH_PAT not set in sandbox env; see docs 'How the PAT is injected'"
git pull         # sync latest changes from Cursor
pnpm run dev     # run development server
# Claude Code edits files, runs tests, executes code, etc.
```

**Preview URL:** `https://3000-<id>.proxy.daytona.work` when dev server is running.

### 3) Hybrid workflow benefits

| **Environment**         | **Best Used For**                                              | **Claude Code Features**                                    |
| ----------------------- | ------------------------------------------------------------- | ----------------------------------------------------------- |
| **Cursor IDE (local)**  | Code exploration, understanding, git management              | Full codebase context, IntelliSense integration, shortcuts |
| **Daytona (remote)**    | Code execution, file modifications, testing, development     | Direct file system access, isolated execution, full CLI    |

> **Key insight:** Use both environments for their strengths - Cursor for exploration and planning, Daytona for actual development work.

#### Tip
Add a tiny alias in the sandbox:
>
> ```bash
> echo 'alias gp="git pull --ff-only"' >> ~/.bashrc && source ~/.bashrc
> ```
> Then just type `gp` after every local push.

### 4) Running the Application

#### Quick Service Status Check
```bash
# Check if services are running:
redis-cli ping                                      # Redis (should return "PONG")
curl -s http://localhost:8000/health | jq .         # Backend API
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000  # Frontend (should return 200)
```

#### Starting Services

##### 1. Redis (REQUIRED - Must be running first)
```bash
# Check if running
redis-cli ping  # Should return "PONG"

# If not running, start it:
brew services start redis        # macOS with Homebrew
# OR
sudo systemctl start redis       # Linux
# OR  
docker run -d -p 6379:6379 redis:7-alpine  # Docker
```

##### 2. Backend API Server
```bash
# Activate Python environment
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Check if running
curl -s http://localhost:8000/health | jq .

# If not running, start it:
python -m uvicorn api.main:app --reload --port 8000

# API will be available at:
# - http://localhost:8000
# - API docs: http://localhost:8000/docs
```

##### 3. Frontend Dashboard
```bash
# Navigate to dashboard directory
cd dashboard

# Check if running
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000

# If not running, start it:
npm install  # First time only
npm run dev

# Dashboard will be available at:
# - http://localhost:3000
```

#### Stopping Services
- **Redis**: `brew services stop redis` (or keep running, it's lightweight)
- **Backend**: Press `Ctrl+C` in the terminal running uvicorn
- **Frontend**: Press `Ctrl+C` in the terminal running npm


### 5) Pulling in new jobs data

To update the Database with New Jobs, use `/scripts/run_ingestion.py`. The ingestion script:

- Fetches jobs from configured ATS sources (Greenhouse, Lever, Ashby)
- Normalizes job data
- Generates embeddings using OpenAI
- Stores/updates jobs in the job_postings table
- Tracks last_seen_at timestamp for existing jobs
- Can optionally clean up duplicates and expired jobs

* Basic ingestion (fetches from all configured sources:
    `python scripts/run_ingestion.py`

* Fetch limited number of jobs (useful for testing:
    `python scripts/run_ingestion.py --limit 5`

* Fetch from specific sources only:
    `python scripts/run_ingestion.py --sources greenhouse lever`

* Run with cleanup (remove duplicates and expired jobs:
    `python scripts/run_ingestion.py --cleanup`

* Update embeddings for jobs without them:
    `python scripts/run_ingestion.py --update-embeddings`

* Dry run (fetch but don't store:
    `python scripts/run_ingestion.py --no-store`

* Verbose logging:
    `python scripts/run_ingestion.py -v`

### 6) Stop & cleanup Daytona sandbox

- Do nothing: sandbox **auto‑stops after 45 min idle**, then **auto‑archives 60 min later**.
- Or stop immediately when you're done:
  ```bash
  make stop
  ```

> **Note:** Claude Code installation persists in the sandbox until it's archived, so you only need to install it once per sandbox lifecycle.

---

## Where to run tests

- **Cursor IDE (exploration):** Quick unit tests locally for fast feedback
- **Daytona sandbox (main development):** `pytest` for backend tests in Claude Code sessions
- **CI (source of truth for PRs):** Full test suites; see `.github/workflows/`

### Current Test Status
- **Total Tests**: ✅ 77/77 tests passing
- **Backend Coverage**: Authentication, Resume Processing, Job Ingestion, Scoring Engine, AI Research & Pitch
- **Security Features**: Redis-based HMAC validation, rate limiting, replay attack prevention
- **Frontend**: Full UI implementation with Next.js 15.5.0

---

## Claude Code shortcuts in Cursor

- `Cmd/Ctrl + L`: Ask Claude about selected code
- `Cmd/Ctrl + I`: Inline edit with Claude  
- `Cmd/Ctrl + K`: Generate code with Claude
- `Cmd/Ctrl + Shift + P` → "Add to CLAUDE.md": Save context for future sessions
- `Cmd/Ctrl + Shift + P` → "Claude: Understand codebase": Get code structure analysis

---

Need the rationale, caveats, PAT setup, or CI examples? Read **[`./docs/dev-overview.md`](./docs/dev-overview.md)**.


---

## Prebuilt dev image (faster cold-starts)

We publish a dev image to GHCR via **.github/workflows/build-dev-image.yml**.
First time only, trigger the build so the image exists:

```bash
git commit --allow-empty -m "build: seed dev image"
git push
```

Once the workflow completes, `make dev` will start much faster (the sandbox pulls `ghcr.io/<org>/<repo>:dev`).

---

## Project Status

### ✅ Completed Features
- **All 7 Development Phases Complete** - See [`docs/dev-plan.md`](./docs/dev-plan.md) for details
- **Backend API**: FastAPI with comprehensive route structure
- **Frontend**: Next.js 15.5.0 with dark theme UI
- **Database**: Supabase with pgvector for semantic search
- **Security**: Redis-based HMAC validation, rate limiting, replay attack prevention
- **AI Integration**: OpenAI for embeddings, company research, and pitch generation
- **Testing**: 77 tests passing across all components

### 🔄 Recent Improvements
- [x] Implement job ingestion with proper embedding service ✅ (OpenAI embeddings working)
- [x] Add public API connectors for Lever/Greenhouse ✅ (no keys required)
- [x] Implement proper RLS security for job data ✅ (service-role only access)

### 🔄 Future Enhancements
- **Email Notifications**: Integrate Resend/SendGrid for match alerts
- **Weave Integration**: Add LLM observability for production monitoring
- **Next.js ESLint Migration**: Required for Next.js 16 compatibility
- **Redis HA**: Add Sentinel or cluster for production scaling
- **Job Cleanup Logic**: Add cleanup based on business rules
- **Export System Tests**: Implement Phase 6 tests
- **API Documentation**: Add comprehensive API docs

### 📚 Documentation
- **Architecture Overview**: [`docs/project-structure-overview.md`](./docs/project-structure-overview.md)
- **Development Plan**: [`docs/dev-plan.md`](./docs/dev-plan.md)
- **Security Details**: [`docs/security-overview.md`](./docs/security-overview.md)
- **AIEWF Workflow**: [`docs/dev-overview.md`](./docs/dev-overview.md)

