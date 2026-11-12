"""Coverage-matrix builder: map evaluators + results onto framework controls.

Scans each plugin for framework references (evaluator `REFS` const + per-case
`refs` in cases/*.json), normalizes them onto a static control catalog, and
overlays the latest stored test scores per system. The output is the
chart/report payload for coverage reporting — every cell knows which evaluators
cover it and what they last scored.
"""
import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Static control catalog. Uncovered controls still appear (covered=False) —
# showing the gap is the matrix's job.
CONTROL_CATALOG: Dict[str, List[str]] = {
    "owasp_llm": [f"LLM{i:02d}" for i in range(1, 11)],
    "owasp_asi": [f"ASI{i:02d}" for i in range(1, 11)],
    "mitre_atlas": ["AML.T0051", "AML.T0051.001", "AML.T0053", "AML.T0054",
                    "AML.T0056", "AML.T0057", "AML.T0068", "AML.T0086",
                    "AML.T0110", "AML.T0024"],
    "nist_600_1": ["MS-2.7-007", "MS-2.10-001"],
    "nist_ai_rmf": ["FAIRNESS"],
    "eu_ai_act": ["Art.9", "Art.10", "Art.15", "Art.50", "Art.55"],
    "iso_42001": ["A.9.4"],  # AI system operation/monitoring
}

# refs-dict keys -> catalog framework. Other keys (lang, axis, expected, corpus,
# threat, benchmark) are metadata, not controls.
_REF_KEY_MAP = {
    "owasp_llm": "owasp_llm",
    "owasp_asi": "owasp_asi",
    "atlas": "mitre_atlas",
    "nist_600_1": "nist_600_1",
    "nist_ai_rmf": "nist_ai_rmf",
    "eu_ai_act": "eu_ai_act",
    "iso_42001": "iso_42001",
}

_REFS_LITERAL = re.compile(r"^REFS\s*=\s*(\{.*?\})", re.M | re.S)
_PRIMARY_KEY_LITERAL = re.compile(r'primary_output_key\s*=\s*["\']([^"\']+)["\']')


def scan_primary_output_keys(plugins_dir: Path) -> Dict[str, str]:
    """{evaluator_name: primary_output_key} parsed from each evaluator.py."""
    out: Dict[str, str] = {}
    for eval_file in Path(plugins_dir).glob("*/evaluator.py"):
        m = _PRIMARY_KEY_LITERAL.search(eval_file.read_text(encoding="utf-8"))
        if m:
            out[eval_file.parent.name] = m.group(1)
    return out


def _normalize_refs(refs: Dict[str, str]) -> Dict[str, List[str]]:
    """{framework: [control, ...]} from one refs dict."""
    out: Dict[str, List[str]] = {}
    for key, value in (refs or {}).items():
        framework = _REF_KEY_MAP.get(key)
        if not framework or not isinstance(value, str):
            continue
        # values like "Art.9/10" expand to both Art.9 and Art.10
        parts = [p.strip() for p in re.split(r"[/,]", value) if p.strip()]
        prefix = re.match(r"^\D*", parts[0]).group(0) if parts else ""
        for part in parts:
            if prefix and part[0].isdigit():
                part = prefix + part
            out.setdefault(framework, [])
            if part not in out[framework]:
                out[framework].append(part)
    return out


def scan_evaluator_refs(plugins_dir: Path) -> Dict[str, Dict[str, List[str]]]:
    """{evaluator_name: {framework: [controls]}} across all plugins.

    Sources: `REFS = {...}` literal in evaluator.py (ast-parsed) plus every
    `refs` dict in cases/*.json / *.jsonl.
    """
    plugins_dir = Path(plugins_dir)
    matrix: Dict[str, Dict[str, List[str]]] = {}
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not (plugin_dir / "plugin.py").exists():
            continue
        merged: Dict[str, List[str]] = {}

        eval_file = plugin_dir / "evaluator.py"
        if eval_file.exists():
            text = eval_file.read_text(encoding="utf-8")
            for m in _REFS_LITERAL.finditer(text):
                try:
                    for fw, ctrls in _normalize_refs(ast.literal_eval(m.group(1))).items():
                        for c in ctrls:
                            if c not in merged.setdefault(fw, []):
                                merged[fw].append(c)
                except (SyntaxError, ValueError):
                    continue  # non-literal REFS (e.g. built dynamically)

        cases_dir = plugin_dir / "cases"
        if cases_dir.is_dir():
            for case_file in sorted(cases_dir.iterdir()):
                docs = []
                if case_file.suffix == ".json":
                    docs = json.loads(case_file.read_text(encoding="utf-8"))
                elif case_file.suffix == ".jsonl":
                    docs = [json.loads(l) for l in
                            case_file.read_text(encoding="utf-8").splitlines() if l.strip()]
                for doc in docs if isinstance(docs, list) else []:
                    for fw, ctrls in _normalize_refs(doc.get("refs", {})).items():
                        for c in ctrls:
                            if c not in merged.setdefault(fw, []):
                                merged[fw].append(c)
        matrix[plugin_dir.name] = merged
    return matrix


def build_matrix(evaluator_refs: Dict[str, Dict[str, List[str]]],
                 latest_scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Control catalog overlaid with evaluator coverage + latest scores.

    latest_scores: {evaluator_name: score} — None values mean "ran, no score".
    Returns {framework: {control: {covered, evaluators: {name: score|None}}}}
    plus summary counts.
    """
    latest_scores = latest_scores or {}
    matrix: Dict[str, Any] = {}
    for framework, controls in CONTROL_CATALOG.items():
        fw: Dict[str, Any] = {}
        for control in controls:
            covering = {
                ev: latest_scores.get(ev)
                for ev, refs in evaluator_refs.items()
                if control in refs.get(framework, [])
            }
            fw[control] = {
                "covered": bool(covering),
                "evaluators": covering,
            }
        matrix[framework] = fw

    covered = sum(c["covered"] for fw in matrix.values() for c in fw.values())
    total = sum(len(fw) for fw in matrix.values())
    return {
        "matrix": matrix,
        "summary": {"controls": total, "covered": covered,
                    "coverage_pct": round(100.0 * covered / total, 1) if total else 0.0},
    }
