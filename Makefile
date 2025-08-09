.PHONY: dev stop

dev:
	@./scripts/dev.sh

stop:
	@daytona sandbox stop --all

# Delete all ARCHIVED sandboxes to free disk on Daytona
prune:
	@command -v jq >/dev/null || { echo "jq is required for 'make prune'"; exit 1; }
	@ids="$$(daytona sandbox list --format json | jq -r '.[] | select((.state|ascii_downcase)=="archived") | .id')"; \
	if [ -n "$$ids" ]; then \
		echo "Deleting archived sandboxes:"; \
		echo "$$ids" | xargs daytona sandbox delete; \
	else \
		echo "No archived sandboxes to delete."; \
	fi
