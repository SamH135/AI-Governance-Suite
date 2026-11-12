# AGENTS.md — shared/ (Unified AI API + platform types)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Not to be confused with `services/shared/` (backend service utilities).

## Purpose
Model-agnostic LLM access layer used by all services: one interface over OpenAI, Anthropic, Google, HuggingFace, and local models. Plus root-level platform types.

## Layout
- `unified_api/base.py` — `ModelConfig`, `ModelRequest` (`prompt`, `system_prompt`, `messages`), `ModelResponse`, `BaseModelProvider` (`generate`, `agenerate`, `stream`, `astream`, `list_models`)
- `unified_api/api.py` — facade (`generate` / `agenerate`); `registry.py` — `ProviderRegistry` auto-discovery; `config.py` — env-based key lookup
- `unified_api/providers/` — `openai`, `anthropic`, `google`, `huggingface`, `local`, `predetermined_responses` (canned responses for cost-free testing)
- `platform_types.py` — shared type definitions

## Interfaces
- Imported by compliance, prompts, and other services (mounted into containers). Full guide: `docs/UNIFIED_AI_API.md`.

## Rules
- Adding a provider = a new `BaseModelProvider` subclass in `providers/`, auto-registered by the registry. Don't special-case providers in callers.
- Provider-specific parameters go in `ModelConfig.provider_options`, not new top-level fields.
- **No hardcoded model lists.** Rely on the provider's `list_models()`.
- API keys come from config or env. Never log keys or full requests.
- Native tool calling uses generic manifests on `ModelRequest.tools` (`{name, description, parameters}`); each provider maps to its own format. Agentic evals can also use the simulated JSON protocol for providers without tool APIs (`native_tools` on `ProbeCase`).

## Verification
- Offline: `pytest tests/unit/test_unified_api.py -v`
- Real providers (needs keys in env, costs money): `pytest tests/integration/test_unified_api_providers.py -v`
- Use the `predetermined_responses` provider for tests that shouldn't spend inference credits.

## Decisions & Known Issues
- 2025: removed hardcoded model names from providers and the DB in favor of `list_models()`.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-11 — Native tool/function calling added: `ModelRequest.tools` (generic manifests `{name, description, parameters}`) and `ModelResponse.tool_calls` (`[{name, arguments}]`). Google, OpenAI (sync+async), Anthropic adapters map to/from their native formats. `api.generate(..., tools=...)` threads through.
- 2026-11-11 — `mcp_client.py`: `MCPToolset` — hand-rolled stdio JSON-RPC client (no deps; official `mcp` SDK requires anyio>=4 which conflicts with fastapi 0.104.x). `connect(command, args, env)` / `tools()` -> generic manifests / `call(name, args)` / `close()`. No HTTP transport yet.
