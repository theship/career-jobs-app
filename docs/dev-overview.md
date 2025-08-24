# GitHub ⇄ Cursor + Daytona + Claude Code ⇄ CodeRabbit workflow

> **Scope:** This is the canonical guide for developing inside a safe "bubble" using **Cursor IDE** for code exploration and **Claude Code running directly in Daytona AI Sandboxes** for development work, with **CodeRabbit** for PR reviews. This hybrid approach provides the best of both worlds: Cursor's excellent IDE features locally and secure code execution in the cloud.

---

## 1) Purpose

- Keep untrusted/npm code execution **isolated** from laptops.
- Keep dev ergonomics high: **Cursor IDE** for code exploration and **Claude Code in Daytona** for development work.
- Keep reviews and CI **in GitHub**, with **CodeRabbit** enforcing PR quality.
- Make the environment **share-by-git** so `make dev` brings anyone to the same bubble.

---

## 2) Project decisions & caveats

### Daytona (AI Sandboxes, CLI ≥ v0.25)
- **No SSH endpoint** for sandboxes, but **Web Terminal** at `https://22222-<id>.proxy.daytona.work` provides full shell access for Claude Code.
- **Claude Code installation**: Persists in sandbox until archived, install once per sandbox lifecycle.
- `daytona sandbox create` prints **human text**, not JSON → use `daytona sandbox list --format json` to query IDs/state.
- When launching with `--context .` **do not pass** `--cpu/--memory/--disk` (snapshot-style error). We default to **class small (1 vCPU / 1 GiB)** which is plenty for Node+Vite+Claude Code.
- Old verbs like `daytona env` and `git-providers` are **gone**. We load `.env` locally and pass vars on create via our script.
- Manual `archive` verb is not exposed in the stable CLI. We rely on **`autoArchiveMinutes`** to move stopped boxes to cold storage.

### GitHub & tokens
- Daytona needs **one fine-grained PAT** (repo-scoped) with **Contents: RW** and **Workflows: RW**. Store as `GH_PAT` in `.env`.
- **CodeRabbit** is a **GitHub App** → **no PAT** needed for it.

### Cursor IDE + Claude Code
- **Cursor IDE (local)**: Code exploration, file browsing, git operations, and Claude Code for Cursor integration
  - Claude Code in Cursor provides AI assistance with full codebase context
  - Excellent IntelliSense, debugging tools, and IDE features
  - Git integration for commits, branches, and PR management
- **Claude Code (in Daytona)**: Actual development work, code execution, testing, and file modifications
  - Full shell environment with persistent state
  - Direct file system access for reliable code changes
  - Isolated execution environment for security

### Cost discipline (high level)
- **One sandbox per project**; reuse stopped boxes by label.
- **Short sessions:** `make stop` when done; fallback **auto-stop 45 min** → **auto-archive 60 min**.
- **Run tests in CI** by default; only debug in the sandbox.
- **Prebuild dev image** to avoid spending sandbox time on `pnpm i`.

---

## 3) Setting up a new project (one-time)

### A. Prerequisites (run once per laptop)
```bash
git clone git@github.com:theship/career-jobs-app.git
cd career-jobs-app

cp .env.example .env          # add DAYTONA_API_KEY and GH_PAT
brew install daytonaio/cli/daytona

# first-time Daytona login
export DAYTONA_API_KEY=dkp_xxx
daytona login --api-key "$DAYTONA_API_KEY"
```

### B. GitHub repo & PAT
Create a **fine-grained PAT** on your account (or a machine user):
- **Repository access:** only `theship/career-jobs-app`
- **Permissions:** `Contents: Read/Write`, `Workflows: Read/Write`
- Add to `.env`: `GH_PAT=ghp_xxx`

### C. How the PAT is injected
We never use the removed `daytona env`. Our `scripts/dev.sh` loads `.env` and passes `GH_PAT` when creating the sandbox, so `git pull` works in the Web Terminal without prompts. Older sandboxes may lack `GH_PAT`; the script warns—either export it manually in the Web Terminal or create a fresh sandbox.

