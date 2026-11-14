# Custom Evaluator Plugin System

The AI Governance Suite loads compliance evaluators from `plugins/evaluators/` at startup. A plugin is a directory containing a `plugin.py` (the `PluginInterface` wrapper) plus `evaluator.py` (the `BaseEvaluator` implementation) and `metadata.yaml`. See `plugins/AGENTS.md` for the authoritative rules — this file is a guided tour.

## Layout

```
plugins/
├── evaluators/
│   ├── example_plugin/
│   │   ├── plugin.py        # PluginInterface implementation
│   │   └── metadata.yaml    # name, version, framework, category, tags
│   └── <your_plugin>/       # one directory per evaluator
└── configs/                  # optional per-plugin YAML config (e.g. example_plugin.yaml)
```

Code that manages plugins lives in the compliance service:

- `services/compliance/services/evaluators/plugin_manager.py` — `PluginManager` (discovery, load/unload) and `PluginInterface` (abstract: `get_metadata`, `get_evaluator_class`; optional `on_load`/`on_unload` hooks)
- `services/compliance/services/evaluators/enhanced_evaluator_factory.py` — `EnhancedEvaluatorFactory` (built-in + plugin evaluators, framework statistics)
- `services/compliance/framework/core/registry.py` — `Registry` slug lookup (dir name, display name, framework tag)
- `services/compliance/routers/plugins.py` — plugin management API
- `services/compliance/routers/plugin_generator.py` — plugin scaffolding API

## Evaluator contract

Every evaluator subclasses `BaseEvaluator` (`services/compliance/framework/core/base.py`) and implements:

- `get_metadata()` → `EvaluatorMetadata` (name, category, tags, `primary_output_key`, `requires_test_subject_config`, …)
- `evaluate(text, test_subject_config=None, evaluator_llm_config=None, rag_config=None, vector_store=None, **kwargs)` → result dict
- `interpret(results)` → human-readable summary
- `summarize_category_results(category_results)` → aggregate summary

And the plugin wrapper subclasses `PluginInterface`:

```python
from typing import Any, Dict, Type
from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.framework.core.base import BaseEvaluator


class MyPlugin(PluginInterface):
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "my_plugin",
            "version": "1.0.0",
            "description": "My custom evaluator",
            "framework": "MY_FRAMEWORK",
            "category": "custom",
        }

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        from .evaluator import MyEvaluator
        return MyEvaluator
```

`plugins/evaluators/hallucination_checker/` is the reference implementation — copy its structure. Keep `plugin.py` metadata and `metadata.yaml` in sync.

## Two evaluator styles

- **Passive** — scores the target's `text` (e.g. `pii_leakage`, `hallucination_checker`, `insecure_output`).
- **Probe** — drives the target model through scripted scenarios (`requires_test_subject_config=True`; e.g. `system_prompt_leakage`, `tool_misuse`, `model_extraction`, `code_execution`).

### Probe pattern

Probe evaluators use the kit in `services/compliance/framework/probes/`:

```python
from services.compliance.framework.probes import (
    Check, judges, load_cases, make_target_caller, run_suite,
)

class MyProbeEvaluator(BaseEvaluator):
    def evaluate(self, text, test_subject_config=None, **kwargs):
        call_fn = kwargs.get("call_fn") or make_target_caller(test_subject_config)
        cases = load_cases(Path(__file__).parent / "cases" / "cases.json")
        return run_suite(cases, self._checks(), call_fn, provenance={...})
```

- A `ProbeCase` is an immutable scenario: scripted `turns`, optional `system_prompt`, RAG `docs`, simulated `tools`/`tool_outputs`, `canaries`, `expect`, `native_tools`, `mcp_server`.
- A `Check` maps `(transcript, case) -> (score, evidence)`; `weight=0` records a metric.
- `judges` provides deterministic helpers (`canary_hit`, `is_refusal`, `injection_executed`, `exfil_render`, `tool_called`) and `llm_judge` for LLM-as-judge.
- Tests inject a scripted `call_fn` so no network is needed — see `tests/unit/test_probe_evals.py` and `test_eval_integrity.py`.
- Target-call and judge failures raise — an infra error is never scored.

## Plugin management API

Mounted at `/plugins` in the compliance service (`routers/plugins.py`):

| Endpoint | Method | Description |
|---|---|---|
| `/plugins/` | GET | List all plugins |
| `/plugins/{name}` | GET | Plugin details |
| `/plugins/{name}/load` | POST | Load plugin |
| `/plugins/{name}/unload` | POST | Unload plugin |
| `/plugins/{name}/reload` | POST | Reload plugin |
| `/plugins/{name}/enable` | POST | Enable plugin |
| `/plugins/{name}/disable` | POST | Disable plugin |
| `/plugins/{name}/config` | GET / PUT | Read / update plugin config |
| `/plugins/{name}/validate-config` | POST | Validate a config against the plugin schema |

There is no file-upload install or delete endpoint — plugins are added by dropping a directory into `plugins/evaluators/` (mounted into the container) and reloading.

## Plugin generator API

Mounted at `/plugin-generator` (`routers/plugin_generator.py`):

| Endpoint | Method | Description |
|---|---|---|
| `/plugin-generator/templates` | GET | List templates |
| `/plugin-generator/generate` | POST | Generate a plugin scaffold |
| `/plugin-generator/generate-from-template` | POST | Generate from a named template |
| `/plugin-generator/schema-examples` | GET | Config schema examples |
| `/plugin-generator/test-case-examples` | GET | Test case examples |
| `/plugin-generator/validate-plugin-name` | POST | Validate a plugin name |

## Evaluator discovery API

`/evaluators/` and `/api/evaluators/` (the latter for the gateway proxy): list evaluators, get details by framework, per-category listing, health, and `POST /evaluators/test/{framework}` / `/test-with-saved-keys/{framework}`.

## LLM access inside evaluators

Model calls go through `shared/unified_api` only — never provider SDKs directly:

```python
from shared.unified_api import get_unified_api

resp = get_unified_api().generate(prompt=..., system_prompt=..., config=evaluator_llm_config)
if resp.error:
    raise RuntimeError(resp.error.message)   # judge/LLM failures must surface as errors
```

See `docs/UNIFIED_AI_API.md`. A judge/LLM failure must raise or be reported as an error, not silently downgraded to a score (`plugins/AGENTS.md`).

## Frontend

`frontend/src/components/PluginManager.jsx` is the management UI (list, load/unload, enable/disable, config).

## Verification

- Offline: `py tests/unit/test_evaluator_plugins.py` (add the plugin to `expected_plugins`), plus `pytest tests/unit/test_probe_evals.py -v`.
- Per-plugin unit test: fake `call_fn`, one vulnerable and one safe response, assert the score flips — see `tests/unit/test_probe_evals.py`.
- Live: `RUN_LIVE_EVALS=1 LIVE_EVAL_PASSWORD=... LIVE_EVAL_SYSTEM_ID=<id> pytest tests/integration/test_probe_live.py` (add the plugin to `PROBE_EVALUATORS`).
