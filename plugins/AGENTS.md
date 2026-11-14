# AGENTS.md — plugins/ (evaluator plugins)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.
> Active plan: `/plan.md` — new evaluators follow its probe-kit pattern once Phase 1 lands.

## Purpose
The extension point for compliance checks. Every new evaluator is a plugin here (root rule 4).

## Layout
- `evaluators/<name>/` — one plugin per directory:
  - `plugin.py` — subclass of `PluginInterface` (`services/compliance/services/evaluators/plugin_manager.py`); loads `evaluator.py` via `importlib`
  - `evaluator.py` — subclass of `BaseEvaluator` (`services/compliance/framework/core/base.py`): `get_metadata`, `evaluate`, `interpret`, `summarize_category_results`
  - `metadata.yaml` — `name`, `version`, `framework`, `category`, `tags`, `config_schema`
- Current plugins:
  - Passive (judge the response text): `example_plugin`, `excessive_agency`, `generic_compliance`, `hallucination_checker`, `insecure_output`, `pii_leakage`, `prompt_injection`
  - Probe (drive the target model, `requires_test_subject_config=True`): `system_prompt_leakage`, `unbounded_consumption`, `jailbreak_robustness`, `indirect_prompt_injection`, `vector_embedding_security`, `tool_misuse`, `tool_poisoning`, `memory_poisoning`, `multi_turn_escalation`
  - Hybrid: `excessive_agency` is passive by default and adds an `agentic_probe` block when `test_subject_config` is provided
- `cases/*.json` — probe corpora (`ProbeCase` dicts loaded via `framework/probes.load_cases`)
- `configs/` — plugin config examples (placeholder values only)

## Interfaces
- Discovery: any `evaluators/<dir>/` containing `plugin.py`. Loaded by the compliance service and registered in its `Registry`.
- Input: the target response (`text`), `test_subject_config`, `evaluator_llm_config`, optional RAG/vector store. Output: a dict whose main score is `metadata.primary_output_key`.

## Rules
- Reference implementation: `evaluators/hallucination_checker/`. Copy its structure.
- Keep `plugin.py` metadata and `metadata.yaml` in sync (name, version, tags).
- Tag framework references in `tags` (e.g. `llm07`) now; `/plan.md` adds a structured `framework_refs` block.
- A judge/LLM failure must raise or be reported as an error, not silently downgraded to a score.
- Probe evaluators use `framework/probes/`: build `Check`s, `load_cases()`, `run_suite(cases, checks, call_fn)`. Accept a `call_fn` kwarg in `evaluate()` so tests can inject a fake target (`test_probe_evals.py` is the example).
- No secrets in `configs/` or `cases/`. Harmful red-team corpora are **not committed** (see `.gitignore` `prompts/`).

## Verification
- Add the plugin name to `expected_plugins` in `tests/unit/test_evaluator_plugins.py`, then run it.
- Live-verify through the real pipeline before calling it done: `RUN_LIVE_EVALS=1 LIVE_EVAL_PASSWORD=<pw> LIVE_EVAL_SYSTEM_ID=<id> LIVE_EVAL_SET=<plugin> pytest tests/integration/test_probe_live.py` (add the plugin name to `PROBE_EVALUATORS` in that file). Asserts pipeline correctness, not score values — live outputs are nondeterministic.
- Write a per-plugin unit test (`tests/unit/test_plugin_<name>.py`) with a fake target: one vulnerable and one safe response, and assert the result flips. No network.
- New probes must be shown to fail on a deliberately unprotected target before their passes are trusted (`/plan.md` §6).

## Decisions & Known Issues
- Two evaluator styles coexist: passive (score `text`) and probe (drive the target via `framework/probes/`). Remaining Tier-1/Tier-2 probes tracked in `/plan.md`.
- `generic_compliance` is duplicated in `services/compliance/framework/evaluators/`.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-11 — Added probe evaluators `system_prompt_leakage`, `unbounded_consumption`, `jailbreak_robustness` on the new `framework/probes/` kit (`/plan.md` Phase 1-2).
- 2026-11-11 — Added `indirect_prompt_injection`, `vector_embedding_security` (fixture-simulated), `tool_misuse`, `tool_poisoning`, `memory_poisoning`, `multi_turn_escalation`; `excessive_agency` gained a behavioral probe mode.
- 2026-11-12 — Tier-3 metric plugins: `counterfactual_fairness` (demographic-swap pairs), `multilingual_robustness` (per-language ASR), `model_extraction` (verbatim memorization), `code_execution` (ASI05 exec-tool probes).
- 2026-11-13 — Integrity fixes: checks that fired on ANY tool call now only score declared poisoned/forbidden tools (`refs.forbidden_tools` in cases; user-sanctioned calls no longer count as misuse/poisoning/unsafe-exec). `excessive_agency` declares `primary_output_key="agency_score"`; risk-direction evaluators declare `score_higher_is_better=False` (agency/compliance/PII/injection/security/hallucination/bias/safety). `example_plugin` marked demo-only (constant scores, never runnable). `hallucination_checker.evaluate` accepts framework kwargs (was guaranteed TypeError). `generic_compliance` no longer logs raw LLM responses; parse failures raise. `hallucination_checker` now errors when no evidence is retrievable (was flat score-50). Provenance: all probe plugins declare `judge` (`judge_label(config)` → `provider/model_id`, `deterministic`, or `none`). `vector_embedding_security` checks doc-supplied canaries instead of any-tool-call.
- 2026-11-13 — Eval-integrity fixes: `pii_leakage` dropped the bare Title-Case-bigram name pattern (kept the honorific form, `[ \t]+` separators) and flags `judge_disagreement` when LLM=0 < rule score; `model_extraction` matcher is now `difflib.SequenceMatcher` over normalized word lists and `partial_match_ratio` reports `match_ratio*100`.
- 2026-11-14 — `vector_embedding_security`: `cross_tenant_canary_leak`/`poisoned_doc_followed` now scope canaries by the `tenant=` tag of the doc they're planted in (previously both checks fired on any surfaced canary — same-tenant poison hits were mislabeled as cross-tenant leaks). `judges.canary_hit(canaries=)` accepts a scoped subset.
- 2026-11-14 — `model_extraction`: `_prefix_match_ratio` now slides an expected-length window over the output instead of comparing whole-output vs expected (SequenceMatcher diluted verbatim recitations inside long replies to ~0.1 — systematic false negatives, extraction rate understated ~2.5x).
- 2026-11-14 — `counterfactual_fairness`: limitation discloses same-conversation pairing (consistency under observation, not blind counterfactual).
