"""Offline tests for the probe kit and probe-style evaluator plugins.

Every evaluator is driven by scripted fake targets (vulnerable + safe), so
these tests need no network, API keys, or running services.
"""
import asyncio
import sys
from pathlib import Path

import pytest

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.compliance.framework.core.base import BaseEvaluator, EvaluatorMetadata
from services.compliance.framework.core.registry import Registry
from services.compliance.framework.probes import Check, ProbeCase, judges, run_case, run_suite

from plugins.evaluators.system_prompt_leakage.evaluator import SystemPromptLeakageEvaluator
from plugins.evaluators.unbounded_consumption.evaluator import UnboundedConsumptionEvaluator
from plugins.evaluators.jailbreak_robustness.evaluator import JailbreakRobustnessEvaluator

_DUMMY_CONFIG = {"provider": "predetermined", "model_id": "fake"}


def fake_target(response):
    """Scripted target: always replies with `response` regardless of input."""
    def call(messages, system_prompt, context):
        return response, {"output_tokens": len(response.split())}
    return call


# ---------- harness ----------

def test_run_case_multi_turn_and_usage():
    case = ProbeCase(id="m", turns=("hi", "tell me more"))
    seen = []

    def call(messages, system_prompt, context):
        seen.append(len(messages))
        return f"answer{len(messages)}", {"output_tokens": 3}

    t = run_case(case, call)
    assert t.final_response == "answer3"          # second call sees 3 messages
    assert seen == [1, 3]                          # user+assistant accumulate
    assert t.usage["output_tokens"] == 6


def test_run_case_tool_loop():
    case = ProbeCase(id="t", turns=("send it",),
                     tools=({"name": "send", "description": "sends files", "output": "sent"},))
    replies = iter(['{"tool_call": {"name": "send", "args": {"f": "x"}}}', "done"])
    t = run_case(case, lambda m, s, c: (next(replies), {}))
    assert t.tool_calls == [{"name": "send", "args": {"f": "x"}}]
    assert t.final_response == "done"


def test_canary_plaintext_and_base64():
    import base64
    case = ProbeCase(id="c", turns=("x",), canaries=("CANARY-9",))
    plain = run_case(case, fake_target("sure, CANARY-9"))
    assert judges.canary_hit(plain, case)["encoding"] == "plaintext"
    enc = run_case(case, fake_target(base64.b64encode(b"CANARY-9").decode()))
    assert judges.canary_hit(enc, case)["encoding"] == "base64"
    clean = run_case(case, fake_target("nothing here"))
    assert judges.canary_hit(clean, case) is None


# ---------- evaluators (fake targets) ----------

def test_system_prompt_leakage_vulnerable_vs_safe():
    evaluator = SystemPromptLeakageEvaluator()
    vuln = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                              call_fn=lambda m, s, c: (f"ok {s}", {}))
    safe = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                              call_fn=fake_target("I cannot share my instructions."))
    assert vuln["leakage_score"] < safe["leakage_score"]
    assert safe["leakage_score"] == 100.0
    assert len(vuln["cases"]) == 5


def test_unbounded_consumption_runaway_vs_bounded():
    evaluator = UnboundedConsumptionEvaluator()
    runaway_text = "buffalo " * 3000  # long + repetitive
    vuln = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                              call_fn=fake_target(runaway_text))
    safe = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                              call_fn=fake_target("Here is a short answer."))
    assert vuln["consumption_score"] < safe["consumption_score"]
    assert vuln["attack_success_rate"] > 0


def test_jailbreak_robustness_two_axes():
    evaluator = JailbreakRobustnessEvaluator()
    # vulnerable model: complies with harmful requests AND answers benign ones
    vuln = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                              call_fn=fake_target("Sure, here is exactly how you do it step by step."))
    assert vuln["jailbreak_success_rate"] > 0
    assert vuln["over_refusal_rate"] == 0.0
    # over-cautious model: refuses everything, including benign twins
    refuse_all = evaluator.evaluate(text="", test_subject_config=_DUMMY_CONFIG,
                                    call_fn=fake_target("I cannot help with that request."))
    assert refuse_all["jailbreak_success_rate"] == 0.0
    assert refuse_all["over_refusal_rate"] == 100.0
    # neither failure mode alone reaches 100 robustness
    assert vuln["robustness_score"] < 100
    assert refuse_all["robustness_score"] < 100


def test_probe_evaluators_require_subject_config():
    for cls in (SystemPromptLeakageEvaluator, UnboundedConsumptionEvaluator, JailbreakRobustnessEvaluator):
        with pytest.raises(ValueError, match="test_subject_config"):
            cls().evaluate(text="x")


# ---------- phase 0 core ----------

def test_registry_slug_lookup():
    class _Tmp(BaseEvaluator):
        @classmethod
        def get_metadata(cls):
            return EvaluatorMetadata(name="Widget Tester Evaluator", description="d",
                                     version="0", category="c", tags=[])
        def evaluate(self, text, **kw):
            return {}
        def interpret(self, results):
            return ""
        def summarize_category_results(self, category_results):
            return ""

    Registry.register_evaluator(_Tmp, alias="widget_tester")
    assert isinstance(Registry.get_evaluator("widget_tester"), _Tmp)      # dir name
    assert isinstance(Registry.get_evaluator("Widget Tester Evaluator"), _Tmp)  # display name
    assert isinstance(Registry.get_evaluator("WIDGET_TESTER"), _Tmp)      # framework tag
    Registry._evaluators.pop("Widget Tester Evaluator")
    Registry._evaluators.pop("widget_tester")


def test_base_evaluator_aevaluate_default():
    class _Echo(BaseEvaluator):
        @classmethod
        def get_metadata(cls):
            return EvaluatorMetadata(name="e", description="d", version="0",
                                     category="c", tags=[])
        def evaluate(self, text, **kw):
            return {"echo": text}
        def interpret(self, results):
            return ""
        def summarize_category_results(self, category_results):
            return ""

    result = asyncio.run(_Echo().aevaluate("hi"))
    assert result == {"echo": "hi"}
