# AGENTS.md — tests/ (pytest suite)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Not to be confused with `services/tests/` (the test execution service).

## Purpose
Python test suite for all backend code. Each area's `AGENTS.md` names the specific tests to run. This file defines the tiers and conventions.

## Layout and tiers
| Dir | Runs in CI | Needs | Notes |
|---|---|---|---|
| `unit/` | yes | nothing (intended) | **Known issue:** `test_auth.py`, `test_model_config.py`, `test_systems_api.py`, `test_no_fallbacks.py` call `localhost` and need the live stack. Offline today: `test_evaluator`, `test_compliance`, `test_evaluator_plugins`, `test_saved_api_keys`, `test_unified_api`. |
| `integration/` | when stack is up | `docker-compose up`; some need provider keys in env | Cross-service and real-provider tests |
| `manual/` | no | stack + keys | Ad-hoc scripts, not assertions-based |

## Rules
- **Never hardcode API keys.** Read them with `os.getenv("GOOGLE_API_KEY", "")` etc., and skip when unset. (A real key once leaked through test files.)
- New unit tests must run offline: mock the unified API, DB, and Redis, or use the `predetermined_responses` provider.
- No `conftest.py` exists. Tests insert the repo root into `sys.path` (see `unit/test_evaluator_plugins.py`). Follow that pattern or add a shared `conftest.py` in a dedicated PR.
- Name files `test_<area>_<thing>.py` so the right tests can be picked per area.

## What to run for a change
| You changed | Run at minimum |
|---|---|
| `plugins/evaluators/*` | `unit/test_evaluator_plugins.py` + the plugin's own test |
| `services/compliance/*` | `unit/test_evaluator.py`, `unit/test_compliance.py`, `unit/test_evaluator_plugins.py` |
| `shared/unified_api/*` | `unit/test_unified_api.py` (+ `integration/test_unified_api_providers.py` with keys) |
| `services/shared/*` | all offline `unit/` tests + rebuild all containers |
| gateway / cross-service | `integration/` with the stack up |
| frontend | `npm run lint && npm run test` (see `frontend/AGENTS.md`) |

## Change Log
- 2026-11-11 — AGENTS.md created (baseline). Hardcoded Google key removed from all test files during the public-release scrub.