### D. Install CodeRabbit on the repo
GitHub → **Settings → Integrations → GitHub Apps** → install **CodeRabbit** on this repo (no PAT).

### E. Repository hardening (recommended)
- Protect `main` from direct pushes.
- Require status checks: **CodeRabbit** + CI tests must pass before merge.
- Confirm `.gitignore` includes `.env`.

### F. Baseline config files (commit once)
These live in the repo:
- **`.daytona.yml`** (defaults & cost controls)
- **`.devcontainer/devcontainer.json`** (editor parity)
- **`scripts/dev.sh`** (create/resume + open terminal)
- **`Makefile`** (`dev`, `stop`, `prune`)
- **`.env.example`** (template of required keys)

**`.daytona.yml` (project defaults & cost controls)**
```yaml
class: small
labels: { project: career-jobs-app }
autoStopMinutes: 45
autoArchiveMinutes: 60
env:
  - GH_PAT=${GH_PAT}
networkPolicy:
  egress:
    - allow: https://registry.npmjs.org
    - allow: https://github.com
```

### G. Spin up the first sandbox and install Claude Code
```bash
make dev
# A browser tab opens to: https://22222-<sandbox-id>.proxy.daytona.work
# In that Web Terminal, set up Claude Code (first time per sandbox):
curl -fsSL https://claude.ai/install.sh | sh
export ANTHROPIC_API_KEY=your_anthropic_api_key_here
echo 'export ANTHROPIC_API_KEY=your_anthropic_api_key_here' >> ~/.bashrc

# Now you can run Claude Code:
claude

# In Claude Code session (or regular terminal):
git pull
pnpm run dev   # or pnpm test, node scripts/..., etc.
```
Preview at `https://3000-<id>.proxy.daytona.work` when the dev server runs.

### H. CI wiring (tests + nightly jobs)
**PR & push tests** (`.github/workflows/ci.yml`):
```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm install --frozen-lockfile
      - run: pnpm test:unit
      - run: pnpm test:integration --if-present
      - run: pnpm test:e2e --if-present
```

**Nightly job fetch** (`.github/workflows/nightly-fetch.yml`):
```yaml
name: nightly-job-fetch
on:
  schedule: [{ cron: "0 8 * * *" }]  # 08:00 UTC ≈ 01:00 PT
jobs:
  fetch:
    runs-on: ubuntu-latest
    env:
      SS_API_KEY: ${{ secrets.SS_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: pnpm i && pnpm exec node scripts/fetch_jobs.js
```
> **Why CI?** CI minutes are free enough, deterministic, and make CodeRabbit’s status checks meaningful. Running full suites in the sandbox burns quota/time.

---

## 4) Contributing to an existing project

### First run (per machine)
```bash
# Local setup
git clone git@github.com:theship/career-jobs-app.git
cd career-jobs-app
cp .env.example .env          # add DAYTONA_API_KEY, GH_PAT, ANTHROPIC_API_KEY

# How environment variables flow:
# 1. You store keys locally in ~/career-jobs-app/.env:
#    DAYTONA_API_KEY=dkp_your_key_here
#    GH_PAT=ghp_your_token_here  
#    ANTHROPIC_API_KEY=sk-ant-your_key_here
# 2. When you run make dev locally:
#    - scripts/dev.sh loads your .env file
#    - Passes keys to Daytona API when creating sandbox:
#      daytona sandbox create \
#        -e GH_PAT="$GH_PAT" \
#        -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
# 3. Daytona injects them into the sandbox environment
# 4. .daytona.yml references them and makes them available to Claude Code

# Start Daytona sandbox
make dev                      # opens Web Terminal (22222-...)

# In the Web Terminal, install Claude Code (first time per sandbox)
# Use secure installation method
curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh
# Optionally verify checksum here, then:
sh /tmp/claude-install.sh

# API key is automatically available via sandbox environment
# No need to export manually - it's injected via .daytona.yml
```

### Day-to-day workflow

