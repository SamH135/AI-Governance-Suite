# AGENTS.md — plugins/ (evaluator plugins)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Active plan: `/plan.md` — new evaluators follow its probe-kit pattern once Phase 1 lands.

## Purpose
The extension point for compliance checks. Every new evaluator is a plugin here (root rule 4).

## Layout
- `evaluators/<name>/` — one plugin per directory:
  - `plugin.py` — subclass of `PluginInterface` (`services/compliance/services/evaluators/plugin_manager.py`); loads `evaluator.py` via `importlib`
  - `evaluator.py` — subclass of `BaseEvaluator` (`services/compliance/framework/core/base.py`): `get_metadata`, `evaluate`, `interpret`, `summarize_category_results`
  - `metadata.yaml` — `name`, `version`, `framework`, `category`, `tags`, `config_schema`
- Current plugins: `example_plugin`, `excessive_agency`, `g_eval_metric`, `generic_compliance`, `hallucination_checker`, `insecure_output`, `pii_leakage`, `prompt_injection`
- `configs/` — plugin config examples (placeholder values only)

## Interfaces
- Discovery: any `evaluators/<dir>/` containing `plugin.py`. Loaded by the compliance service and registered in its `Registry`.
- Input: the target response (`text`), `test_subject_config`, `evaluator_llm_config`, optional RAG/vector store. Output: a dict whose main score is `metadata.primary_output_key`.

## Rules
- Reference implementation: `evaluators/hallucination_checker/`. Copy its structure.
- Keep `plugin.py` metadata and `metadata.yaml` in sync (name, version, tags).
- Tag framework references in `tags` (e.g. `llm07`) now; `/plan.md` adds a structured `framework_refs` block.
- A judge/LLM failure must raise or be reported as an error, not silently downgraded to a score.
- No secrets in `configs/` or `cases/`. Harmful red-team corpora are **not committed** (see `.gitignore` `prompts/`).

## Verification
- Add the plugin name to `expected_plugins` in `tests/unit/test_evaluator_plugins.py`, then run it.
- Write a per-plugin unit test (`tests/unit/test_plugin_<name>.py`) with a fake target: one vulnerable and one safe response, and assert the result flips. No network.
- New probes must be shown to fail on a deliberately unprotected target before their passes are trusted (`/plan.md` §6).

## Decisions & Known Issues
- Plugins currently judge only the response text. Active probes that drive the target are planned (`/plan.md`).
- `generic_compliance` is duplicated in `services/compliance/framework/evaluators/`.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
