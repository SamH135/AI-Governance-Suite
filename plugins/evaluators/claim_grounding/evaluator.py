"""Claim Grounding evaluator — tier-2 faithfulness check (NLI scoring model).

Deterministic checks can verify a quote exists; an LLM judge can weigh
nuance. This evaluator sits between them: a local NLI model scores whether
each claim in the target's response is entailed by the case's evidence
documents, at a fraction of judge cost. Score = groundedness (100 = every
checkable claim supported by the record).
"""
from pathlib import Path
from typing import Any, Dict, List

from services.compliance.framework.core.base import (
    BaseEvaluator,
    EvaluatorCapability,
    EvaluatorMetadata,
    LLMRequirements,
    ModelRequirement,
)
from services.compliance.framework.probes import (
    Check,
    judges,
    load_cases,
    make_grounding_check,
    make_target_caller,
    run_suite,
)

_CASES_PATH = Path(__file__).parent / "cases" / "grounding.json"

REFS = {"nist_600_1": "MS-2.7-007", "note": "grounded factuality / faithfulness"}


class ClaimGroundingEvaluator(BaseEvaluator):
    """100 = all checkable claims grounded in the evidence; 0 = all fabricated."""

    @classmethod
    def get_metadata(cls) -> EvaluatorMetadata:
        return EvaluatorMetadata(
            name="Claim Grounding",
            description="Scores whether each claim in the response is entailed by "
                        "the evidence documents, using a local NLI model — the "
                        "middle tier between deterministic checks and LLM judges.",
            version="1.0.0",
            category="Quality",
            tags=["groundedness", "faithfulness", "nli", "hallucination", "probe"],
            primary_output_key="groundedness_score",
            requires_test_subject_config=True,
            fallback_mode="error",
            estimated_runtime="medium",
            capabilities=[EvaluatorCapability.RULE_BASED, EvaluatorCapability.RAG_ENABLED],
            llm_requirements=LLMRequirements(requirement_level=ModelRequirement.NONE),
            display_fields=[
                {"key": "groundedness_score", "label": "Groundedness", "type": "score"},
                {"key": "attack_success_rate", "label": "Ungrounded Claim Rate", "type": "percentage"},
            ],
            risk_thresholds={"high": 60, "medium": 30, "low": 0},
        )

    def evaluate(self, text: str, test_subject_config=None, evaluator_llm_config=None,
                 rag_config=None, vector_store=None, **kwargs) -> Dict[str, Any]:
        if test_subject_config is None:
            raise ValueError(
                "Claim Grounding is a probe evaluator: it needs "
                "test_subject_config to drive the target model."
            )
        call_fn = kwargs.get("call_fn") or make_target_caller(test_subject_config)
        threshold = float(kwargs.get("support_threshold", 0.5))
        scorer = kwargs.get("scorer")  # injected in tests — no model download
        cases = load_cases(_CASES_PATH)
        checks = [
            Check("claim_grounding", make_grounding_check(scorer, threshold),
                  weight=1.0, axis="any", refs=REFS),
            Check("over_refusal", judges.refused_but_should_comply,
                  weight=1.0, axis="benign", refs=REFS),
        ]
        results = run_suite(
            cases, checks, call_fn,
            provenance={"evaluator": "claim_grounding", "corpus": _CASES_PATH.name,
                        "case_count": len(cases),
                        "judge": getattr(scorer, "model_id", "nli-scorer"),
                        "refs": REFS},
        )
        results["groundedness_score"] = round(100.0 - results["attack_success_rate"], 2)
        return results

    def interpret(self, results: Dict[str, Any]) -> str:
        score = results.get("groundedness_score", 0)
        bad = [c["case_id"] for c in results.get("cases", [])
               if c["checks"].get("claim_grounding", {}).get("score", 0) > 0]
        if not bad:
            return f"All checkable claims were grounded in the evidence (score {score})."
        return f"Ungrounded claims in {len(bad)} case(s): {', '.join(bad)}. Score {score}."

    def summarize_category_results(self, category_results: List[Dict[str, Any]]) -> str:
        scores = [r.get("groundedness_score", 0) for r in category_results]
        avg = sum(scores) / len(scores) if scores else 0
        return f"Average claim groundedness: {avg:.1f}/100 across {len(scores)} runs."
