# Unified AI API

Model-agnostic LLM access layer used by all services. One `generate`/`agenerate` interface over OpenAI, Anthropic, Google, HuggingFace, and local models. Code lives in `shared/unified_api/`; see `shared/AGENTS.md` for the area rules.

## Layout

- `base.py` — dataclasses and the provider contract:
  - `ModelConfig(provider, model_id, api_key, api_url, temperature, max_tokens, timeout, max_retries, retry_delay, provider_options, usage_type, metadata)`
  - `ModelRequest(prompt, system_prompt, messages, context, tools, temperature, max_tokens, kwargs)`
  - `ModelResponse(content, model_id, provider, tool_calls, usage, metadata, error, latency)` — `error` is an `APIErrorDetail(message, code, type, details)`
  - `BaseModelProvider` — abstract: `generate`, `agenerate`, `stream`, `astream`, `list_models`, `get_provider_name`, `validate_config` (static, raises `ValueError`)
  - `ModelType` — `TEST_SUBJECT | EVALUATOR | RAG | UTILITY` (usage classification)
- `api.py` — `UnifiedModelAPI` facade and `get_unified_api()` singleton
- `registry.py` — `ProviderRegistry`: auto-discovers `BaseModelProvider` subclasses in `providers/` via `pkgutil`, plus alias resolution (e.g. `claude` → `anthropic`, `mock`/`test` → `local`)
- `config.py` — `ConfigManager`: env-var key lookup (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`, `GOOGLE_API_KEY`), default models and API URLs per provider
- `providers/` — `openai`, `anthropic`, `google`, `huggingface`, `local`, `predetermined_responses` (canned dataset used by `local` for cost-free testing)
- `mcp_client.py` — `MCPToolset`, a stdio JSON-RPC MCP client (see below)

## Usage

```python
from shared.unified_api import get_unified_api, ModelConfig

config = ModelConfig(
    provider="google",
    model_id="gemini-3.1-flash-lite",
    api_key="...",                    # falls back to the provider's env var if unset
    temperature=0.7,
    max_tokens=1000,
)

response = get_unified_api().generate(
    prompt="Summarize this text.",
    config=config,
    system_prompt="You are a compliance analyst.",
    messages=[{"role": "user", "content": "earlier turn"}],
    temperature=0.2,
)

if response.error:
    raise RuntimeError(response.error.message)
print(response.content, response.usage, response.tool_calls)
```

`generate` is synchronous; `agenerate` has the same signature minus `tools` and awaits `provider.agenerate`. Extra keyword arguments land on `ModelRequest.kwargs`. `config` also accepts a plain `dict`, which `ConfigManager` fills in (api key from env, default model, api_url).

## API key resolution

When `ModelConfig.api_key` is unset, `ConfigManager.get_api_key` first tries saved user keys (via the gateway) and then falls back to the provider's env var. Per-user keys are stored Fernet-encrypted in the `user_api_keys` table and are decrypted in the compliance service (`systems.py::_resolve_model_config`) via `get_encryption_fernet()` — requires `API_KEY_ENCRYPTION_KEY`.

## OpenAI-compatible endpoints (Groq, DeepSeek, vLLM…)

Use `provider="openai"` with `api_url` pointed at the compatible base URL — the OpenAI provider sends its standard chat-completions payload to `config.api_url` instead of the default OpenAI endpoint.

## Native tool calling

Pass generic manifests on `generate(tools=[...])`:

```python
tools = [{"name": "read_file", "description": "Reads a file", "parameters": {"type": "object", "properties": {}}}]
resp = api.generate(prompt="read x", config=config, tools=tools)
# resp.tool_calls -> [{"name": "read_file", "arguments": {...}}] or None
```

OpenAI (sync+async), Anthropic, and Google map these to/from their native function-calling formats. `ModelResponse.tool_calls` is a list of `{name, arguments}`.

## MCP tools

`MCPToolset` (in `mcp_client.py`) is a hand-rolled, dependency-free stdio JSON-RPC client. The probe harness is synchronous and the official `mcp` SDK is anyio-async, so adopting the SDK would mean bridging an event loop into a sync call path for no functional gain:

```python
mcp = MCPToolset().connect(command="python", args=["server.py"], env={})
manifests = mcp.tools()          # generic manifests for the tools= kwarg
output = mcp.call("read_secret", {"path": "/etc/passwd"})
mcp.close()
```

Stdio transport only — no HTTP/SSE transport yet.

## Provider notes

- **Google (Gemini):** `request.messages` becomes alternating `contents` (`assistant` → `model`; consecutive same-role messages merge into one content with multiple `parts`). `system_prompt` is sent as top-level `systemInstruction`. A candidate with no text or functionCall parts returns `ModelResponse.error` with `type="blocked"` (e.g. a `SAFETY` finishReason) instead of stringified JSON. Known limit: `stream`/`astream` send only `request.prompt` — no messages history or `systemInstruction`.
- **Local:** returns canned responses from `providers/predetermined_responses.py`; the aliases `mock` and `test` resolve to `local`. Use it for tests that shouldn't spend inference credits.
- Providers auto-discover on import — a new `BaseModelProvider` subclass dropped into `providers/` registers itself; no registry edits needed.

## Verification

- Offline: the fake-target tests in `tests/unit/test_probe_evals.py` and `tests/unit/test_eval_integrity.py` (the latter covers the Gemini payload mapping)
- Real providers (needs keys in env, costs money): `pytest tests/integration/test_unified_api_providers.py -v`
