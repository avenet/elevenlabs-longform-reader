.PHONY: help hlp fmt lint lint-fixup test test-unit test-live serve check

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[-a-zA-Z0-9_]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

hlp: help

fmt: ## Format code with ruff
	pipenv run fmt

lint: ## Lint code with ruff
	pipenv run lint

lint-fixup: ## Lint and auto-fix with ruff
	pipenv run lint-fixup

test: ## Run the full test suite
	pipenv run test

test-unit: ## Run mocked tests (skip live ElevenLabs)
	pipenv run test-unit

test-live: ## Run live ElevenLabs integration tests
	pipenv run test-live

serve: ## Start the FastAPI app with reload
	pipenv run serve

check: ## Lint and run mocked tests
	pipenv run check
