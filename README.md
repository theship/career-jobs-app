# Career Jobs App — Dev Quickstart

For full details see **[`./docs/dev-overview.md`](./docs/dev-overview.md)**. This README is the **short, practical guide** you’ll actually use day‑to‑day.

---

## First‑time setup (per machine)

```bash
git clone git@github.com:theship/career-jobs-app.git
cd career-jobs-app
cp .env.example .env        # add DAYTONA_API_KEY and GH_PAT
# optional (only if you haven't yet): daytona login --api-key "$DAYTONA_API_KEY"
```

Now you’re ready for daily dev.

---

## Daily workflow

### 1) Edit locally with Cursor + Claude Code
*(Claude stays on your laptop; nothing new to configure.)*

```
~/career-jobs-app/         ← normal folder
│   src/…
│   scripts/…
│   .daytona.yml
└─  .env
```

Claude writes/edits files here, runs inline tests, etc.

### 2) Run / preview remotely in the sandbox

Start or resume your sandbox:

```bash
make dev
```

A browser tab opens to **`https://22222-<id>.proxy.daytona.work`** — that’s your sandbox Web Terminal. In that terminal:

```bash
# first time each session
git pull         # fetch the code Claude just edited locally
pnpm run dev     # or pnpm test, node scripts/…, etc.
```

Because we inject `GH_PAT` into the sandbox, `git pull` works without prompts.

### 3) Push / pull loop

| You do in **Cursor**                                              | Then do in **Web Terminal**             | Result                                                            |
| ----------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------- |
| `git add .` <br>`git commit -m "feat: login page"` <br>`git push` | `git pull`                              | Sandbox gets the latest code; dev server restarts / tests re-run. |
| Edit a single file & save (no commit yet)                         | `gh pr diff --cached` *(optional look)* | You can see the diff without committing.                          |
| Merge a PR on GitHub                                              | `git pull`                              | Sandbox updates to the new main branch.                           |

> **Tip:** add a tiny alias in the sandbox:
>
> ```bash
> echo 'alias gp="git pull --ff-only"' >> ~/.bashrc && source ~/.bashrc
> ```
> Then just type `gp` after every local push.

### 4) Stop & clean‑up

- Do nothing: sandbox **auto‑stops after 45 min idle**, then **auto‑archives 60 min later**.
- Or stop immediately when you’re done:
  ```bash
  make stop
  ```

**Preview URL:** when `pnpm run dev` is running, open `https://3000-<id>.proxy.daytona.work`.

---

## Where to run tests

- **Local (fast iteration):** `pnpm test:watch`
- **Sandbox (debug/preview as needed):** `pnpm test`
- **CI (source of truth for PRs):** runs full suites; see `.github/workflows/`

---

Need the rationale, caveats (no SSH on sandboxes), PAT setup, or CI examples? Read **[`./docs/dev-overview.md`](./docs/dev-overview.md)**.


---

## Prebuilt dev image (faster cold-starts)

We publish a dev image to GHCR via **.github/workflows/build-dev-image.yml**.
First time only, trigger the build so the image exists:

```bash
git commit --allow-empty -m "build: seed dev image"
git push
```

Once the workflow completes, `make dev` will start much faster (the sandbox pulls `ghcr.io/<org>/<repo>:dev`).

