# AGENTS.md — services/compliance/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Active plan: `/plan.md` (evaluator overhaul) — read it before touching evaluator plumbing.

## Purpose
Evaluation engine: AI systems + model configs CRUD, runs compliance tests against a target model, executes evaluators (built-in + plugins), RAG context, reports.

## Layout
- `main.py` — routers: `/compliance`, `/evaluators` (+ `/api/evaluators`), `/reports`, `/local-models`, `/plugins`, `/plugin-generator`, `/api` (models, model-configs, systems, system-tests)
- `framework/core/` — `base.py` (`BaseEvaluator` contract, `EvaluatorMetadata`, `aevaluate`), `registry.py` (evaluator discovery + slug lookup), `model_manager.py`
- `framework/probes/` — probe kit: `ProbeCase`/`Check`/`Transcript`, multi-turn/RAG/tool-sim harness, judges, `run_suite`. Infrastructure, not evaluation logic.
- `framework/evaluators/` — built-in evaluators: `bias_detection`, `generic_compliance`, `safety_analysis`
- `services/evaluators/plugin_manager.py` — loads `plugins/evaluators/*` (`PluginInterface`)
- `services/` — `compliance_service`, `evaluator_factory` (legacy → Registry), `rag_service`, `milvus_service`, `advanced_rag_service`, `local_model_service`
- `routers/systems.py` — **main test flow**: resolve configs → call target via unified API → run evaluators on the response

## Interfaces
- Container `compliance-service`, host port **8001** → 8000. Build context is the repo root.
- Depends on: PostgreSQL, Redis, Milvus (full stack), `shared/unified_api`, `services/shared`.
- Consumed by: gateway proxy (`/api/...` routes exist for it).

## Rules
- **No new evaluation logic here.** New checks go in `plugins/evaluators/` (root rule 4). This service hosts only the evaluator *framework*.
- Evaluators implement `BaseEvaluator` (`get_metadata`, `evaluate`, `interpret`, `summarize_category_results`). Read scores through `metadata.primary_output_key`, not guessed field names.
- Judge/LLM failures must surface as errors. Don't add new silent fallbacks that turn an infra failure into a score.
- Model calls go through `shared/unified_api` only. No direct provider SDK calls.

## Verification
- Offline unit tests: `pytest tests/unit/test_evaluator.py tests/unit/test_compliance.py tests/unit/test_evaluator_plugins.py tests/unit/test_probe_evals.py -v`
  (no `pytest-asyncio` locally — run `py tests/unit/test_evaluator_plugins.py` to execute its `__main__` block)
- Live stack required: `tests/unit/test_systems_api.py`, `tests/unit/test_model_config.py` (these call localhost despite being in `unit/`).
- Evaluator framework change → also run every plugin through `test_evaluator_plugins.py`.
- End-to-end: create a system in the UI, attach a model, run a test, confirm the results page shows per-evaluator output.

## Decisions & Known Issues
- Passive evaluators only receive the target's response (`text=`). Probe evaluators (`requires_test_subject_config=True`) drive the target via `framework/probes/`.
- `BaseEvaluator.aevaluate()` exists (default wraps `evaluate` in a thread) but `systems.py` does not await it yet — wire it when the in-flight `systems.py` WIP lands.
- There are two test paths: `routers/systems.py` (calls the target) and `routers/system_tests.py` (evaluates prompts directly, with guessed score keys).
- `generic_compliance` exists both here and in `plugins/evaluators/`. `advanced_rag_service.py` duplicates the prompts service copy.
- `Registry` resolves display names, plugin dir names, and framework tags via slug lookup (`Registry._slug`).
- `g_eval_metric` is broken: `get_metadata()` references `EvaluatorCapability.GENERAL_TEXT_ANALYSIS`, which does not exist — it cannot register in `Registry` until fixed.
- `routers/plugins.py:315` calls `plugin_manager.install_plugin`, which does not exist.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline). Evaluator overhaul planned in `/plan.md`.
- 2026-11-11 — Phase 0 (partial) + Phase 1 landed: `aevaluate`, Registry slug lookup, `framework/probes/` kit, 3 probe plugins. `test_probe_evals.py` = 9 passed.
- 2026-11-11 — `systems.py` now awaits `aevaluate` at both evaluator call sites; `_calculate_overall_score` reads the nested result + `primary_output_key` (it previously read the wrapper and always scored 0).
- 2026-11-11 — Live-tested all 3 probes vs gemini-3.1-flash-lite via `/api/systems/{id}/test-unified`: leakage attack_success 93.3%, consumption 81.9, jailbreak robustness 87.5. Fixed en route: `./plugins` volume mount was missing from docker-compose (no plugin could ever load in-container); `model_configs.py` referenced nonexistent `top_p`/penalty fields; `UserAPIKey` ORM class was missing for the `api_key_id` FK. Plugins must be POSTed to `/plugins/{name}/load` after every service restart — nothing loads them at startup.
- 2026-11-11 — Probe harness supports native tool calling: `ProbeCase.native_tools: true` sends tool manifests via provider function-calling (no JSON-prompt instruction) and reads `resp.tool_calls`. Simulated JSON loop still used when `native_tools` is false/absent. `CallFn` implementations that support native tools must accept a `tools` kwarg and may return a 3-tuple `(text, usage, tool_calls)`.
- 2026-11-11 — `ProbeCase.mcp_server` (`{command, args, env}`): harness spawns the MCP server, merges its live tool manifests, and executes matching tool_calls via the real server instead of `output` fixtures. Works with both simulated-JSON and `native_tools` paths.
