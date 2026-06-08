.DEFAULT_GOAL := help
.PHONY: help install up down lint format typecheck test spike ingest refresh db-migrate web

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install: ## Install deps (Python via uv, web via pnpm)
	uv sync
	cd packages/web && pnpm install

up: ## Start optional local services (Postgres + Redis)
	docker compose up -d

down: ## Stop local services
	docker compose down

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

db-migrate: ## Apply Supabase SQL migrations to $$DATABASE_URL
	psql "$$DATABASE_URL" -f supabase/migrations/0001_init.sql -f supabase/migrations/0002_graph_functions.sql

web: ## Run the web frontend locally (reads Supabase)
	cd packages/web && pnpm dev
