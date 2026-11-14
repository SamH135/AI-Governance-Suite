"""Probe-kit data model — verifiers-inspired primitives for compliance evals.

A ProbeCase is an immutable test scenario (≈ vf.TaskData). A Check is a
weighted scoring function (≈ @vf.reward; weight=0 ≈ @vf.metric). A Transcript
records everything the target did (≈ vf.Trace) and is the audit evidence.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ProbeCase:
    """One scripted test scenario executed against the test subject."""
    id: str
    turns: Tuple[str, ...]                     # scripted user turns
    system_prompt: Optional[str] = None        # may embed a canary
    docs: Tuple[str, ...] = ()                 # RAG fixtures injected as context
    tools: Tuple[Dict[str, Any], ...] = ()     # simulated tool manifests {name, description, parameters, output}
    native_tools: bool = False                 # send tools via provider function-calling instead of JSON prompt
    mcp_server: Optional[Dict[str, Any]] = None  # {command, args, env} — live MCP server for real tool execution
    tool_outputs: Tuple[str, ...] = ()         # tool results injected as a user/tool turn before turn 1
    canaries: Tuple[str, ...] = ()             # secrets that must never appear in output
    expect: str = "refuse"                     # refuse | comply | ignore_injection
    refs: Dict[str, str] = field(default_factory=dict)  # {"owasp_llm": "LLM07", "atlas": "AML.T0056", ...}
    max_tool_steps: int = 8

    _EXPECTS = frozenset({"refuse", "comply", "ignore_injection"})

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ProbeCase":
        expect = d.get("expect", "refuse")
        if expect not in ProbeCase._EXPECTS:
            raise ValueError(f"case {d.get('id')!r}: unknown expect {expect!r}")
        return ProbeCase(
            id=d["id"],
            turns=tuple(d["turns"]),
            system_prompt=d.get("system_prompt"),
            docs=tuple(d.get("docs", ())),
            tools=tuple(d.get("tools", ())),
            native_tools=bool(d.get("native_tools", False)),
            mcp_server=d.get("mcp_server"),
            tool_outputs=tuple(d.get("tool_outputs", ())),
            canaries=tuple(d.get("canaries", ())),
            expect=expect,
            refs=d.get("refs", {}),
            max_tool_steps=d.get("max_tool_steps", 8),
        )


def load_cases(path: str | Path) -> List[ProbeCase]:
    """Load cases from a .json (list) or .jsonl file."""
    p = Path(path)
    if p.suffix == ".jsonl":
        return [ProbeCase.from_dict(json.loads(l)) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [ProbeCase.from_dict(d) for d in json.loads(p.read_text(encoding="utf-8"))]


@dataclass
class Turn:
    role: str            # user | assistant | tool | document
    content: str
    tool_call: Optional[Dict[str, Any]] = None  # parsed {name, args} when the model called a tool


@dataclass
class Transcript:
    """Full record of one probe run — the audit evidence."""
    case_id: str
    turns: List[Turn] = field(default_factory=list)
    final_response: str = ""
    provider_blocked: bool = False   # platform safety filter refused before the model could answer
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def all_output(self) -> str:
        return "\n".join(t.content for t in self.turns if t.role == "assistant")


# A check maps (transcript, case) -> (score 0-100 or None when the check does
# not apply to the case, evidence dict). None = skipped, never scored.
CheckFn = Callable[[Transcript, ProbeCase], Tuple[Optional[float], Dict[str, Any]]]


@dataclass(frozen=True)
class Check:
    """One named scoring signal. weight=0 records a metric without scoring (≈ vf.metric).

    axis controls which cases the check scores:
    - "attack" (default): runs only on expect!="comply" cases — benign twins are skipped
    - "benign": runs only on expect=="comply" cases (e.g. over-refusal)
    - "any": runs on every case (e.g. extraction corpora where comply IS the attack)
    """
    name: str
    fn: CheckFn
    weight: float = 1.0
    axis: str = "attack"
    refs: Dict[str, str] = field(default_factory=dict)
