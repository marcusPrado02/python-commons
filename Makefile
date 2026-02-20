.DEFAULT_GOAL := help
PYTHON        := python3
UV            := uv
SRC           := src
TESTS         := tests

.PHONY: help install install-dev lint format typecheck test test-unit test-integration test-cov security clean build docs

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

install: ## Install runtime dependencies only (no dev extras)
	$(UV) sync

install-dev: ## Install all dependencies including dev extras
	$(UV) sync --extra dev

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint: ## Run ruff linter (check only)
	$(UV) run ruff check $(SRC) $(TESTS)

lint-fix: ## Run ruff linter and auto-fix safe issues
	$(UV) run ruff check --fix $(SRC) $(TESTS)

format: ## Run ruff formatter (check only)
	$(UV) run ruff format --check $(SRC) $(TESTS)

format-fix: ## Run ruff formatter and apply changes
	$(UV) run ruff format $(SRC) $(TESTS)

typecheck: ## Run mypy strict type checking
	$(UV) run mypy $(SRC)

security: ## Run bandit security scan + pip-audit
	$(UV) run bandit -r $(SRC) -c pyproject.toml
	$(UV) run pip-audit

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run all tests (unit + integration)
	$(UV) run pytest $(TESTS)

test-unit: ## Run unit tests only
	$(UV) run pytest $(TESTS)/unit -m unit

test-integration: ## Run integration tests only (requires running infrastructure)
	$(UV) run pytest $(TESTS)/integration -m integration

test-cov: ## Run tests with coverage report
	$(UV) run pytest $(TESTS) --cov=$(SRC) --cov-report=term-missing --cov-report=html

test-fast: ## Run unit tests in parallel (pytest-xdist)
	$(UV) run pytest $(TESTS)/unit -m unit -n auto

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

build: ## Build source distribution and wheel
	$(UV) build

# ---------------------------------------------------------------------------
# Docs
# ---------------------------------------------------------------------------

docs: ## List all ADRs
	@echo "Architecture Decision Records:"
	@ls docs/architecture/*.md 2>/dev/null | sed 's|docs/architecture/||'

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean: ## Remove build artefacts, caches, and coverage data
	rm -rf dist/ build/ .eggs/ *.egg-info
	rm -rf htmlcov/ .coverage .coverage.* coverage.xml
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