#### 1) Code exploration with Cursor IDE (local)
```text
~/career-jobs-app/         ← Open this in Cursor IDE
│   src/…
│   scripts/…
│   .daytona.yml
└─  .env
```
- Use Claude Code in Cursor for AI assistance with full codebase context
- Browse files, understand code structure, review changes
- Use Cursor's excellent IntelliSense and debugging tools
- Manage git operations (branches, commits, PRs) through Cursor's UI

#### 2) Development work in Daytona Web Terminal
In the **Web Terminal** at `https://22222-<id>.proxy.daytona.work`:
```bash
# Start Claude Code for development work
claude

# In Claude Code session:
git pull         # sync latest changes
pnpm run dev     # run development server
# Claude Code can now edit files, run tests, etc.
```

#### 3) Push / pull loop

| You do in **Cursor**                                              | Then do in **Web Terminal**             | Result                                                            |
| ----------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------- |
| `git add .` <br>`git commit -m "feat: login page"` <br>`git push` | `git pull`                              | Sandbox gets latest; dev server/test reruns.                      |
| Edit a file locally (no commit)                                   | `gh pr diff --cached` *(optional)*      | Inspect diff without committing.                                  |
| Merge a PR on GitHub                                              | `git pull`                              | Sandbox updates to new `main`.                                    |

#### 4) Hybrid workflow benefits

| **Environment**         | **Best Used For**                                              | **Tools Available**                                    |
| ----------------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| **Cursor IDE (local)**  | Code exploration, git management, AI assistance              | Claude Code integration, IntelliSense, git UI        |
| **Daytona (remote)**    | Code execution, file modifications, testing, development     | Claude Code CLI, full shell, isolated execution      |


> **Key insight:** You get the best of both worlds - Cursor's excellent IDE features locally and secure, isolated development in the cloud.

#### 4) Stop & clean-up
- **Stop immediately when you’re done:**
  ```bash
  make stop
  ```
- If you forget, the sandbox **auto-stops after 45 min idle**, then **auto-archives 60 min later**.

---

## 5) Tests — where to create and run them

**Unit tests (fast, no network):**
- Framework: **Vitest** (or Jest) under `src/**/__tests__/*.test.ts`.
- **Local** during development (`pnpm test:watch`), **CI** on PRs.

**Integration tests (API boundaries, DB mocks):**
- Place under `tests/integration/*.test.ts`.
- Run in **CI** (`pnpm test:integration`), and in the **sandbox** only for debugging.

**E2E tests (browser):**
- Framework: **Playwright** under `tests/e2e/`.
- Prefer **CI** for determinism (`pnpm test:e2e`); sandbox is for repro.

`package.json` scripts:
```jsonc
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:unit": "vitest run --dir src",
    "test:integration": "vitest run --dir tests/integration",
    "test:e2e": "playwright test"
  }
}
```
> **Cost saver:** Default to CI for anything heavier than unit tests.

---

## 6) Cost discipline (detailed)

- **One sandbox at a time** per project. Our script reuses any `state=stopped` sandbox with label `project=career-jobs-app`.
- **Small class** unless proven otherwise; upgrade only if CI shows a need.
- **Short sessions:** use `make stop`. Rely on `autoStopMinutes: 45` and `autoArchiveMinutes: 60` for safety.
- **Prebuild dev image** so cold-starts don’t spend time installing deps (see CI snippet below).

### Optional CI to prebuild image (cuts sandbox minutes)
```yaml
# .github/workflows/build-dev-image.yml
name: build-dev-image
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build & push
        run: |
          IMAGE=ghcr.io/${{ github.repository }}:dev
          docker build -t "$IMAGE" -f Dockerfile.dev .
          docker push "$IMAGE"
```
Then in `.daytona.yml`: `image: ghcr.io/theship/career-jobs-app:dev`.

### Prune command (Makefile)

```make
# markdownlint-disable MD010
prune:
	@daytona sandbox list --format json | 	jq -r '.[] | select((.state|ascii_downcase)=="archived") | .id' | 	xargs -r daytona sandbox delete
  # markdownlint-enable MD010
```

