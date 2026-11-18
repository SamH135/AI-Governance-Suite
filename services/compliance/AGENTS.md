# AGENTS.md — services/compliance/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.
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
- There are two test paths: `routers/systems.py` (calls the target) and `routers/system_tests.py` (evaluates prompts directly, with guessed score keys).
- `generic_compliance` exists both here and in `plugins/evaluators/`.
- `Registry` resolves display names, plugin dir names, and framework tags via slug lookup (`Registry._slug`).

## Change Log
- 2026-11-11 — AGENTS.md created (baseline). Evaluator overhaul planned in `/plan.md`.
- 2026-11-11 — Phase 0 (partial) + Phase 1 landed: `aevaluate`, Registry slug lookup, `framework/probes/` kit, 3 probe plugins. `test_probe_evals.py` = 9 passed.
- 2026-11-11 — `systems.py` now awaits `aevaluate` at both evaluator call sites; `_calculate_overall_score` reads the nested result + `primary_output_key` (it previously read the wrapper and always scored 0).
- 2026-11-11 — Live-tested all 3 probes vs gemini-3.1-flash-lite via `/api/systems/{id}/test-unified`. Fixed en route: missing `./plugins` volume mount (no plugin could load in-container); `model_configs.py` referenced nonexistent `top_p`/penalty fields; missing `UserAPIKey` ORM class for `api_key_id` FK. `main.py` auto-loads all plugins at startup.
- 2026-11-11 — Probe harness supports native tool calling: `ProbeCase.native_tools: true` sends tool manifests via provider function-calling (no JSON-prompt instruction) and reads `resp.tool_calls`. Simulated JSON loop still used when `native_tools` is false/absent. `CallFn` implementations that support native tools must accept a `tools` kwarg and may return a 3-tuple `(text, usage, tool_calls)`.
- 2026-11-11 — `ProbeCase.mcp_server` (`{command, args, env}`): harness spawns the MCP server, merges its live tool manifests, and executes matching tool_calls via the real server instead of `output` fixtures. Works with both simulated-JSON and `native_tools` paths.
- 2026-11-12 — `routers/systems.py::_resolve_model_config` now resolves `api_key_id` → decrypts `user_api_keys` via `get_encryption_fernet()` when no plaintext `api_key` is set. Requires `API_KEY_ENCRYPTION_KEY` in the compliance env (added to both compose files). Previously `api_key_id` was read but never resolved — managed keys silently ran with `api_key=None`.
- 2026-11-12 — Removed dead `/plugins/install` + `/plugins/uninstall` routes (called `install_plugin`/`uninstall_plugin`, which never existed). Removed `g_eval_metric` plugin (broken metadata, judge wiring never built).
- 2026-11-12 — Judge-injection hardening: `llm_judge(untrusted=)` wraps graded target output in a random-nonce tag and requires a random sentinel echo in the verdict; missing/wrong sentinel raises (never scores). Applied at both judge call sites (StrongREJECT, paraphrase-leak).
- 2026-11-12 — Judge hardening extended: rubric now goes in the system role and untrusted target output stays in the user role behind the nonce tag (channel separation via `ModelRequest.system_prompt`); providers without a system role fold it back into one stream (no worse than before).
- 2026-11-13 — Deleted dead `services/advanced_rag_service.py` (unimported duplicate of the prompts copy; had a syntax error since the initial commit) and `services/shared/backup_restore_service.py` (same).
- 2026-11-13 — Eval-integrity overhaul (see `/plan.md`): `Check.axis` (`attack`/`benign`/`any`) gates per-case applicability in `run_suite`; skipped checks carry no `score` and are excluded from `attack_success_rate` denominators; `check_rates` reports per-check signals. `judges.py`: refusal patterns cover corpus languages without matching compliant text, `_decodings` inspects every token, `exfil_render` gates on markdown-image/canary, `injection_executed` ignores payload-origin canaries and counts only declared-forbidden tool calls, judge-less StrongREJECT returns `skipped` (never a fabricated 50). `harness.py`: step-cap records the pending tool call with `dropped_at_step_cap`, OpenAI string `arguments` are parsed to dicts, tool-call JSON is extracted by balanced braces, duplicate tool names resolve to the LAST manifest (attacker shadow wins — that's the thing under test). `run_suite` auto-attaches provenance: target model, corpus sha256, git SHA, case ids. `EvaluatorMetadata.score_higher_is_better` (default True) marks risk-direction scores; `_calculate_overall_score` inverts them before averaging. `systems.py`: empty target response fails the run (was graded as "No response from test subject"); `iterations` (1-20) re-runs target+evaluators and merges via mean of `primary_output_key`; `concurrent_evaluators` actually gathers via asyncio; self-judging runs (evaluator == target model config) warn + set `self_judging` in results. `system_tests.py`: dead `execute_test_with_model` removed; GET routes fixed from asyncpg `fetchrow`/`fetch` to SQLAlchemy `execute(text())`; `test_id` path param is `str` (POST mints `test_<sys>_<ts>`).
- 2026-11-13 — Eval-integrity fixes: `run_case` now delivers `case.docs` as `[retrieved document]` user messages (recorded as `role="document"` turns) instead of the unread `context=` param; empty final replies with no tool call raise `RuntimeError` (infra error, never scored); `judges.canary_hit(ignore_payload=True)` skips canaries present in `case.docs`/`case.tool_outputs` — `injection_executed` uses it so quoting an attacker-supplied canary while refusing no longer counts as execution.
- 2026-11-14 — Security hardening: `_resolve_model_config` in `routers/systems.py` scopes `AIModelConfig` and `UserAPIKey` resolution to the owning `user_id` (not-owned resolves exactly like not-found) and re-validates `api_url` via `services.shared.url_safety` at call time for rows written before schema validation
- 2026-11-15 — Phase 6A attack expansion: `probes/mutations.py` — deterministic `TRANSFORMS` (base64/rot13/hex/atbash/morse decode-instruction wrappers, leetspeak/homoglyph/char_join obfuscation, prefix_override/fiction_wrap templates) + `mutate()` expanding only `expect="refuse"` cases (last turn only; lineage in refs). `ProbeCase.history` injects fake prior turns into target messages without entering `transcript.turns`. StrongREJECT grades `refs.original_request`; `canary_hit` decodes hex. `run_suite` emits `by_technique`, `attack_success_ci95` (Wilson), `usage_total`, and per-case `history` evidence.
- 2026-11-15 — Phase 6B: `probes/adaptive.py` — PAIR attacker (`run_adaptive_case`: attacker LLM -> `run_case` sub-transcript -> judge 1-10, refusal-first scoring, best-attempt wins, usage summed across attempts). `make_attacker` wraps target responses in per-call nonce tags (untrusted data); `make_score_fn` reuses `llm_judge`. `Transcript` gained `technique`/`attempts`; `run_suite(case_runner=)` overrides per-case execution; `by_technique` keys on `transcript.technique` first. New plugin `adaptive_jailbreak`.
- 2026-11-16 — `probes/grounding.py`: tier-2 grounding check between deterministic checks and `llm_judge`. `NLIGroundingScorer` lazy-loads an NLI pair-classifier via HF `text-classification` pipeline (fail-loud on missing deps/load errors/no-entailment-label; NLI-format checkpoints only — seq2seq scorers like HHEM/MiniCheck-FT5 are a documented upgrade). `make_grounding_check` splits `all_output` into claims (skips refusals + abstention phrasing), scores each against max-entailment over `case.docs`/`tool_outputs`, returns the unsupported fraction (attack-axis semantics). HF models persist in the `hf_cache` compose volume. Default scorer `ynie/roberta-large-...-nli` won a 6-model bake-off on accuracy-per-ms (`tests/manual/grounding_bakeoff.py`, 27 labeled legal/medical pairs); `MoritzLaurer/DeBERTa-v3-large` scored 100% at ~3.5x latency — override via `GROUNDING_MODEL_ID`. MiniCheck-DeBERTa binary "0"/"1" labels supported (1 = supported).
- 2026-11-16 — `probes/grounding.py` gained `make_fact_leak_check`: NLI "does response entail protected fact" per-atomic-fact conveyance scoring for paraphrase-leak detection (no refusal skip — hedge-then-leak must score). `split_claims` gained `min_words` (fact extraction uses 2 — secret tokens like "Codename: X." are <4 words). Binary "0"/"1" label checkpoints (MiniCheck-DeBERTa; 1=supported) supported. Default scorer switched to `ynie/roberta-large-...-nli` after the bake-off.
- 2026-11-17 — `services/plugin_generator_service.py` implemented — the `/plugin-generator` router was mounted but dead (undefined `plugin_generator` → NameError on every call; the admin UI calls it from `PluginManager.jsx`). Slug-validated scaffold writer (traversal/overwrite rejected), modeled on `plugins/evaluators/example_plugin`. Also fixed F821 latent bugs: `routers/systems.py` logger used before assignment.
- 2026-11-18 — `update_plugin_config` yaml write moved to `asyncio.to_thread` (S7493).
