# AGENTS.md — services/analytics/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

## Purpose
Aggregates test results into metrics, reports, and dashboard data.

## Layout
- `main.py` — routers: `/analytics`, `/reports`, `/dashboards`
- `services/analytics_service.py` — all aggregation queries

## Interfaces
- Container `analytics-service`, host port **8005** → 8000. Build context is the repo root.
- Reads: `test_results`, `tests`, `ai_systems`, `analytics_cache` (PostgreSQL).
- Consumed by: gateway proxy (`ANALYTICS_SERVICE_URL`) → dashboard pages.

## Rules
- Raw SQL must use bound parameters (`text(query)` with `params`). Never build SQL by string interpolation of input.
- **Every query is scoped by `user_id`** (tenant isolation). Join through `ai_systems.user_id`.
- Async DB access only.

## Verification
- No tests exist for this service. A new or changed aggregation needs a `tests/unit/test_analytics_*.py` against a mocked session, including a test that one user's data never appears in another user's result.
- Manual: dashboard page loads with real test results after running a compliance test.

## Decisions & Known Issues
- In progress (uncommitted as of 2026-11-11): ORM-style queries being replaced with raw parameterized SQL in `analytics_service.py`.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
