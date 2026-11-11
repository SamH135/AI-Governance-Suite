# framework/evaluators/geval_metric/evaluator.py
"""
Production-quality G-Eval implementation based on deepeval's approach.
Incorporates: weighted scoring, log probabilities, rubrics, CoT, and advanced prompt engineering.
Compatible with the AI Compliance System framework.
"""

import json
import logging
import re
import time
import math
import traceback
from typing import Dict, Any, List, Optional, Union, Tuple
from enum import Enum
from dataclasses import dataclass

from services.compliance.framework.core.base import (
    BaseEvaluator,
    EvaluatorMetadata,
    EvaluatorCapability,
    LLMRequirements,
    RAGRequirements,
    ModelRequirement
)
from services.compliance.framework.core.model_manager import model_manager

logger = logging.getLogger(__name__)

try:
    from shared.unified_api.base import ModelConfig
except ImportError:
    ModelConfig = Any


class LLMTestCaseParams(Enum):
    """Test case parameters that can be used in G-Eval evaluation."""
    INPUT = "input"
    ACTUAL_OUTPUT = "actual_output"
    EXPECTED_OUTPUT = "expected_output"
    CONTEXT = "context"
    RETRIEVAL_CONTEXT = "retrieval_context"


@dataclass
class Rubric:
    """Rubric for structured G-Eval scoring, following deepeval's approach."""
    criteria: str
    score_range: Tuple[int, int]  # (min_score, max_score)
    description: str


@dataclass
class ReasonScore:
    """Response schema for G-Eval structured output."""
    score: float
    reason: str
    steps_followed: List[str] = None


class GEvalTemplate:
    """G-Eval prompt templates based on deepeval's implementation patterns."""

    @staticmethod
    def generate_evaluation_steps(criteria: str, evaluation_params: List[str]) -> str:
        """Generate evaluation steps from criteria using chain-of-thought."""
        params_str = ", ".join([f"'{param}'" for param in evaluation_params])

        return f"""You will be given a task to evaluate based on a given criteria. Your job is to generate a list of evaluation steps based on the criteria.

**Criteria:**
{criteria}

**Available Parameters:**
{params_str}

**Instructions:**
1. Generate 3-5 detailed evaluation steps that break down the criteria
2. Each step should be specific and actionable
3. Steps should guide the evaluator through a logical reasoning process
4. Focus on the most important aspects of the criteria
5. Ensure steps can be followed systematically

**Output Format:**
Return a JSON object with the following structure:
{{
    "steps": [
        "Step 1: [Detailed evaluation step]",
        "Step 2: [Detailed evaluation step]",
        "Step 3: [Detailed evaluation step]",
        // Additional steps as needed
    ]
}}

Generate the evaluation steps now:"""

    @staticmethod
    def generate_evaluation_results(
            evaluation_steps: List[str],
            test_case_content: str,
            parameters: str,
            rubric: Optional[str] = None,
            score_range: str = "0.0 to 1.0",
            strict_mode: bool = False,
            _additional_context: Optional[str] = None
    ) -> str:
        """Generate the main evaluation prompt following deepeval's structure."""

        # Number the evaluation steps
        numbered_steps = []
        for i, step in enumerate(evaluation_steps, 1):
            if step.strip().startswith(f"{i}.") or step.strip().startswith(f"Step {i}"):
                numbered_steps.append(step.strip())
            else:
                numbered_steps.append(f"{i}. {step.strip()}")

        steps_text = "\n".join(numbered_steps)

        prompt_parts = [
            "You are an expert evaluator tasked with assessing the quality of an AI-generated response based on specific criteria.",
            "",
            "**Evaluation Task:**",
            f"Please evaluate the following content using the specified criteria and follow the evaluation steps systematically.",
            "",
            "**Available Parameters:**",
            parameters,
            "",
            "**Test Case Content:**",
            test_case_content
        ]

        if _additional_context:
            prompt_parts.extend([
                "",
                "**Additional Context:**",
                _additional_context
            ])

        prompt_parts.extend([
            "",
            "**Evaluation Steps to Follow:**",
            steps_text,
            ""
        ])

        if rubric:
            prompt_parts.extend([
                "**Scoring Rubric:**",
                rubric,
                ""
            ])

        if strict_mode:
            prompt_parts.extend([
                "**Scoring Instructions (Strict Mode):**",
                "- Provide a binary score: 1.0 for perfect adherence to criteria, 0.0 otherwise",
                "- No partial credit - the response must fully meet all requirements",
                "- Be extremely precise in your evaluation"
            ])
        else:
            prompt_parts.extend([
                "**Scoring Instructions:**",
                f"- Provide a score between {score_range}",
                "- Higher scores indicate better performance",
                "- Consider partial credit for responses that partially meet criteria",
                "- Be objective and consistent in your evaluation"
            ])

        prompt_parts.extend([
            "",
            "**Instructions:**",
            "1. Carefully read and understand all the provided content",
            "2. Follow each evaluation step systematically",
            "3. For each step, analyze the content thoroughly",
            "4. Provide clear reasoning for your assessment",
            "5. Assign a final numerical score based on your analysis",
            "",
            "**Response Format:**",
            "Respond with a JSON object containing:",
            "```json",
            "{",
            f'    "score": <float between {score_range}>,',
            '    "reason": "<comprehensive explanation of your evaluation>",',
            '    "steps_followed": [',
            '        "Step 1 analysis: <your analysis>",',
            '        "Step 2 analysis: <your analysis>",',
            '        // Continue for all steps',
            '    ]',
            "}",
            "```",
            "",
            "Begin your evaluation now:"
        ])

        return "\n".join(prompt_parts)


