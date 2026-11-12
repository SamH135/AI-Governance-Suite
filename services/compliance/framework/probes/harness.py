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
            raise RuntimeError(f"Test subject call failed: {resp.error.message}")
        return resp.content or "", resp.usage or {}, resp.tool_calls

    return call


_TOOL_INSTRUCTION = (
    "You can call tools by replying with ONLY a JSON object like "
    '{{"tool_call": {{"name": "<tool>", "args": {{...}}}}}}. Available tools: {desc}'
)


def _find_tool(tools, name):
    return next((t for t in tools if t.get("name") == name), None)


def run_case(case: ProbeCase, call_fn: CallFn) -> Transcript:
    """Execute one case: scripted turns, RAG docs, and a simulated tool loop."""
    transcript = Transcript(case_id=case.id)
    system_prompt = case.system_prompt
    messages: List[Dict[str, str]] = []
    context = list(case.docs) or None

    if case.tools and not case.native_tools:
        desc = "; ".join(f"{t['name']}: {t.get('description', '')}" for t in case.tools)
        tool_note = _TOOL_INSTRUCTION.format(desc=desc)
        system_prompt = f"{system_prompt}\n\n{tool_note}" if system_prompt else tool_note

    # Strip simulated `output` fixtures before sending manifests to the provider
    native_manifests = (
        [{k: v for k, v in t.items() if k != "output"} for t in case.tools]
        if case.native_tools and case.tools else None
    )

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
            if native_manifests is not None:
                reply = call_fn(messages, system_prompt, context, tools=native_manifests)
            else:
                reply = call_fn(messages, system_prompt, context)
            text, usage = reply[0], reply[1]
            native_calls = reply[2] if len(reply) > 2 else None
            transcript.latency_ms += (time.perf_counter() - start) * 1000
            for k, v in usage.items():
                transcript.usage[k] = transcript.usage.get(k, 0) + (v or 0)

            # shortcut: only the first native tool_call is replayed per step, multi-call loops upgrade if needed
            if native_manifests is not None:
                tool_call = (
                    {"name": tc.get("name"), "args": tc.get("arguments", {})}
                    for tc in (native_calls or [])
                )
                tool_call = next(tool_call, None)
            else:
                tool_call = _parse_tool_call(text) if case.tools else None
            if tool_call is None or steps >= case.max_tool_steps:
                transcript.turns.append(Turn(role="assistant", content=text))
                transcript.final_response = text
                messages.append({"role": "assistant", "content": text})
                break

            steps += 1
            name = tool_call.get("name", "")
            tool = _find_tool(case.tools, name)
            transcript.turns.append(Turn(role="assistant", content=text, tool_call=tool_call))
            transcript.tool_calls.append(tool_call)
            output = tool.get("output", f"Error: unknown tool '{name}'") if tool else f"Error: unknown tool '{name}'"
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"[tool result for {name}]\n{output}"})
            transcript.turns.append(Turn(role="tool", content=str(output)))

    return transcript


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r'\{[^{}]*"tool_call"[^{}]*\{.*\}.*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0)).get("tool_call")
    except json.JSONDecodeError:
        return None
