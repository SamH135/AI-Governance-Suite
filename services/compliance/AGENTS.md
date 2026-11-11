# AGENTS.md — services/compliance/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Active plan: `/plan.md` (evaluator overhaul) — read it before touching evaluator plumbing.

## Purpose
Evaluation engine: AI systems + model configs CRUD, runs compliance tests against a target model, executes evaluators (built-in + plugins), RAG context, reports.

## Layout
- `main.py` — routers: `/compliance`, `/evaluators` (+ `/api/evaluators`), `/reports`, `/local-models`, `/plugins`, `/plugin-generator`, `/api` (models, model-configs, systems, system-tests)
- `framework/core/` — `base.py` (`BaseEvaluator` contract, `EvaluatorMetadata`), `registry.py` (evaluator discovery), `model_manager.py`
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
- Offline unit tests: `pytest tests/unit/test_evaluator.py tests/unit/test_compliance.py tests/unit/test_evaluator_plugins.py -v`
- Live stack required: `tests/unit/test_systems_api.py`, `tests/unit/test_model_config.py` (these call localhost despite being in `unit/`).
- Evaluator framework change → also run every plugin through `test_evaluator_plugins.py`.
- End-to-end: create a system in the UI, attach a model, run a test, confirm the results page shows per-evaluator output.

## Decisions & Known Issues
- Evaluators only receive the target's response (`text=`), never the attack prompt or conversation. Overhaul tracked in `/plan.md` §2.
- `BaseEvaluator.evaluate()` is sync but called from async tasks. `plan.md` Phase 0 adds `aevaluate()`.
- There are two test paths: `routers/systems.py` (calls the target) and `routers/system_tests.py` (evaluates prompts directly, with guessed score keys).
- `generic_compliance` exists both here and in `plugins/evaluators/`. `advanced_rag_service.py` duplicates the prompts service copy.
- `Registry` keys evaluators by `metadata.name`; requests use plugin directory names. Verify the mapping before adding plugins.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline). Evaluator overhaul planned in `/plan.md`.
