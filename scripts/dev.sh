#!/usr/bin/env bash
set -euo pipefail

# 0) prereqs
command -v jq >/dev/null || { echo "jq is required (brew install jq)"; exit 1; }

# 1) load .env
[[ -f .env ]] && { set -a; source .env; set +a; }
: "${DAYTONA_API_KEY:?DAYTONA_API_KEY is not set}"
: "${GH_PAT:?GH_PAT is not set}"

# 2) ensure we're logged in
if ! daytona sandbox list --limit 1 &>/dev/null; then
  echo "Run once: export DAYTONA_API_KEY=… && daytona login --api-key \$DAYTONA_API_KEY"
  exit 1
fi

LABEL_KEY="project"
LABEL_VAL="career-jobs-app"

get_id () {
  local want_state="$1"  # started|stopped
  daytona sandbox list --format json 2>/dev/null |
    jq -r --arg k "$LABEL_KEY" --arg v "$LABEL_VAL" --arg s "$want_state" '
      .[] |
      select( (.state|ascii_downcase)==$s and
              ( .labels[$k]?==$v or (.labels[]?==($k + "=" + $v)) ) ) |
      .id ' | head -n1
}

NEWLY_CREATED=""

# 3) reuse running or stopped; else create
ID="$(get_id started || true)"
if [[ -n "${ID:-}" ]]; then
  echo "✅ Using running sandbox $ID"
else
  ID="$(get_id stopped || true)"
  if [[ -n "${ID:-}" ]]; then
    echo "▶️  Resuming sandbox $ID"
    daytona sandbox start "$ID"
  else
    echo "🆕  Creating new sandbox..."
    ID=$(daytona sandbox create \
          --label "$LABEL_KEY=$LABEL_VAL" \
          --context . \
          --auto-stop 45 \
          -e GH_PAT="$GH_PAT" \
          | grep -oE '[0-9a-f\-]{36}')
    NEWLY_CREATED="1"
  fi
fi

# 4) check whether resumed sandbox has GH_PAT (don't leak secrets)
if [[ -z "$NEWLY_CREATED" && -n "${ID:-}" ]]; then
  HAS_PAT=$(daytona sandbox list --format json 2>/dev/null |
    jq -r --arg id "$ID" '.[] | select(.id==$id) | .env.GH_PAT // ""')
  if [[ -z "$HAS_PAT" ]]; then
    echo "⚠️  This sandbox was created without GH_PAT."
    echo "    In the Web Terminal, set your token (do not paste secrets here):"
    echo "      export GH_PAT=<your PAT> && git pull"
    echo "    (Alternatively: stop & delete this sandbox, then rerun 'make dev' to create a fresh one.)"
  fi
fi

# 5) open Web Terminal (best-effort)
URL="https://22222-${ID}.proxy.daytona.work"
echo "🔗  Opening Web Terminal: $URL"
if command -v open >/dev/null; then
  open "$URL" || true
elif command -v xdg-open >/dev/null; then
  xdg-open "$URL" || true
else
  echo "Open this URL in your browser: $URL"
fi