---

## 7) Reviewing & evolving this workflow

- **When:** after Daytona CLI releases, when test stacks change, or when adding services (DB/GPU).
- **What to check:** does `make dev` reuse boxes? Are auto-stop/archive intervals right? Is CodeRabbit still required? Do CI workflows reflect real suites?
- **How:** open a PR updating `docs/dev-overview.md`, `.daytona.yml`, `scripts/dev.sh`, and workflows. Tag platform reviewers.

---

## Appendix A — Daytona CLI gotchas

- No `daytona env` / `git-providers` → use `.env` loader + `--env` on create.
- `create` isn’t JSON → use `sandbox list --format json` to query.
- `--context .` + resource flags will error out → remove flags or launch from a prebuilt snapshot/image.
- No `archive` subcommand yet → rely on `autoArchiveMinutes` or `delete`.
- State strings are lowercase; labels may be an object or `["key=value"]`. Our reuse logic handles both.

## Appendix B — Cursor + Claude Code tips

- **Claude Code in Cursor**: Excellent for code exploration, understanding existing code, and planning changes with full codebase context.
  - `Cmd/Ctrl + L`: Ask Claude about selected code
  - `Cmd/Ctrl + I`: Inline edit with Claude
  - `Cmd/Ctrl + K`: Generate code with Claude
  - `Cmd/Ctrl + Shift + P` → "Add to CLAUDE.md": Save important context for future sessions
  - `Cmd/Ctrl + Shift + P` → "Claude: Understand codebase": Get high-level code structure analysis
- **Claude Code in Daytona**: Use for actual development work, file modifications, testing, and execution.
- Install Dev-Containers extension if you like, but **do not click "Reopen in Container"** (that starts a local Docker container and confuses the workflow).
- **Git workflow**: Use Cursor's git UI for branch management and commits, then sync to Daytona with `git pull`.
- **Persistent Claude Code setup**: Once installed in a Daytona sandbox, Claude Code persists until the sandbox is archived (~60 minutes after stopping).

## Appendix C — Security & secrets

- Keep the GitHub PAT **fine-grained** and **repo-scoped**; rotate every 90 days.
- **CodeRabbit** requires **no PAT** (GitHub App installs tokens automatically).
- `.env` is **never committed**. CI reads secrets from **GitHub Actions → Secrets**.

---

## TODO — Switch Daytona to the prebuilt dev image (not enabled yet)

We already have **`.github/workflows/build-dev-image.yml`** in this repo. It builds `Dockerfile.dev` and pushes a dev image to **GHCR** as `ghcr.io/<owner>/<repo>:dev`.  
**Right now we are *not* using that image** for sandboxes; Daytona still creates from the default snapshot and seeds your local repo via `--context .`.

### Why we might enable it later
- **Faster cold-starts**: deps (pnpm/node modules) are preinstalled, so sandboxes start in seconds.
- **Lower sandbox minutes**: fewer “npm install” minutes burning the free tier.
- **Parity**: CI and local runs share the same base image.

### How to enable when ready
1) **Build the image at least once** (so the tag exists):
   ```bash
   git commit --allow-empty -m "build: seed dev image" && git push
   # wait for Actions ▸ build-dev-image to finish
   ```
2) **Make it pullable**: if the repo is private, GHCR packages default to private. Either:
   - Flip the `:dev` image visibility to **public** (recommended for dev; no secrets inside), or
   - Keep it private and wire registry credentials for Daytona (extra setup; TBD).
3) **Point Daytona at the image** by adding to `.daytona.yml`:
   ```yaml
   image: ghcr.io/theship/career-jobs-app:dev
   ```
   (Everything else in `.daytona.yml` stays the same.)

> Optional: If we later remove `--context .` from `scripts/dev.sh`, we’ll `git clone` / `git pull` inside the sandbox instead. For now, keeping `--context .` is simpler—Daytona will still pull the image first once `image:` is set, then copy our repo into place.
