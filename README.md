# Career Jobs App — Dev Quickstart

For full details see **[`./docs/dev-overview.md`](./docs/dev-overview.md)**. This README is the **short, practical guide** for the hybrid Cursor + Daytona + Claude Code workflow you'll use day‑to‑day.

---

## First‑time setup (per machine)

### 1) Local setup
```bash
git clone git@github.com:theship/career-jobs-app.git
cd career-jobs-app
cp .env.example .env    # add DAYTONA_API_KEY and GH_PAT

# Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Load environment variables and login to Daytona
source .env
daytona login --api-key $DAYTONA_API_KEY

make setup              # installs daytona, jq, gh, shellcheck, node/pnpm (macOS: via Brewfile)
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

### 4) Stop & cleanup

- Do nothing: sandbox **auto‑stops after 45 min idle**, then **auto‑archives 60 min later**.
- Or stop immediately when you're done:
  ```bash
  make stop
  ```

> **Note:** Claude Code installation persists in the sandbox until it's archived, so you only need to install it once per sandbox lifecycle.

---

## Where to run tests

- **Cursor IDE (exploration):** Quick unit tests locally for fast feedback
- **Daytona sandbox (main development):** `pnpm test` in Claude Code sessions
- **CI (source of truth for PRs):** Full test suites; see `.github/workflows/`

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

