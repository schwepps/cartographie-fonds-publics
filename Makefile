.DEFAULT_GOAL := help
.PHONY: help install up down supabase-up supabase-down supabase-reset lint format typecheck test spike ingest refresh db-migrate db-verify web

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install: ## Install deps (Python via uv, web via pnpm) + git hooks
	uv sync
	cd packages/web && pnpm install
	uv run pre-commit install --install-hooks

up: ## Start optional local Redis (cache)
	docker compose up -d

down: ## Stop local Redis
	docker compose down

supabase-up: ## Start the local dev Supabase stack (Postgres + PostgREST + Studio)
	supabase start

supabase-down: ## Stop the local dev Supabase stack
	supabase stop

supabase-reset: ## Reset the local dev DB and re-apply supabase/migrations/*.sql
	supabase db reset

lint: ## Lint Python
	uv run ruff check .

format: ## Format Python
	uv run ruff format .

typecheck: ## Type-check Python
	uv run mypy packages

test: ## Run Python tests
	uv run pytest

spike: ## Run the Phase-0 SIREN-match spike (offline sample)
	uv run python spikes/phase0_siren_match/spike.py --sample

ingest: ## Run the ingestion pipeline (reads data/registry, writes Supabase)
	uv run python -m ingestion.cli ingest

refresh: ## Discover latest millésimes for all sources
	uv run python -m ingestion.cli refresh

db-migrate: ## Apply Supabase SQL migrations (in order) to $$DATABASE_URL
	@for f in supabase/migrations/*.sql; do \
		echo "→ applying $$f"; \
		psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$$f" || exit 1; \
	done

db-verify: ## Verify RLS posture (anon can read + call RPC, cannot write)
	psql "$$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/rls_checks.sql

web: ## Run the web frontend locally (reads Supabase)
	cd packages/web && pnpm dev
