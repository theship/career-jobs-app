# Brewfile — dev machine deps
# Brewfile — macOS devs run `brew bundle`

tap "daytonaio/cli"            # Daytona CLI tap
brew "daytona"                 # Daytona CLI
brew "jq"                      # JSON parsing (make prune)
brew "gh"                      # GitHub CLI (PRs, checks)
brew "shellcheck"              # shell linter (make lint-sh)

# Node toolchain for local unit tests (optional if you never run tests locally)
brew "node@20"                 # or plain "node" if you prefer latest
brew "pnpm"                    # optional; otherwise use corepack
# nice-to-have
brew "git-delta"               # prettier diffs in terminal
