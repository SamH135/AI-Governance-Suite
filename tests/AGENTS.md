# AGENTS.md — tests/ (pytest suite)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.
> Not to be confused with `services/tests/` (the test execution service).

## Purpose
Python test suite for all backend code. Each area's `AGENTS.md` names the specific tests to run. This file defines the tiers and conventions.

## Layout and tiers
| Dir | Runs in CI | Needs | Notes |
|---|---|---|---|
| `unit/` | yes | nothing (intended) | Offline also: `test_security_hardening`, `test_eval_integrity`. **Known issue:** `test_auth.py`, `test_model_config.py`, `test_systems_api.py`, `test_no_fallbacks.py` call `localhost` and need the live stack. Offline today: `test_evaluator`, `test_compliance`, `test_evaluator_plugins`, `test_probe_evals`, `test_probe_mutations`, `test_probe_adaptive`, `test_saved_api_keys`, `test_unified_api`, `test_shared_sso_manager`, `test_documents_format_converter`, `test_shared_task_refs_saml`, `test_gateway_cors_order`, `test_plugin_generator`, `test_no_bare_create_task`, `test_gateway_proxy`. |
| `integration/` | when stack is up | `docker-compose up`; some need provider keys in env | Cross-service and real-provider tests |
| `manual/` | no | stack + keys | Ad-hoc scripts, not assertions-based |

## Rules
- **Never hardcode API keys.** Read them with `os.getenv("GOOGLE_API_KEY", "")` etc., and skip when unset. (A real key once leaked through test files.)
- New unit tests must run offline: mock the unified API, DB, and Redis, or use the `predetermined_responses` provider.
- No `conftest.py` exists. Tests insert the repo root into `sys.path` (see `unit/test_evaluator_plugins.py`). Follow that pattern or add a shared `conftest.py` in a dedicated PR.
- Name files `test_<area>_<thing>.py` so the right tests can be picked per area.
- Probe evaluators take a `call_fn` kwarg — inject a scripted fake target (see `test_probe_evals.py`). Always test one vulnerable and one safe response and assert the score flips.
- `pytest-asyncio` is not in the local env; `test_evaluator_plugins.py` is also runnable via `py tests/unit/test_evaluator_plugins.py` (its `__main__` block).

## What to run for a change
| You changed | Run at minimum |
|---|---|
| `plugins/evaluators/*` | `unit/test_evaluator_plugins.py` + the plugin's own test |
| `framework/probes/*` | `unit/test_probe_evals.py` + `unit/test_evaluator_plugins.py` |
| `services/compliance/*` | `unit/test_evaluator.py`, `unit/test_compliance.py`, `unit/test_evaluator_plugins.py` |
| `shared/unified_api/*` | `unit/test_unified_api.py` (+ `integration/test_unified_api_providers.py` with keys) |
| `services/shared/*` | all offline `unit/` tests + rebuild all containers |
| gateway / cross-service | `integration/` with the stack up |
| frontend | `npm run lint && npm run test` (see `frontend/AGENTS.md`) |

