"""Benchmark adapters: convert external red-team datasets into ProbeCase lists.

Supported shapes (auto-detected by field names):
- HarmBench/JailbreakBench: {"goal"|"behavior"|"prompt": str} — harmful asks
- XSTest: {"prompt"|"question": str, "type"|"label": "safe"|...} — contrast set
- AgentDojo-style injection: {"user_task"|"instruction": str, "injection"|"injection_task": str}
- Generic: {"turns": [...]} or {"prompt": str} with optional expect/refs

Usage: drop a .json/.jsonl corpus under a plugin's cases/ (or anywhere) and
`load_benchmark_cases(path)` yields ProbeCases ready for run_suite.
External corpora stay out of git (licensing); only loaders ship.
"""
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import ProbeCase


def _iter_records(path: Path) -> Iterable[Dict[str, Any]]:
    if path.suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("data", data.get("cases", [data]))
        yield from data


def _to_case(rec: Dict[str, Any], idx: int) -> ProbeCase:
    rid = str(rec.get("id") or rec.get("case_id") or f"bench_{idx}")
    refs = rec.get("refs", {})
    canaries = tuple(rec.get("canaries") or ())

    # AgentDojo-style: task + injected instruction embedded in docs
    if "injection" in rec or "injection_task" in rec:
        injection = rec.get("injection") or rec.get("injection_task")
        task = rec.get("user_task") or rec.get("instruction") or "Complete the task."
        return ProbeCase(
            id=rid, turns=(task,),
            docs=(f"[untrusted content] {injection}",),
            expect="ignore_injection", refs=refs, canaries=canaries)

    label = str(rec.get("type") or rec.get("label") or "").lower()
    benign = label in {"safe", "benign", "contrast"}
    prompt = (rec.get("goal") or rec.get("behavior") or rec.get("prompt")
              or rec.get("question") or rec.get("instruction") or "")
    turns = tuple(rec.get("turns") or [prompt])
    return ProbeCase(
        id=rid, turns=turns,
        system_prompt=rec.get("system_prompt"),
        expect="comply" if benign else "refuse",
        refs=refs, canaries=canaries)


def load_benchmark_cases(path: str | Path) -> List[ProbeCase]:
    """Load an external benchmark file into ProbeCases.

    Raises on empty/unrecognized input — a silently-empty corpus must not
    produce a vacuous 100% score.
    """
    path = Path(path)
    cases = [_to_case(rec, i) for i, rec in enumerate(_iter_records(path))]
    if not cases:
        raise ValueError(f"No cases parsed from {path} — check the file format")
    return cases
