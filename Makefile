.PHONY: help cv data data-prs data-packages data-other data-talks data-contributions serve

PORT ?= 8000
GITHUB_TOKEN ?= $(shell gh auth token)
export GITHUB_TOKEN

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-19s %s\n", $$1, $$2}'

data: ## Rebuild data/ (ONLY="prs packages other talks contributions" for just some)
	uv run scripts/build_data.py $(ONLY)

# one section each; skipped sections are read back from data/
data-prs: ## Rebuild merged PR counts (searches this year and last)
	@$(MAKE) data ONLY=prs
data-packages: ## Rebuild packages: downloads, roles, reviews, epics
	@$(MAKE) data ONLY=packages
data-other: ## Rebuild other repos (reads packages.json)
	@$(MAKE) data ONLY=other
data-talks: ## Rebuild talks, videos, and posts
	@$(MAKE) data ONLY=talks
data-contributions: ## Rebuild contribution calendars
	@$(MAKE) data ONLY=contributions

cv: ## Build cv/cv_barret_schloerke.pdf from cv/cv.json and data/ (needs typst)
	typst compile --root . --ignore-system-fonts --font-path cv/fonts cv/cv.typ cv/cv_barret_schloerke.pdf

serve: ## Preview the site at http://localhost:$PORT (default 8000)
	uv run scripts/serve.py $(PORT)
