#!/usr/bin/env bash
set -euo pipefail

# 0) prereqs
command -v jq >/dev/null || { echo "jq is required (brew install jq)"; exit 1; }

# 1) load .env
[[ -f .env ]] && { set -a; source .env; set +a; }
: "${DAYTONA_API_KEY:?DAYTONA_API_KEY is not set}"
: "${GH_PAT:?GH_PAT is not set}"
: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is not set}"

# 2) ensure we're logged in
# Note: Bypassing list check due to API response format issue
# The login is successful but list command has JSON parsing issues
# if ! daytona sandbox list --limit 1 &>/dev/null; then
#   echo "Run once: export DAYTONA_API_KEY=… && daytona login --api-key \$DAYTONA_API_KEY"
#   exit 1
# fi

LABEL_KEY="project"
LABEL_VAL="career-jobs-app"

get_id () {
  local want_state="$1"  # started|stopped|archived
  daytona sandbox list --format json 2>/dev/null |
    jq -r --arg k "$LABEL_KEY" --arg v "$LABEL_VAL" --arg s "$want_state" '
      .[] |
      select( (.state|ascii_downcase)==$s and
              ( .labels[$k]?==$v or (.labels[]?==($k + "=" + $v)) ) ) |
      .id ' | head -n1
}

NEWLY_CREATED=""

# 3) reuse running or stopped; delete archived; else create
ID="$(get_id started || true)"
if [[ -n "${ID:-}" ]]; then
  echo "✅ Using running sandbox $ID"
else
  ID="$(get_id stopped || true)"
  if [[ -n "${ID:-}" ]]; then
    echo "▶️  Resuming sandbox $ID"
    daytona sandbox start "$ID"
  else
    # Check for archived sandboxes and clean them up
    ARCHIVED_ID="$(get_id archived || true)"
    if [[ -n "${ARCHIVED_ID:-}" ]]; then
      echo "🗑️  Deleting archived sandbox $ARCHIVED_ID"
      daytona sandbox delete "$ARCHIVED_ID" || true
    fi
    
    echo "🆕  Creating new sandbox..."
    # Daytona returns JSON, so parse it with jq
    RESPONSE=$(daytona sandbox create \
          --label "$LABEL_KEY=$LABEL_VAL" \
          --context . \
          --auto-stop 45 \
          -e GH_PAT="$GH_PAT" \
          -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
    
    # Try to parse as JSON first, fallback to grep if it's plain text
    ID=$(echo "$RESPONSE" | jq -r '.id' 2>/dev/null || echo "$RESPONSE" | grep -oE '[0-9a-f\-]{36}' | head -1)
    
    if [[ -z "$ID" ]]; then
      echo "Failed to extract sandbox ID from response:"
      echo "$RESPONSE"
      exit 1
    fi
    
    NEWLY_CREATED="1"
  fi
fi

# 4) check environment variables on resumed sandbox (don't leak secrets)
if [[ -z "$NEWLY_CREATED" && -n "${ID:-}" ]]; then
  ENV_INFO=$(daytona sandbox list --format json 2>/dev/null |
    jq -r --arg id "$ID" '.[] | select(.id==$id) | {gh_pat: .env.GH_PAT // "", anthropic_key: .env.ANTHROPIC_API_KEY // ""}')
  HAS_PAT=$(echo "$ENV_INFO" | jq -r '.gh_pat')
  HAS_ANTHROPIC=$(echo "$ENV_INFO" | jq -r '.anthropic_key')
  
  if [[ -z "$HAS_PAT" || -z "$HAS_ANTHROPIC" ]]; then
    echo "⚠️  This sandbox is missing environment variables:"
    [[ -z "$HAS_PAT" ]] && echo "    Missing: GH_PAT"
    [[ -z "$HAS_ANTHROPIC" ]] && echo "    Missing: ANTHROPIC_API_KEY"
    echo "    (Recommendation: stop & delete this sandbox, then rerun 'make dev' to create a fresh one.)"
  fi
fi

# 5) open Web Terminal (best-effort)
URL="https://22222-${ID}.proxy.daytona.work"
echo "🔗  Opening Web Terminal: $URL"
if [[ -n "$NEWLY_CREATED" ]]; then
  echo ""
  echo "💡  First time setup in the Web Terminal:"
  echo "    # Install Claude Code (secure method)"
  echo "    curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh"
  echo "    sh /tmp/claude-install.sh"
  echo ""
  echo "    # API key is automatically available via sandbox environment"
  echo "💻  Then start Claude Code with: claude"
  echo ""
fi

if command -v open >/dev/null; then
  open "$URL" || true
elif command -v xdg-open >/dev/null; then
  xdg-open "$URL" || true
else
  echo "Open this URL in your browser: $URL"
fi
