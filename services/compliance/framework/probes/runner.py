"""Suite runner: execute cases, score checks, compose the evaluator result dict."""
from typing import Any, Dict, List

from .harness import CallFn
from .models import Check, ProbeCase


def run_suite(cases: List[ProbeCase], checks: List[Check], call_fn: CallFn,
              provenance: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run every case through the harness and every check over the transcript.

    Score = 100 - weighted mean of check scores (checks report "attack success",
    so the evaluator score means "the subject held up"). Per-check evidence and
    framework refs are preserved for audit reports.
    """
    from .harness import run_case

    case_results = []
    totals: Dict[str, float] = {}
    for case in cases:
        transcript = run_case(case, call_fn)
        check_results = {}
        for check in checks:
            score, evidence = check.fn(transcript, case)
            check_results[check.name] = {
                "score": round(score, 2), "weight": check.weight,
                "evidence": evidence, "refs": check.refs,
            }
            if check.weight > 0:
                totals[check.name] = totals.get(check.name, 0.0) + score * check.weight
        case_results.append({
            "case_id": case.id, "expect": case.expect, "refs": case.refs,
            "checks": check_results,
            "transcript": {
                "turns": [{"role": t.role, "content": t.content[:2000],
                           **({"tool_call": t.tool_call} if t.tool_call else {})}
                          for t in transcript.turns],
                "tool_calls": transcript.tool_calls,
                "usage": transcript.usage,
                "latency_ms": round(transcript.latency_ms, 1),
            },
        })

    total_weight = sum(c.weight for c in checks if c.weight > 0) * max(len(cases), 1)
    attack_success = sum(totals.values()) / total_weight if total_weight else 0.0
    return {
        "attack_success_rate": round(attack_success, 2),
        "cases": case_results,
        "provenance": provenance or {},
    }
