.PHONY: all dev stop prune clean test lint-sh setup

setup:
	@./scripts/bootstrap.sh

lint-sh:
	@command -v shellcheck >/dev/null || { echo "Install shellcheck (brew install shellcheck)"; exit 1; }
	@shellcheck -s bash -x scripts/dev.sh

all: dev

dev:
	@./scripts/dev.sh

stop:
	@command -v daytona >/dev/null || { echo "daytona CLI is required (see docs)"; exit 1; }
	@daytona sandbox stop --all


# Delete all ARCHIVED sandboxes to free disk on Daytona

# markdownlint-disable MD010
prune:
		@command -v jq >/dev/null || { echo "jq is required for 'make prune'"; exit 1; }; ids="$$(daytona sandbox list --format json | jq -r '.[] | select((.state|ascii_downcase)=="archived") | .id')"; test -n "$$ids" && echo "$$ids" | xargs daytona sandbox delete || echo "No archived sandboxes to delete."
# markdownlint-enable MD010

clean: stop prune

test:
	@echo "No tests wired via Makefile; run 'pnpm test' instead."

