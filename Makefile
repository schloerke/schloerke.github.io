.PHONY: help data serve

PORT ?= 8000
GITHUB_TOKEN ?= $(shell gh auth token)
export GITHUB_TOKEN

help: ## Show targets
	@grep -E '^[a-z%-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

data: ## Rebuild data/ (ONLY="prs packages other talks contributions" for just some)
	uv run scripts/build_data.py $(ONLY)

data-%: ## Rebuild one section, e.g. data-packages (same as data ONLY=packages)
	@$(MAKE) data ONLY=$*

serve: ## Preview the site at http://localhost:$PORT (default 8000)
	uv run python -m http.server $(PORT)