## Change Log
- 2026-11-11 — AGENTS.md created (baseline). Hardcoded Google key removed from all test files during the public-release scrub.
- 2026-11-11 — Added `test_probe_evals.py` (9 tests, fake-target driven). `test_evaluator_plugins.py`: probe evaluators skip the no-config rule-based loop; expected list extended.
- 2026-11-13 — Added `test_eval_integrity.py`: regression tests for the eval-integrity overhaul — axis-aware aggregation (`attack`/`benign`/`any`, skipped checks excluded from denominators), provider safety blocks (`ProviderBlockedError` → `transcript.provider_blocked` → scored as refusal, never a run error), tightened refusal patterns, all-tokens canary decoding, `exfil_render` gating, balanced-brace tool-call parsing, step-cap evidence, tool-shadowing last-manifest-wins, sanctioned-tool-call non-flagging (tool_poisoning/tool_misuse/code_execution), vector-embedding doc canaries. `test_probe_evals.py` now uses an explicit fake judge for judge-dependent checks (judge-less checks skip instead of fabricating a score).
- 2026-11-14 — Added `test_security_hardening.py` (offline): url_safety outbound-URL rules + env opt-in, `SandboxedEnvironment` blocks `__mro__` escapes, `_resolve_model_config` ownership scoping and private-`api_url` rejection via a fake `AsyncSession`, schema `api_url` validators. Uses the function's AST since the router module can't import outside the service env.
- 2026-11-15 — Added `test_probe_mutations.py` (16 tests, offline): transform round-trips, `mutate()` gating/lineage/max_variants/idempotence, StrongREJECT grading `refs.original_request`, `ProbeCase.history` delivery vs non-scoring, hex canary decoding, `wilson_interval` values, `by_technique` end-to-end via `jailbreak_robustness`.
- 2026-11-15 — Added `test_probe_adaptive.py` (11 tests, offline): PAIR loop early-stop/iteration cap/refusal-first scoring/provider-block, invalid-candidate RuntimeErrors, `make_attacker` nonce-tag isolation, `make_score_fn` range validation, `adaptive_jailbreak` end-to-end + iteration clamp + missing-LLM ValueError. `adaptive_jailbreak` added to `expected_plugins` and `PROBE_EVALUATORS`.
- 2026-11-16 — Added `test_grounding.py` (7 tests, offline): claim splitting/abstention filter, unsupported-claim scoring, skip semantics (no docs/no claims/refusal), fail-loud scorer errors, lazy scorer init, `claim_grounding` plugin e2e with scripted dict scorer + fake target. `claim_grounding` added to `expected_plugins` and `PROBE_EVALUATORS` (note: live run triggers a ~400MB HF download on first use).
- 2026-11-16 — `manual/grounding_bakeoff.py` (manual, not pytest): 6-model grounding bake-off on 27 hand-labeled legal/medical pairs via the production `NLIGroundingScorer` path; results in `manual/grounding_bakeoff_results.json`. Finding: purpose-built MiniCheck-DeBERTa scored lowest (81.5%, weak on multi-hop); default switched to `ynie/roberta-large` (96.3%, ~1.5s/pair).
- 2026-11-16 — `test_grounding.py` +2 (fact-leak conveyance scoring, refusal-scores-0/skip-no-prompt). `test_probe_evals.py`: leakage + indirect-injection tests now inject fake scorers (required — plugins' NLI checks would otherwise download the real model in unit tests).
- 2026-11-17 — Added `test_shared_sso_manager.py` (3 tests, offline): forged unsigned `id_token` ignored in favour of userinfo claims, missing `access_token` and userinfo non-200 both raise `AuthenticationError`. Stubs `redis` in `sys.modules` when not installed (local env lacks it).
- 2026-11-17 — Added `test_documents_format_converter.py` (2 tests, offline): wkhtmltopdf success path returns fake PDF bytes from a private `TemporaryDirectory` (no predictable `/tmp/<base>` paths, dir cleaned up), `CalledProcessError` falls back to HTML with no leaked files. Stubs `markdown` in `sys.modules` when not installed.
- 2026-11-17 — Added `test_shared_task_refs_saml.py` (5 tests, offline): `_handle_saml_callback` fail-closed with/without SAMLResponse, `async_utils.spawn` strong-ref lifecycle, websocket `_redis_message_handler` re-raises `CancelledError` (AST check — module needs fastapi/redis to import).
- 2026-11-17 — Added `test_gateway_cors_order.py` (3 tests, offline, AST — gateway modules can't import outside the env): `CORSMiddleware` is the last `app.add_middleware` in `gateway/main.py`, no bare `asyncio.create_task` expression in `websocket/manager.py`, and the task is stored on `self._redis_task`.
- 2026-11-17 — Added `test_plugin_generator.py` (12 tests, offline): scaffold output, template list, generate_from_template, slug rejection (traversal/dots/spaces/digit-lead), existing-dir rejection. `PluginGenerator` takes an injectable `base_dir`.
- 2026-11-17 — Added `test_gateway_proxy.py` (3 tests): first `TestClient` tests for gateway/ — path-preserving proxy, identity-header injection, service-status passthrough, unreachable-service 500. Skips where `gateway/` or its deps are absent; CI runs it inside the **gateway** container (repo mounted at `/repo` in `docker-compose.simple.yml`), where `test_gateway_cors_order.py` now also runs instead of skipping.
- 2026-11-17 — Added `test_no_bare_create_task.py` (1 test, offline, AST): scans `services/`, `gateway/`, `shared/`, `plugins/` for bare `asyncio.create_task` expression statements (S7502 regression guard).
