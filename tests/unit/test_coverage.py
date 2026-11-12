"""Offline tests for the framework coverage-matrix builder."""
import sys
from pathlib import Path

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.compliance.framework import coverage


def test_normalize_refs_splits_slash_values():
    out = coverage._normalize_refs({"eu_ai_act": "Art.9/10", "lang": "es"})
    assert out == {"eu_ai_act": ["Art.9", "Art.10"]}


def test_scan_evaluator_refs_real_plugins():
    refs = coverage.scan_evaluator_refs(Path(root_path) / "plugins" / "evaluators")
    assert "LLM07" in refs["system_prompt_leakage"]["owasp_llm"]
    assert "ASI05" in refs["code_execution"]["owasp_asi"]
    assert "AML.T0054" in refs["jailbreak_robustness"]["mitre_atlas"]
    # passive evaluators without refs come back empty, not missing
    assert "prompt_injection" in refs


def test_build_matrix_coverage_and_scores():
    matrix = coverage.build_matrix(
        {"ev_a": {"owasp_llm": ["LLM07"]}, "ev_b": {"owasp_llm": ["LLM01"]}},
        {"ev_a": 42.0})
    llm07 = matrix["matrix"]["owasp_llm"]["LLM07"]
    assert llm07["covered"] and llm07["evaluators"] == {"ev_a": 42.0}
    llm03 = matrix["matrix"]["owasp_llm"]["LLM03"]
    assert not llm03["covered"] and llm03["evaluators"] == {}
    assert 0 < matrix["summary"]["coverage_pct"] < 100


def test_build_matrix_none_score_means_ran_failed():
    matrix = coverage.build_matrix(
        {"ev_a": {"owasp_llm": ["LLM07"]}}, {"ev_a": None})
    assert matrix["matrix"]["owasp_llm"]["LLM07"]["evaluators"]["ev_a"] is None
