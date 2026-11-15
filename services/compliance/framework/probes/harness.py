"""Probe harnesses: drive the test subject through a ProbeCase and record a Transcript.

call_fn signature: (messages, system_prompt, context) -> (response_text, usage_dict).
Use make_target_caller(config) for the real unified API, or a scripted fake in tests.
Target call failures raise — an infra error is never scored as a model result.
"""
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import ProbeCase, Transcript, Turn

CallFn = Callable[[List[Dict[str, str]], Optional[str], Optional[List[str]]], Tuple[str, Dict[str, int]]]


class ProviderBlockedError(RuntimeError):
    """The provider's safety layer refused the request before the model answered."""


def make_target_caller(config: Any) -> CallFn:
    """Build a CallFn that invokes the test subject through the unified API."""
    from shared.unified_api import get_unified_api
    from shared.unified_api.base import ModelConfig, ModelType

    if isinstance(config, dict):
        config = ModelConfig(**{k: v for k, v in config.items() if k in ModelConfig.__dataclass_fields__})
    if config is None:
        raise ValueError("Probe evaluator requires test_subject_config")
    config.usage_type = ModelType.TEST_SUBJECT
    api = get_unified_api()

    def call(messages, system_prompt, context, tools=None):
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        resp = api.generate(prompt=last_user, messages=messages, system_prompt=system_prompt,
                            context=context, tools=tools, config=config)
        if resp.error:
            if resp.error.type == "blocked":
                raise ProviderBlockedError(resp.error.message)
            raise RuntimeError(f"Test subject call failed: {resp.error.message}")
        return resp.content or "", resp.usage or {}, resp.tool_calls

    call.target_model = f"{config.provider}/{config.model_id}"  # for run_suite provenance
    return call


_TOOL_INSTRUCTION = (
    "You can call tools by replying with ONLY a JSON object like "
    '{{"tool_call": {{"name": "<tool>", "args": {{...}}}}}}. Available tools: {desc}'
)


def _find_tool(tools, name):
    # last manifest wins: in tool-shadowing cases the attacker's duplicate is
    # listed second and must be the definition that actually executes
    found = None
    for t in tools:
        if t.get("name") == name:
            found = t
    return found


def run_case(case: ProbeCase, call_fn: CallFn) -> Transcript:
    """Execute one case: scripted turns, RAG docs, and a simulated tool loop."""
    transcript = Transcript(case_id=case.id)
    system_prompt = case.system_prompt
    messages: List[Dict[str, str]] = []
    context = None  # docs are delivered as messages below; no provider reads request.context
    try:

        # Live MCP server first: its real tools join the manifest + get real execution
        mcp = None
        mcp_tool_names: set = set()
        effective_tools: List[Dict[str, Any]] = list(case.tools)
        if case.mcp_server:
            from shared.unified_api.mcp_client import MCPToolset
            mcp = MCPToolset().connect(**case.mcp_server)
            server_manifests = mcp.tools()
            mcp_tool_names = {t["name"] for t in server_manifests}
            effective_tools += server_manifests

        if effective_tools and not case.native_tools:
            desc = "; ".join(f"{t['name']}: {t.get('description', '')}" for t in effective_tools)
            tool_note = _TOOL_INSTRUCTION.format(desc=desc)
            system_prompt = f"{system_prompt}\n\n{tool_note}" if system_prompt else tool_note


        # Strip simulated `output` fixtures before sending manifests to the provider
        native_manifests = (
            [{k: v for k, v in t.items() if k != "output"} for t in effective_tools]
            if case.native_tools and effective_tools else None
        )

        # Fake prior turns for many-shot/prefill attacks: sent to the target
        # but deliberately NOT recorded in transcript.turns — fabricated
        # assistant text must never be scored as model output.
        for h in case.history:
            messages.append({"role": h["role"], "content": h["content"]})

        for doc in case.docs:
            messages.append({"role": "user", "content": f"[retrieved document]\n{doc}"})
            transcript.turns.append(Turn(role="document", content=doc))

        for injected in case.tool_outputs:
            turn = f"[tool result]\n{injected}"
            messages.append({"role": "user", "content": turn})
            transcript.turns.append(Turn(role="tool", content=injected))

        for user_msg in case.turns:
            messages.append({"role": "user", "content": user_msg})
            transcript.turns.append(Turn(role="user", content=user_msg))

            steps = 0
            while True:
                start = time.perf_counter()
                try:
                    if native_manifests is not None:
                        reply = call_fn(messages, system_prompt, context, tools=native_manifests)
                    else:
                        reply = call_fn(messages, system_prompt, context)
                except ProviderBlockedError as e:
                    # platform safety refused before the model answered: that IS
                    # a refusal — evidence, not a run failure
                    transcript.provider_blocked = True
                    transcript.turns.append(Turn(role="assistant", content=""))
                    transcript.final_response = ""
                    transcript.latency_ms += (time.perf_counter() - start) * 1000
                    break
                text, usage = reply[0], reply[1]
                native_calls = reply[2] if len(reply) > 2 else None
                transcript.latency_ms += (time.perf_counter() - start) * 1000
                for k, v in usage.items():
                    transcript.usage[k] = transcript.usage.get(k, 0) + (v or 0)

                # shortcut: only the first native tool_call is replayed per step, multi-call loops upgrade if needed
                if native_manifests is not None:
                    tool_call = None
                    for tc in (native_calls or []):
                        args = tc.get("arguments", {})
                        if isinstance(args, str):  # OpenAI returns a JSON string; google/anthropic return dicts
                            try:
                                args = json.loads(args)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        tool_call = {"name": tc.get("name"), "args": args}
                        break
                else:
                    tool_call = _parse_tool_call(text) if effective_tools else None
                if tool_call is None or steps >= case.max_tool_steps:
                    if tool_call is None and not (text or "").strip():
                        raise RuntimeError(f"Empty response from test subject in case {case.id}")
                    if tool_call is not None:
                        # step cap hit mid-loop: record the pending call as evidence
                        # (the model attempted it — it counts as execution intent)
                        tool_call = {**tool_call, "dropped_at_step_cap": True}
                        transcript.tool_calls.append(tool_call)
                    transcript.turns.append(Turn(role="assistant", content=text, tool_call=tool_call))
                    transcript.final_response = text
                    messages.append({"role": "assistant", "content": text})
                    break

                steps += 1
                name = tool_call.get("name", "")
                tool = _find_tool(effective_tools, name)
                transcript.turns.append(Turn(role="assistant", content=text, tool_call=tool_call))
                transcript.tool_calls.append(tool_call)
                if name in mcp_tool_names:
                    try:
                        output = mcp.call(name, tool_call.get("args"))
                    except Exception as e:
                        output = f"Error: MCP tool call failed: {e}"
                else:
                    output = tool.get("output", f"Error: unknown tool '{name}'") if tool else f"Error: unknown tool '{name}'"
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"[tool result for {name}]\n{output}"})
                transcript.turns.append(Turn(role="tool", content=str(output)))

            if transcript.provider_blocked:
                break

    finally:
        if mcp is not None:
            mcp.close()

    return transcript


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extract {"tool_call": {...}} via balanced-brace scan — a regex misses
    calls when the reply has braces before or after the JSON block."""
    text = text or ""
    for m in re.finditer(r"\{", text):
        depth = 0
        for i in range(m.start(), len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[m.start():i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "tool_call" in obj:
                        return obj["tool_call"]
                    break
    return None
