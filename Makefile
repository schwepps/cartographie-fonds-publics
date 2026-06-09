.DEFAULT_GOAL := help
.PHONY: help install up down supabase-up supabase-down supabase-reset lint format typecheck test spike spike-live spike-resolve spike-resolve-live resolve resolve-seed operators ingest refresh db-migrate db-verify web

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

install: ## Install deps (Python via uv, web via pnpm) + git hooks
	uv sync
	cd packages/web && pnpm install
	git config core.hooksPath .githooks   # committed, worktree-relative hooks (Conductor-safe)
	uv run pre-commit install-hooks       # pre-build hook envs (does not touch .git/hooks)

up: ## Start optional local Redis (cache)
	docker compose up -d

down: ## Stop local Redis
	docker compose down

supabase-up: ## Start the local dev Supabase stack (Postgres + PostgREST + Auth + Studio)
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

spike-live: ## Run the Phase-0 spike LIVE (discover+download+validate+snapshot+match, FSC-19)
	uv run python spikes/phase0_siren_match/spike.py

spike-resolve: ## Run the Phase-0.5 operator name->SIREN resolution spike (offline sample, FSC-48)
	uv run python spikes/phase0_siren_match/resolve_spike.py --sample

spike-resolve-live: ## Run the Phase-0.5 resolution spike LIVE (~430 operators via recherche-entreprises)
	uv run python spikes/phase0_siren_match/resolve_spike.py

resolve: ## Resolve the offline operator sample via the crosswalk (report + resolution rate, FSC-23)
	uv run python -m ingestion.cli resolve --operators spikes/phase0_siren_match/fixtures/operateurs_resolve_sample.csv

resolve-seed: ## Regenerate the crosswalk from the spike CSV (merge-aware; run a spike-resolve first)
	uv run python -m ingestion.cli resolve-seed --resolution-csv spikes/phase0_siren_match/out/operator_resolution.csv

operators: ## Transform the offline operator sample into entities + tutelle edges (report + rate, FSC-25)
	uv run python -m ingestion.cli operators --operators spikes/phase0_siren_match/fixtures/operateurs_resolve_sample.csv

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
