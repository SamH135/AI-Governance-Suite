"""Live verification of probe fixes — real DeepSeek target + Gemini judge.

Runs probe evaluators through the real framework (harness -> unified API ->
run_suite -> judges) without the web stack. Asserts pipeline correctness,
not score values. Keys come from .env; nothing secret is printed.

Usage: py scripts/verify_live_probes.py [evaluator ...]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for line in open(os.path.join(os.path.dirname(__file__), "..", ".env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

from shared.unified_api.base import ModelConfig, ModelType  # noqa: E402

TARGET = ModelConfig(
    provider="openai", model_id="deepseek-chat",
    api_key=os.environ["DEEPSEEK_API_KEY"],
    api_url="https://api.deepseek.com",
    temperature=0.0, max_tokens=1200, timeout=60,
    usage_type=ModelType.TEST_SUBJECT,
)
JUDGE = ModelConfig(
    provider="google", model_id="gemini-3.1-flash-lite",
    api_key=os.environ["GEMINI_API_KEY"],
    temperature=0.0, timeout=60,
    usage_type=ModelType.EVALUATOR,
)


def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {name} {detail}")
    if not cond:
        FAILURES.append(name)


def evaluator(name):
    import importlib
    import inspect
    mod = importlib.import_module(f"plugins.evaluators.{name}.evaluator")
    cls = next(v for v in vars(mod).values()
               if isinstance(v, type) and v.__name__.endswith("Evaluator")
               and not inspect.isabstract(v))
    return cls()


FAILURES = []
results = {}

for name in sys.argv[1:] or ["tool_poisoning", "jailbreak_robustness"]:
    print(f"\n=== {name} (deepseek target, gemini judge) ===")
    t0 = time.time()
    try:
        out = evaluator(name).evaluate(
            text="", test_subject_config=TARGET, evaluator_llm_config=JUDGE)
    except Exception as e:
        print(f"  evaluator raised: {e}")
        FAILURES.append(f"{name}:raised")
        continue
    results[name] = out
    prov = out.get("provenance", {})

    check("provenance target", prov.get("target") == "openai/deepseek-chat", prov.get("target"))
    check("provenance git_sha", bool(prov.get("git_sha")), prov.get("git_sha"))
    check("provenance corpus_sha256", bool(prov.get("corpus_sha256")), prov.get("corpus_sha256"))
    check("provenance judge", bool(prov.get("judge")), prov.get("judge"))
    check("has attack_success_rate", "attack_success_rate" in out, out.get("attack_success_rate"))

    for c in out.get("cases", []):
        turns = c["transcript"]["turns"]
        asst = [t for t in turns if t["role"] == "assistant"]
        check(f"{c['case_id']}: got response", bool(asst and asst[-1]["content"]),
              f"{len(turns)} turns, {len(c['transcript']['tool_calls'])} tool calls")
        for chk, r in c["checks"].items():
            if r.get("skipped"):
                print(f"      {c['case_id']}.{chk}: skipped ({r['evidence'].get('reason', '')})")

    elapsed = time.time() - t0
    print(f"  {elapsed:.0f}s | ASR={out.get('attack_success_rate')} check_rates={out.get('check_rates')}")

print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"FAILURES: {FAILURES}"))
sys.exit(1 if FAILURES else 0)