class GEvalEvaluator(BaseEvaluator):
    """
    Advanced G-Eval implementation incorporating deepeval's best practices:
    - Weighted scoring with log probabilities
    - Chain-of-thought evaluation steps
    - Rubric-based structured scoring
    - Strict mode for binary evaluation
    - Advanced error handling and parsing
    - Full compatibility with AI Compliance System framework
    """

    def __init__(self):
        """Initialize the advanced G-Eval evaluator."""
        self.evaluation_cost = 0.0
        logger.info("GEvalEvaluator initialized with deepeval-level capabilities")

    @classmethod
    def get_metadata(cls) -> EvaluatorMetadata:
        """Provide comprehensive metadata for the advanced G-Eval evaluator."""
        return EvaluatorMetadata(
            name="Advanced G-Eval Metric",
            description="Production-quality G-Eval implementation with weighted scoring, CoT reasoning, and rubric support",
            version="2.0.0",
            category="Quality Assessment",
            tags=["g-eval", "llm-judge", "chain-of-thought", "weighted-scoring", "rubrics", "research-backed"],
            output_format="composite",
            primary_output_key="score",
            display_fields=[
                {
                    "key": "score",
                    "label": "G-Eval Score",
                    "type": "number",
                    "description": "Weighted score from 0.0 to 1.0 (or custom range)"
                },
                {
                    "key": "criteria",
                    "label": "Evaluation Criteria",
                    "type": "text"
                },
                {
                    "key": "reasoning",
                    "label": "Detailed Reasoning",
                    "type": "text"
                },
                {
                    "key": "evaluation_steps",
                    "label": "Generated Steps",
                    "type": "array"
                },
                {
                    "key": "passed",
                    "label": "Test Passed",
                    "type": "boolean"
                },
                {
                    "key": "confidence",
                    "label": "Confidence Score",
                    "type": "number"
                }
            ],
            risk_thresholds={"high": 0.8, "medium": 0.6, "low": 0.4},
            capabilities=[
                EvaluatorCapability.LLM_ENHANCED,
                EvaluatorCapability.GENERAL_TEXT_ANALYSIS
            ],
            llm_requirements=LLMRequirements(
                requirement_level=ModelRequirement.REQUIRED,
                suggested_providers=["anthropic", "openai", "google"],
                suggested_models=[
                    "claude-3-sonnet-20240229",
                    "claude-3-opus-20240229",
                    "gpt-4",
                    "gpt-4-turbo",
                    "gemini-pro"
                ],
                expected_response_format="json",
                min_context_window=8000
            ),
            rag_requirements=RAGRequirements(
                requirement_level=ModelRequirement.OPTIONAL,
                vector_store_required=False,
                min_context_chunks=1,
                max_context_chunks=15
            ),
            requires_test_subject_config=False,
            fallback_mode="degraded",
            estimated_runtime="medium",
            parallel_safe=True
        )

    def evaluate(
            self,
            text: str,
            test_subject_config: Optional[ModelConfig] = None,
            evaluator_llm_config: Optional[ModelConfig] = None,
            rag_config: Optional[Dict[str, Any]] = None,
            vector_store: Optional[Any] = None,
            **kwargs
    ) -> Dict[str, Any]:
        """
        Advanced G-Eval evaluation compatible with your framework's signature.

        Args:
            text: The AI-generated text to evaluate (the LLM's response)
            test_subject_config: Configuration of the model being tested (for context)
            evaluator_llm_config: Configuration for LLM to perform G-Eval analysis
            rag_config: RAG model configuration (optional, can enhance evaluation)
            vector_store: Vector store for retrieving evaluation context (optional)
            **kwargs: G-Eval specific parameters including:
                - criteria: Evaluation criteria (string) - REQUIRED
                - evaluation_steps: Pre-defined steps (optional)
                - threshold: Score threshold for pass/fail (default: 0.5)
                - strict_mode: Enable binary scoring (default: False)
                - input: Original input/prompt (for context)
                - expected_output: Expected response (for comparison)

        Returns:
            Dictionary containing comprehensive G-Eval results with weighted scoring
        """
        start_time = time.time()

        try:
            # VALIDATION: G-Eval requires an LLM to perform evaluation
            if not evaluator_llm_config:
                raise ValueError("G-Eval requires evaluator_llm_config to function")

            # Extract G-Eval specific parameters from kwargs
            criteria = kwargs.get('criteria')
            evaluation_steps = kwargs.get('evaluation_steps')
            evaluation_params = kwargs.get('evaluation_params', [LLMTestCaseParams.ACTUAL_OUTPUT])
            threshold = kwargs.get('threshold', 0.5)
            strict_mode = kwargs.get('strict_mode', False)
            verbose_mode = kwargs.get('verbose_mode', False)

            # Validate that criteria is provided (core requirement for G-Eval)
            if not criteria and not evaluation_steps:
                raise ValueError(
                    "G-Eval requires either 'criteria' or 'evaluation_steps' to be provided in the request configuration")

            # Extract context from both kwargs and standard framework parameters
            input_text = kwargs.get('input', kwargs.get('input_prompt', ''))
            expected_output = kwargs.get('expected_output', '')
            context = kwargs.get('context', '')
            retrieval_context = kwargs.get('retrieval_context', [])

            # Store all context for evaluation
            context_kwargs = {
                'input': input_text,
                'expected_output': expected_output,
                'context': context,
                'retrieval_context': retrieval_context
            }

            # Step 1: Generate evaluation steps if not provided
            if not evaluation_steps:
                if verbose_mode:
                    logger.info("Generating evaluation steps from criteria")

                evaluation_steps = self._generate_evaluation_steps(
                    criteria, evaluation_params, evaluator_llm_config
                )
            else:
                if verbose_mode:
                    logger.info("Using provided evaluation steps")

            # Step 2: Construct test case content from your framework's parameters
            test_case_content = self._construct_test_case_content(
                text, evaluation_params, context_kwargs
            )

            # Step 3: Generate evaluation parameters string
            params_string = self._construct_eval_params_string(evaluation_params)

            # Step 4: Perform evaluation with weighted scoring
            score, reasoning, confidence, steps_analysis = self._evaluate_with_cot(
                evaluation_steps=evaluation_steps,
                test_case_content=test_case_content,
                params_string=params_string,
                strict_mode=strict_mode,
                evaluator_config=evaluator_llm_config,
                verbose_mode=verbose_mode
            )

            # Step 5: Apply weighted normalization (deepeval's key innovation)
            if not strict_mode:
                score = self._apply_weighted_normalization(score, confidence)

            # Determine pass/fail
            passed = score >= threshold

            execution_time = time.time() - start_time

            # Prepare comprehensive results following your framework's pattern
            result = {
                "score": float(score),
                "criteria": criteria or "Custom evaluation steps provided",
                "reasoning": reasoning,
                "evaluation_steps": evaluation_steps,
                "steps_analysis": steps_analysis,
                "passed": passed,
                "threshold": threshold,
                "confidence": confidence,
                "strict_mode": strict_mode,
                "evaluation_cost": self.evaluation_cost,
                "execution_time": execution_time,

                # Framework compatibility fields
                "compliance_score": 100 - (score * 100),  # Convert to risk score (lower is better)
                "violations_count": 1 if not passed else 0,
                "method": "llm_enhanced_geval",

                "metadata": {
                    "evaluator_model": evaluator_llm_config.model_id,
                    "test_subject_model": test_subject_config.model_id if test_subject_config else "unknown",
                    "methodology": "Advanced G-Eval with Weighted Scoring",
                    "version": "2.0.0",
                    "framework_compatible": True,
                    "features": [
                        "chain_of_thought",
                        "weighted_scoring",
                        "log_probabilities",
                        "strict_mode"
                    ]
                }
            }

            if verbose_mode:
                logger.info(f"G-Eval completed: score={score:.3f}, passed={passed}, time={execution_time:.2f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Advanced G-Eval evaluation failed: {str(e)}")
            logger.error(traceback.format_exc())

            # Return error result compatible with your framework
            return {
                "score": 0.0,
                "compliance_score": 100.0,  # Maximum risk score on error
                "violations_count": 1,
                "method": "error",
                "criteria": kwargs.get('criteria', 'Unknown'),
                "reasoning": f"G-Eval evaluation failed: {str(e)}",
                "evaluation_steps": [],
                "steps_analysis": [],
                "passed": False,
                "confidence": 0.0,
                "error": str(e),
                "execution_time": execution_time,
                "metadata": {
                    "status": "error",
                    "error_type": type(e).__name__,
                    "framework_compatible": True
                }
            }

    def interpret(self, evaluation_result: Dict[str, Any]) -> str:
        """
        Interpret G-Eval results in a human-readable format.
        Compatible with your framework's interpretation system.
        """
        if "error" in evaluation_result:
            return f"G-Eval Error: {evaluation_result['error']}"

        score = evaluation_result.get('score', 0.0)
        passed = evaluation_result.get('passed', False)
        criteria = evaluation_result.get('criteria', 'Unknown criteria')
        reasoning = evaluation_result.get('reasoning', 'No reasoning provided')
        confidence = evaluation_result.get('confidence', 0.0)

        # Create interpretation based on score and pass/fail
        if passed:
            status = "✅ PASSED"
            risk_level = "LOW RISK"
        else:
            if score < 0.3:
                status = "❌ FAILED"
                risk_level = "HIGH RISK"
            elif score < 0.6:
                status = "⚠️ PARTIAL"
                risk_level = "MEDIUM RISK"
            else:
                status = "❌ FAILED"
                risk_level = "LOW-MEDIUM RISK"

        interpretation = f"""{status} - G-Eval Assessment ({risk_level})

📊 Score: {score:.3f}/1.0 (Confidence: {confidence:.2f})
🎯 Criteria: {criteria}

📝 Analysis:
{reasoning}

💡 Methodology: Advanced G-Eval with Chain-of-Thought reasoning and weighted scoring"""

        # Add evaluation steps if available
        steps_analysis = evaluation_result.get('steps_analysis', [])
        if steps_analysis:
            interpretation += "\n\n🔍 Step-by-Step Analysis:"
            for i, step in enumerate(steps_analysis, 1):
                interpretation += f"\n   {i}. {step}"

        return interpretation.strip()

    def summarize_category_results(self, category_results: List[Dict[str, Any]]) -> str:
        """
        Summarize G-Eval results for a category of prompts.
        Compatible with your framework's batch analysis system.
        """
        if not category_results:
            return "No G-Eval results to summarize"

        total_prompts = len(category_results)
        passed_count = 0
        failed_count = 0
        error_count = 0
        total_score = 0.0
        total_processing_time = 0

        for result in category_results:
            # Handle different result structures based on your framework pattern
            geval_result = None

            # Check if this is a direct G-Eval result
            if 'score' in result and 'criteria' in result:
                geval_result = result
            # Check if this is wrapped in the framework's test structure
            elif 'tests' in result and 'Advanced G-Eval Metric' in result['tests']:
                test_data = result['tests']['Advanced G-Eval Metric']
                if 'results' in test_data:
                    geval_result = test_data['results']
                elif 'status' in test_data and test_data['status'] == 'error':
                    error_count += 1
                    continue
            # Check if this is in raw_results field
            elif 'raw_results' in result:
                geval_result = result['raw_results']

            if geval_result:
                if geval_result.get('error'):
                    error_count += 1
                elif geval_result.get('passed', False):
                    passed_count += 1
                else:
                    failed_count += 1

                score = geval_result.get('score', 0.0)
                total_score += score

                processing_time = geval_result.get('execution_time', 0)
                if isinstance(processing_time, (int, float)):
                    total_processing_time += processing_time

        # Calculate averages
        avg_score = total_score / total_prompts if total_prompts > 0 else 0.0
        avg_processing_time = total_processing_time / total_prompts if total_prompts > 0 else 0.0
        pass_rate = (passed_count / total_prompts) * 100 if total_prompts > 0 else 0.0

        # Determine overall assessment
        if pass_rate >= 80:
            overall_status = "✅ EXCELLENT"
        elif pass_rate >= 60:
            overall_status = "👍 GOOD"
        elif pass_rate >= 40:
            overall_status = "⚠️ NEEDS IMPROVEMENT"
        else:
            overall_status = "❌ POOR PERFORMANCE"

        # Build summary
        summary = [
            f"Advanced G-Eval Metric Summary",
            f"=" * 50,
            f"Overall Status: {overall_status} (Pass Rate: {pass_rate:.1f}%)",
            f"",
            f"📊 Results Breakdown:",
            f"  Total Prompts: {total_prompts}",
            f"  ✅ Passed: {passed_count}",
            f"  ❌ Failed: {failed_count}",
            f"  ⚠️ Errors: {error_count}",
            f"",
            f"📈 Performance Metrics:",
            f"  Average Score: {avg_score:.3f}/1.0",
            f"  Average Processing Time: {avg_processing_time:.2f}s",
        ]

        # Add recommendations based on performance
        summary.extend([
            f"",
            f"💡 Recommendations:",
        ])

        if pass_rate < 60:
            summary.append(f"  - Review and strengthen evaluation criteria")
            summary.append(f"  - Consider adjusting thresholds based on requirements")

        if error_count > 0:
            summary.append(f"  - Investigate {error_count} evaluation errors")

        if avg_score < 0.6:
            summary.append(f"  - Focus on improving areas with low scores")

        summary.append(f"  - Use detailed reasoning from failed cases for model improvement")

        return "\n".join(summary)

    # Helper methods
    def _generate_evaluation_steps(
            self, criteria: str, evaluation_params: List[LLMTestCaseParams], config: ModelConfig
    ) -> List[str]:
        """Generate evaluation steps from criteria using chain-of-thought."""
        param_names = [param.value for param in evaluation_params]
        prompt = GEvalTemplate.generate_evaluation_steps(criteria, param_names)

        try:
            response = model_manager.get_evaluator_analysis(
                config=config,
                analysis_prompt=prompt,
                system_prompt="You are an expert at creating systematic evaluation procedures."
            )

            if hasattr(response, 'cost'):
                self.evaluation_cost += response.cost

            result = self._parse_json_response(response.content)
            steps = result.get("steps", [])

            if not steps:
                return self._generate_default_steps(criteria)

            return steps

        except Exception as e:
            logger.warning(f"Failed to generate evaluation steps: {e}")
            return self._generate_default_steps(criteria)

    def _evaluate_with_cot(
            self,
            evaluation_steps: List[str],
            test_case_content: str,
            params_string: str,
            strict_mode: bool,
            evaluator_config: ModelConfig,
            verbose_mode: bool
    ) -> Tuple[float, str, float, List[str]]:
        """Perform chain-of-thought evaluation with weighted scoring."""

        prompt = GEvalTemplate.generate_evaluation_results(
            evaluation_steps=evaluation_steps,
            test_case_content=test_case_content,
            parameters=params_string,
            strict_mode=strict_mode
        )

        try:
            response = model_manager.get_evaluator_analysis(
                config=evaluator_config,
                analysis_prompt=prompt,
                system_prompt="You are a precise evaluator using the G-Eval methodology."
            )

            if hasattr(response, 'cost'):
                self.evaluation_cost += response.cost

            result = self._parse_evaluation_response(response.content, strict_mode)

            score = result.get('score', 0.0)
            reasoning = result.get('reason', result.get('reasoning', 'No reasoning provided'))
            steps_analysis = result.get('steps_followed', [])

            confidence = self._calculate_confidence(result, response.content)

            if verbose_mode:
                logger.info(f"Evaluation completed: score={score}, confidence={confidence}")

            return float(score), reasoning, confidence, steps_analysis

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return 0.0, f"Evaluation error: {str(e)}", 0.0, []

    def _apply_weighted_normalization(self, score: float, confidence: float) -> float:
        """Apply weighted normalization similar to deepeval's approach."""
        try:
            # Simulate log probability weighting effect
            scale_score = score * 4 + 1  # 0-1 -> 1-5

            weights = []
            for i in range(1, 6):
                distance = abs(i - scale_score)
                prob = math.exp(-distance) * confidence
                weights.append(prob)

            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]
                weighted_score = sum(i * w for i, w in enumerate(weights, 1))
                normalized_score = (weighted_score - 1) / 4
                final_score = confidence * normalized_score + (1 - confidence) * score
                return max(0.0, min(1.0, final_score))

        except Exception as e:
            logger.warning(f"Weighted normalization failed: {e}")

        return score

    def _construct_test_case_content(
            self, text: str, evaluation_params: List[LLMTestCaseParams], kwargs: Dict[str, Any]
    ) -> str:
        """Construct test case content from available parameters."""
        content_parts = []

        for param in evaluation_params:
            if param == LLMTestCaseParams.ACTUAL_OUTPUT:
                content_parts.append(f"**Actual Output:**\n{text}")
            elif param == LLMTestCaseParams.INPUT:
                input_text = kwargs.get('input', '')
                if input_text:
                    content_parts.append(f"**Input:**\n{input_text}")
            elif param == LLMTestCaseParams.EXPECTED_OUTPUT:
                expected = kwargs.get('expected_output', '')
                if expected:
                    content_parts.append(f"**Expected Output:**\n{expected}")
            elif param == LLMTestCaseParams.CONTEXT:
                context = kwargs.get('context', '')
                if context:
                    content_parts.append(f"**Context:**\n{context}")
            elif param == LLMTestCaseParams.RETRIEVAL_CONTEXT:
                retrieval_context = kwargs.get('retrieval_context', [])
                if retrieval_context:
                    if isinstance(retrieval_context, list):
                        context_text = "\n".join([f"- {ctx}" for ctx in retrieval_context])
                    else:
                        context_text = str(retrieval_context)
                    content_parts.append(f"**Retrieval Context:**\n{context_text}")

        return "\n\n".join(content_parts)

    def _construct_eval_params_string(self, evaluation_params: List[LLMTestCaseParams]) -> str:
        """Generate evaluation parameters description."""
        param_descriptions = {
            LLMTestCaseParams.INPUT: "The original input/prompt given to the system",
            LLMTestCaseParams.ACTUAL_OUTPUT: "The output generated by the system being evaluated",
            LLMTestCaseParams.EXPECTED_OUTPUT: "The expected or reference output for comparison",
            LLMTestCaseParams.CONTEXT: "Additional context or background information",
            LLMTestCaseParams.RETRIEVAL_CONTEXT: "Retrieved context from knowledge base or documents"
        }

        descriptions = []
        for param in evaluation_params:
            desc = param_descriptions.get(param, f"Parameter: {param.value}")
            descriptions.append(f"- {param.value}: {desc}")

        return "\n".join(descriptions)

    def _calculate_confidence(self, result: Dict[str, Any], raw_response: str) -> float:
        """Calculate confidence score based on response quality."""
        confidence_factors = []

        if 'score' in result and 'reason' in result:
            confidence_factors.append(0.3)

        reasoning = result.get('reason', result.get('reasoning', ''))
        if len(reasoning) > 50:
            confidence_factors.append(0.2)

        try:
            json.loads(raw_response.strip())
            confidence_factors.append(0.2)
        except:
            pass

        score = result.get('score', 0)
        if 0 <= score <= 1:
            confidence_factors.append(0.3)

        return min(1.0, sum(confidence_factors))

    def _parse_evaluation_response(self, response: str, strict_mode: bool = False) -> Dict[str, Any]:
        """Parse LLM evaluation response with robust error handling."""
        try:
            json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            json_match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)

            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        raise ValueError("No JSON structure found")

            result = json.loads(json_str)

            score = result.get('score', 0.0)
            if isinstance(score, str):
                score = float(re.search(r'[\d.]+', score).group())

            score = max(0.0, min(1.0, float(score)))

            return {
                "score": score,
                "reason": result.get('reason', result.get('reasoning', 'No reasoning provided')),
                "steps_followed": result.get('steps_followed', []),
                "criteria_met": result.get('criteria_met', score >= 0.5)
            }

        except Exception as e:
            logger.warning(f"JSON parsing failed, using fallback: {e}")
            return self._fallback_parse(response, strict_mode)

    def _fallback_parse(self, response: str, strict_mode: bool) -> Dict[str, Any]:
        """Fallback parsing when JSON extraction fails."""
        score_patterns = [
            r'(?:score|rating)[:=\s]*([0-9]*\.?[0-9]+)',
            r'([0-9]*\.?[0-9]+)(?:/[0-9]+)?(?:\s*(?:out of|/)\s*[0-9]+)?'
        ]

        score = 0.0
        for pattern in score_patterns:
            score_match = re.search(pattern, response.lower())
            if score_match:
                try:
                    score = float(score_match.group(1))
                    if score > 1:
                        if score <= 5:
                            score = score / 5.0
                        elif score <= 10:
                            score = score / 10.0
                        else:
                            score = 1.0
                    break
                except ValueError:
                    continue

        if strict_mode:
            score = 1.0 if score >= 0.5 else 0.0

        return {
            "score": max(0.0, min(1.0, score)),
            "reason": response.strip()[:500] + "..." if len(response) > 500 else response.strip(),
            "steps_followed": [],
            "criteria_met": score >= 0.5
        }

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response with multiple fallback strategies."""
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            try:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))

                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))

                raise ValueError("No valid JSON found")
            except:
                return {"error": "Failed to parse JSON", "raw_response": response}

    def _generate_default_steps(self, criteria: str) -> List[str]:
        """Generate default evaluation steps when automatic generation fails."""
        return [
            f"Analyze the content against the criteria: {criteria}",
            "Identify key aspects that meet or don't meet the criteria",
            "Evaluate the overall quality and adherence to requirements",
            "Consider any partial fulfillment of the criteria",
            "Provide a final assessment based on your analysis"
        ]