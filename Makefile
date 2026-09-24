.PHONY: help data serve

PORT ?= 8000
GITHUB_TOKEN ?= $(shell gh auth token)
export GITHUB_TOKEN

help: ## Show targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

data: ## Rebuild data.json from GitHub, cranlogs, and pypistats
	uv run scripts/build_data.py

serve: ## Preview the site at http://localhost:$PORT (default 8000)
	uv run python -m http.server $(PORT)
