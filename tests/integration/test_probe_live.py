"""Live end-to-end eval verification — gated behind RUN_LIVE_EVALS=1.

Runs each probe evaluator through the real authenticated workflow:
login -> POST /api/systems/{system_id}/test-unified -> assert result shape.

This verifies the full pipeline (auth, system ownership, model config,
plugin resolution, provider call, scoring) against a real model. It does
NOT assert on score values — live model outputs are nondeterministic;
results are evidence, recorded in the response and by the caller.

Env:
  RUN_LIVE_EVALS=1          required or the whole module skips
  LIVE_EVAL_BASE            compliance service URL (default http://localhost:8001)
  LIVE_EVAL_LOGIN           gateway login URL (default http://localhost:8000)
  LIVE_EVAL_USER            username (default testuser)
  LIVE_EVAL_PASSWORD        password (required)
  LIVE_EVAL_SYSTEM_ID       system id wired to the target model (required)
  LIVE_EVAL_JUDGE_ID        evaluator/judge model config id (optional)
  LIVE_EVAL_SET             comma-separated evaluator list (default: all probe evals)
  LIVE_EVAL_OUT             directory to dump full JSON responses (optional; created if missing)
  LIVE_EVAL_PREFIX          filename prefix for dumps, e.g. "groq" (default "live")

Run:
  RUN_LIVE_EVALS=1 LIVE_EVAL_PASSWORD=... LIVE_EVAL_SYSTEM_ID=5 \
      pytest tests/integration/test_probe_live.py -v
"""
import json
import os
import urllib.error
import urllib.request

import pytest

PROBE_EVALUATORS = [
    "system_prompt_leakage",
    "unbounded_consumption",
    "jailbreak_robustness",
    "indirect_prompt_injection",
    "vector_embedding_security",
    "tool_misuse",
    "tool_poisoning",
    "memory_poisoning",
    "multi_turn_escalation",
    "counterfactual_fairness",
    "multilingual_robustness",
    "model_extraction",
    "code_execution",
    "adaptive_jailbreak",
]

ENABLED = os.environ.get("RUN_LIVE_EVALS") == "1"
BASE = os.environ.get("LIVE_EVAL_BASE", "http://localhost:8001").rstrip("/")
LOGIN = os.environ.get("LIVE_EVAL_LOGIN", "http://localhost:8000").rstrip("/")
USER = os.environ.get("LIVE_EVAL_USER", "testuser")
PASSWORD = os.environ.get("LIVE_EVAL_PASSWORD", "")
SYSTEM_ID = os.environ.get("LIVE_EVAL_SYSTEM_ID", "")
JUDGE_ID = os.environ.get("LIVE_EVAL_JUDGE_ID")
EVALUATORS = [e.strip() for e in os.environ.get("LIVE_EVAL_SET", "").split(",") if e.strip()] \
    or PROBE_EVALUATORS
OUT_DIR = os.environ.get("LIVE_EVAL_OUT")
OUT_PREFIX = os.environ.get("LIVE_EVAL_PREFIX", "live")

pytestmark = pytest.mark.skipif(
    not ENABLED or not PASSWORD or not SYSTEM_ID,
    reason="live evals need RUN_LIVE_EVALS=1, LIVE_EVAL_PASSWORD, LIVE_EVAL_SYSTEM_ID",
)


def _post(url, body, token=None, timeout=300):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture(scope="module")
def token():
    status, body = _post(f"{LOGIN}/api/auth/login",
                         {"username": USER, "password": PASSWORD}, timeout=30)
    assert status == 200, f"login failed: {status}"
    tok = (body.get("access_token") or body.get("token")
           or body.get("data", {}).get("access_token")
           or body.get("data", {}).get("token"))
    assert tok, f"no token in login response: {list(body)}"
    return tok


def test_login_and_system_visible(token):
    status, body = _post(f"{BASE}/api/systems/{SYSTEM_ID}/test-unified",
                         {"evaluators": [], "test_prompts": "pipeline check"},
                         token=token, timeout=60)
    # empty evaluator list may 422 on validation — anything but 401/403 means auth+route work
    assert status not in (401, 403), f"auth failed: {status}"


@pytest.mark.parametrize("evaluator", EVALUATORS)
def test_probe_evaluator_live(token, evaluator):
    body = {"evaluators": [evaluator], "test_prompts": "live verification"}
    if JUDGE_ID:
        body["evaluator_model_id"] = int(JUDGE_ID)
    status, data = _post(f"{BASE}/api/systems/{SYSTEM_ID}/test-unified",
                         body, token=token, timeout=300)
    assert status == 200, f"{evaluator}: HTTP {status}"
    payload = data.get("data", data)
    assert payload.get("status") == "completed", f"{evaluator}: {payload.get('status')}"
    results = payload.get("evaluator_results", {})
    assert evaluator in results, f"{evaluator}: missing from results {list(results)}"
    result = results[evaluator].get("result", results[evaluator])
    assert "error" not in result, f"{evaluator}: {result['error'][:200]}"
    assert result.get("cases") or result.get("compliance_score") is not None \
        or any("score" in k for k in result), \
        f"{evaluator}: no scored output in {list(result)[:8]}"
    if OUT_DIR:
        os.makedirs(OUT_DIR, exist_ok=True)
        # stamp the code SHA — the container has no .git so run_suite can't bind it there
        try:
            import subprocess
            sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            sha = ""
        if sha:
            for wrap in ((data.get("data", data).get("evaluator_results") or {}).values()):
                prov = (wrap.get("result") or {}).get("provenance")
                if isinstance(prov, dict):
                    prov.setdefault("git_sha", sha)
        # utf-8 + ensure_ascii=False: past exports saved through a Windows shell produced mojibake
        with open(os.path.join(OUT_DIR, f"{OUT_PREFIX}_{evaluator}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
