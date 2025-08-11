# scripts/bootstrap.sh — macOS/Linux dev machine setup
# macOS: run `brew bundle`
# Linux: run `sudo apt-get install -y jq shellcheck gh curl git`
# then `source scripts/bootstrap.sh`

#!/usr/bin/env bash
set -euo pipefail

echo "▶ Bootstrap dev tools…"

need() { command -v "$1" >/dev/null; }

if [[ "$(uname -s)" == "Darwin" ]]; then
  if need brew; then
    if [[ -f Brewfile ]]; then
      brew bundle
    else
      brew install daytonaio/cli/daytona jq gh shellcheck node@20 pnpm || true
    fi
  else
    echo "❌ Homebrew not found. Install from https://brew.sh then rerun."
    exit 1
  fi
else
  # Debian/Ubuntu-ish
  if need apt-get; then
    sudo apt-get update
    sudo apt-get install -y jq shellcheck gh curl git
    # Node (pick one: nvm/fnm preferred; fallback to distro node)
    if ! need node; then
      echo "⚠ Installing distro Node (you can replace with nvm later)…"
      sudo apt-get install -y nodejs npm
    fi
    # Daytona CLI (Linux): install if missing
    if ! need daytona; then
      echo "⚠ Install Daytona CLI manually: https://www.daytona.io/docs/cli"
    fi
  else
    echo "❌ Unsupported Linux distro. Install jq, shellcheck, gh, node(>=20), pnpm, daytona manually."
    exit 1
  fi
fi

# Enable pnpm via corepack if available
if command -v corepack >/dev/null; then
  corepack enable || true
  corepack prepare pnpm@latest --activate || true
fi

echo "✅ Dev tools ready."
