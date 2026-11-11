# AGENTS.md — services/tests/ (test execution service)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Not to be confused with `/tests/` (the pytest suite).

## Purpose
Test execution and orchestration service: schedules and runs test executions, tracks their state.

## Layout
- `main.py` — routers: `/executions`, `/orchestrator` (also mounted under `/api/...` for the gateway proxy)
- `routers/executions.py`, `routers/orchestrator.py`
- `services/test_executor.py` — orchestration logic

## Interfaces
- Container `test-service`, host port **8004** → 8000. Build context is the repo root.
- Tables: `test_executions`, `execution_results`.
- Consumed by: gateway proxy (`TESTS_SERVICE_URL`). Design notes: `docs/test_execution_design.md`.

## Rules
- Execution state changes are async DB writes. Don't block the event loop with model calls; use the unified API's async methods.

## Verification
- No tests exist for this service. New orchestration logic needs a `tests/unit/test_executor_*.py` with DB and model calls mocked.
- Manual: `http://localhost:8004/docs`, create an execution and poll its status.

## Decisions & Known Issues
- Overlaps with `services/compliance/routers/systems.py` and `system_tests.py`, which also run tests. Decide on one owner of test execution before extending either.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
