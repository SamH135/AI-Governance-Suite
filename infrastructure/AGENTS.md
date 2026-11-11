# AGENTS.md — infrastructure/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

## Purpose
Database schema and infra setup for the docker-compose stack.

## Layout
- `database/init.sql` — the **single consolidated** PostgreSQL schema + seed data. Tables include users, ai_systems, tests, test_results, ai_model_configs, ai_system_model_configs, user_api_keys, compliance_test_executions, document_*, prompt_*, workflow_*, audit_logs, analytics_cache, provider_configs/models, and others.

## Interfaces
- Mounted to `/docker-entrypoint-initdb.d/init.sql` in the `postgres` container. It runs **only when the volume is empty** (first start).

## Rules
- There's no migration tool. A schema change means editing `init.sql`, and existing databases only pick it up after `docker-compose down -v`, which **destroys all data**. Say this explicitly in the PR, and never run it on a shared or production database.
- Seed data is dev-only. The default admin user (`admin123`) must never be used outside local dev. Never seed real credentials or keys.
- Keep a single consolidated `init.sql` (deliberate consolidation, 2025). Don't scatter schema across files.

## Verification
- `docker-compose down -v && docker-compose up --build`, then check `docker-compose logs postgres` for SQL errors.
- Smoke check that services relying on changed tables still start (`/health` on each) and the affected UI flow works.

## Decisions & Known Issues
- Introducing migrations (e.g. Alembic) is the upgrade path once there are real deployments to preserve.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
