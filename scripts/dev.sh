#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────── 0. prereqs ─────────────────────────
command -v jq >/dev/null || { echo "jq is required (brew install jq)"; exit 1; }

# ──────────────────────── 1. load .env ───────────────────────
[[ -f .env ]] && { set -a; source .env; set +a; }
: "${DAYTONA_API_KEY:?DAYTONA_API_KEY is not set}"
: "${GH_PAT:?GH_PAT is not set}"

# ──────────────────────── 2. auth probe ──────────────────────
if ! daytona sandbox list --limit 1 &>/dev/null; then
  echo "Run once: export DAYTONA_API_KEY=… && daytona login --api-key \$DAYTONA_API_KEY"
  exit 1
fi

LABEL_KEY="project"
LABEL_VAL="career-jobs-app"

# Helper to get the first sandbox id matching label+state
get_id () {
  local want_state="$1"  # started|stopped
  daytona sandbox list --format json 2>/dev/null |
    jq -r --arg k "$LABEL_KEY" --arg v "$LABEL_VAL" --arg s "$want_state" '
      .[] |
      select( (.state|ascii_downcase)==$s and
              ( .labels[$k]?==$v or (.labels[]?==($k + "=" + $v)) ) ) |
      .id ' | head -n1
}

# ──────────────────────── 3. reuse or create ─────────────────
# 3a ▸ if a RUNNING sandbox exists, use it
ID="$(get_id started || true)"
if [[ -n "${ID:-}" ]]; then
  echo "✅ Using running sandbox $ID"
else
  # 3b ▸ else try a STOPPED sandbox
  ID="$(get_id stopped || true)"
  if [[ -n "${ID:-}" ]]; then
    echo "▶️  Resuming sandbox $ID"
    daytona sandbox start "$ID"
  else
    # 3c ▸ else create a new sandbox with GH_PAT injected
    echo "🆕  Creating new sandbox..."
    ID=$(daytona sandbox create \
          --label "$LABEL_KEY=$LABEL_VAL" \
          --context . \
          --auto-stop 45 \
          -e GH_PAT="$GH_PAT" \
          | grep -oE '[0-9a-f\-]{36}')
  fi
fi

# ──────────────────────── 4. verify GH_PAT on resumed boxes ─
# (skip if we just created)
if [[ -z "${NEWLY_CREATED:-}" && -n "${ID:-}" ]]; then
  HAS_PAT=$(daytona sandbox list --format json 2>/dev/null |
    jq -r --arg id "$ID" '.[] | select(.id==$id) | .env.GH_PAT // ""')
  if [[ -z "$HAS_PAT" ]]; then
    echo "⚠️  This sandbox was created without GH_PAT."
    echo "    In the Web Terminal, run:  export GH_PAT=$GH_PAT"
    echo "    then: git pull"
    echo "    (Alternatively: stop & delete this sandbox, then rerun make dev to create a fresh one.)"
  }
fi

# ──────────────────────── 5. open Web Terminal ───────────────
URL="https://22222-${ID}.proxy.daytona.work"
echo "🔗  Opening Web Terminal: $URL"
command -v open >/dev/null && open "$URL" || xdg-open "$URL"
