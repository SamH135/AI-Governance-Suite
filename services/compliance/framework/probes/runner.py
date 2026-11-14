"""Suite runner: execute cases, score checks, compose the evaluator result dict."""
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .harness import CallFn
from .models import Check, ProbeCase

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _applies(check: Check, case: ProbeCase) -> bool:
    if check.axis == "any":
        return True
    benign = case.expect == "comply"
    return (check.axis == "benign") == benign


def run_suite(cases: List[ProbeCase], checks: List[Check], call_fn: CallFn,
              provenance: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run every case through the harness and every check over the transcript.

    Score = 100 - weighted mean of check scores (checks report "attack success",
    so the evaluator score means "the subject held up"). Per-check evidence and
    framework refs are preserved for audit reports.

    A check only contributes to attack_success_rate for the (check, case) pairs
    it actually scored — axis-gated skips and checks returning None are excluded
    from both numerator and denominator, so benign twins can't dilute attacks
    and unconfigured judges can't be read as failures. `check_rates` exposes
    each signal separately so e.g. over-refusal is visible next to attack success.
    """
    from .harness import run_case

    case_results = []
    totals: Dict[str, float] = {}
    applied_weight: Dict[str, float] = {}
    attack_totals: List[float] = []
    attack_weight = 0.0
    for case in cases:
        transcript = run_case(case, call_fn)
        check_results = {}
        for check in checks:
            if not _applies(check, case):
                check_results[check.name] = {
                    "skipped": True, "weight": check.weight,
                    "evidence": {"reason": f"axis={check.axis}, expect={case.expect}"},
                    "refs": check.refs,
                }
                continue
            score, evidence = check.fn(transcript, case)
            if score is None:
                check_results[check.name] = {
                    "skipped": True, "weight": check.weight,
                    "evidence": evidence, "refs": check.refs,
                }
                continue
            check_results[check.name] = {
                "score": round(score, 2), "weight": check.weight,
                "evidence": evidence, "refs": check.refs,
            }
            if check.weight > 0:
                totals[check.name] = totals.get(check.name, 0.0) + score * check.weight
                applied_weight[check.name] = applied_weight.get(check.name, 0.0) + check.weight
                if check.axis != "benign":
                    attack_totals.append(score * check.weight)
                    attack_weight += check.weight
        case_results.append({
            "case_id": case.id, "expect": case.expect, "refs": case.refs,
            "checks": check_results,
            "transcript": {
                # bounded so evidence files stay readable, but wide enough that a
                # canary leaking late in the output can't be truncated out of view
                "turns": [{"role": t.role, "content": t.content[:20000],
                           **({"tool_call": t.tool_call} if t.tool_call else {})}
                          for t in transcript.turns],
                "tool_calls": transcript.tool_calls,
                "usage": transcript.usage,
                "latency_ms": round(transcript.latency_ms, 1),
            },
        })

    prov = dict(provenance or {})
    prov.setdefault("case_ids", [c.id for c in cases])
    target = getattr(call_fn, "target_model", None)
    if target:
        prov.setdefault("target", target)
    corpus = prov.get("corpus")
    if corpus and "corpus_sha256" not in prov:
        for p in (_REPO_ROOT / "plugins" / "evaluators").glob(f"*/cases/{corpus}"):
            prov["corpus_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            break
    if "git_sha" not in prov:
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=_REPO_ROOT,
                capture_output=True, text=True, timeout=5).stdout.strip()
            if sha:
                prov["git_sha"] = sha
        except Exception:
            pass  # not a git checkout (e.g. slim container) — omit rather than fail

    # attack_success_rate is attack-axis only; benign signals stay in check_rates
    attack_success = sum(attack_totals) / attack_weight if attack_weight else 0.0
    return {
        "attack_success_rate": round(attack_success, 2),
        "check_rates": {n: round(totals[n] / applied_weight[n], 2) for n in totals},
        "cases": case_results,
        "provenance": prov,
    }
