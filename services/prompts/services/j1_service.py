"""J1 service for prompt generation and optimization."""

import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog
import random

from services.shared.exceptions import ValidationError, ExternalServiceError
from services.shared.redis_client import redis_client

# Import Unified API with fallback
try:
    from shared.unified_api.base import ModelConfig, ModelType
    from shared.unified_api import get_unified_api
except ImportError:
    ModelConfig = Any
    ModelType = Any
    get_unified_api = None

logger = structlog.get_logger()

class J1Service:
    """J1 service for prompt optimization with Unified API support."""
    
    def __init__(self):
        self.initialized = False
        
        # Unified API for LLM interactions
        self.unified_api = None
        
        # Performance analytics (5-dimensional analysis)
        self.performance_dimensions = [
            "clarity",
            "structure", 
            "specificity",
            "tone_appropriateness",
            "actionability"
        ]
    
    async def initialize(self):
        """Initialize the J1 service with Unified API support."""
        if self.initialized:
            return
        
        try:
            # Initialize Unified API for LLM interactions
            if get_unified_api:
                self.unified_api = get_unified_api()
                providers = self.unified_api.list_providers()
                logger.info("Unified API initialized for J1 service", providers=providers)
            else:
                logger.warning("Unified API not available - LLM enhancement disabled")
            
            self.initialized = True
            logger.info("J1 service initialized successfully")
            
        except Exception as e:
            logger.error("J1 service initialization failed", error=str(e))
            raise ExternalServiceError("J1Service", f"Initialization failed: {str(e)}")
    
    async def generate_prompts(
        self,
        requirements: str,
        category: str = "general",
        count: int = 1,
        system_context: Optional[str] = None,
        llm_config: Optional[ModelConfig] = None,
        optimization_params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate initial prompts using genetic algorithm approach."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            # Generate base prompts using template-based approach
            base_prompts = self._generate_base_prompts(requirements, category, count)
            
            # Apply genetic algorithm for initial optimization
            optimized_prompts = await self._apply_genetic_optimization(
                base_prompts, requirements, system_context
            )
            
            # Evaluate and score prompts
            scored_prompts = []
            for prompt in optimized_prompts:
                score = await self._evaluate_prompt_quality(prompt, requirements, llm_config)
                scored_prompts.append({
                    "text": prompt,
                    "quality_score": score,
                    "category": category,
                    "generated_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "llm_enhanced": llm_config is not None and self.unified_api is not None,
                        "optimization_params": optimization_params
                    },
                    "thinking_trace": {
                        "evaluation_method": "llm_enhanced" if (llm_config and self.unified_api) else "rule_based",
                        "requirements_alignment": f"Evaluated against: {requirements[:100]}..."
                    }
                })
            
            # Sort by quality score
            scored_prompts.sort(key=lambda x: x["quality_score"], reverse=True)
            
            logger.info(
                "Prompts generated successfully",
                count=len(scored_prompts),
                avg_quality=np.mean([p["quality_score"] for p in scored_prompts])
            )
            
            return scored_prompts[:count]
            
        except Exception as e:
            logger.error("Prompt generation failed", error=str(e))
            raise ValidationError(f"Prompt generation failed: {str(e)}")
    
    def _generate_base_prompts(
        self, 
        requirements: str, 
        category: str, 
        count: int
    ) -> List[str]:
        """Generate base prompts using templates and variations."""
        
        templates = {
            "general": [
                "Create a comprehensive guide that {requirements}. Include specific examples and actionable steps.",
                "Develop detailed instructions for {requirements}. Focus on clarity and practical implementation.",
                "Write a thorough explanation of {requirements}. Provide context and real-world applications."
            ],
            "technical_writing": [
                "Write technical documentation that {requirements}. Include code examples, best practices, and troubleshooting tips.",
                "Create a developer guide for {requirements}. Focus on implementation details and common pitfalls.",
                "Develop comprehensive technical specifications for {requirements}. Include architecture diagrams and API references."
            ],
            "educational": [
                "Design a learning module that {requirements}. Include exercises, assessments, and progressive difficulty.",
                "Create an educational resource for {requirements}. Focus on clear explanations and interactive elements.",
                "Develop a curriculum that {requirements}. Include learning objectives and practical applications."
            ]
        }
        
        category_templates = templates.get(category, templates["general"])
        base_prompts = []
        
        for i in range(count):
            template = category_templates[i % len(category_templates)]
            prompt = template.format(requirements=requirements.lower())
            
            # Add variations
            variations = [
                f"Please {prompt}",
                f"Your task is to {prompt}",
                f"I need you to {prompt}",
                prompt
            ]
            
            base_prompts.append(variations[i % len(variations)])
        
        return base_prompts
    
    async def _apply_genetic_optimization(
        self,
        base_prompts: List[str],
        requirements: str,
        system_context: Optional[str]
    ) -> List[str]:
        """Apply genetic algorithm for initial prompt optimization."""
        
        population = base_prompts.copy()
        generations = 3  # Limited generations for initial optimization
        
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = []
            for prompt in population:
                score = await self._evaluate_prompt_quality(prompt, requirements)
                fitness_scores.append(score)
            
            # Selection: keep top 50%
            sorted_population = sorted(
                zip(population, fitness_scores), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            selected = [prompt for prompt, _ in sorted_population[:len(population)//2]]
            
            # Crossover and mutation
            new_population = selected.copy()
            
            while len(new_population) < len(population):
                parent1, parent2 = random.sample(selected, 2)
                child = self._crossover_prompts(parent1, parent2)
                child = self._mutate_prompt(child)
                new_population.append(child)
            
            population = new_population
        
        return population
    
    def _crossover_prompts(self, parent1: str, parent2: str) -> str:
        """Create child prompt by combining parts of two parent prompts."""
        
        words1 = parent1.split()
        words2 = parent2.split()
        
        # Take first half from parent1, second half from parent2
        split_point = len(words1) // 2
        child_words = words1[:split_point] + words2[split_point:]
        
        return " ".join(child_words)
    
    def _mutate_prompt(self, prompt: str) -> str:
        """Apply random mutations to a prompt."""
        
        mutations = [
            lambda p: p.replace("create", "develop"),
            lambda p: p.replace("write", "compose"),
            lambda p: p.replace("include", "incorporate"),
            lambda p: p.replace("provide", "offer"),
            lambda p: p.replace("explain", "describe"),
            lambda p: f"{p} Be thorough and detailed.",
            lambda p: f"{p} Focus on practical applications.",
            lambda p: f"Please {p.lower()}"
        ]
        
        if random.random() < 0.3:  # 30% mutation rate
            mutation = random.choice(mutations)
            try:
                return mutation(prompt)
            except:
                return prompt
        
        return prompt
    
    async def _evaluate_prompt_quality(
        self, 
        prompt: str, 
        requirements: str,
        llm_config: Optional[ModelConfig] = None
    ) -> float:
        """Evaluate prompt quality using multiple criteria and optional LLM enhancement."""
        
        # Always compute rule-based scores as baseline
        rule_based_score = self._compute_rule_based_quality(prompt, requirements)
        
        # If Unified API and LLM config available, enhance with LLM evaluation
        if self.unified_api and llm_config:
            try:
                llm_score = await self._llm_enhanced_quality_evaluation(prompt, requirements, llm_config)
                # Weighted combination: 60% LLM, 40% rule-based
                return 0.6 * llm_score + 0.4 * rule_based_score
            except Exception as e:
                logger.warning(f"LLM quality evaluation failed, using rule-based: {e}")
                return rule_based_score
        
        return rule_based_score
    
    def _compute_rule_based_quality(self, prompt: str, requirements: str) -> float:
        """Compute rule-based quality score."""
        scores = []
        
        # Length appropriateness (0.0 to 1.0)
        length_score = min(1.0, len(prompt.split()) / 50.0)
        scores.append(length_score)
        
        # Clarity (based on simple heuristics)
        clarity_indicators = ["clear", "specific", "detailed", "step", "example"]
        clarity_score = sum(1 for indicator in clarity_indicators if indicator in prompt.lower()) / len(clarity_indicators)
        scores.append(clarity_score)
        
        # Structure (presence of organizing words)
        structure_indicators = ["first", "then", "next", "finally", "include", "focus"]
        structure_score = sum(1 for indicator in structure_indicators if indicator in prompt.lower()) / len(structure_indicators)
        scores.append(structure_score)
        
        # Relevance to requirements (simple keyword matching)
        requirement_words = set(requirements.lower().split())
        prompt_words = set(prompt.lower().split())
        relevance_score = len(requirement_words.intersection(prompt_words)) / len(requirement_words) if requirement_words else 0.5
        scores.append(relevance_score)
        
        # Actionability (presence of action words)
        action_words = ["create", "write", "develop", "include", "provide", "explain", "describe"]
        action_score = sum(1 for word in action_words if word in prompt.lower()) / len(action_words)
        scores.append(action_score)
        
        return np.mean(scores)
    
    async def _llm_enhanced_quality_evaluation(
        self, 
        prompt: str, 
        requirements: str, 
        llm_config: ModelConfig
    ) -> float:
        """Use LLM to evaluate prompt quality."""
        evaluation_prompt = f"""
        Evaluate the quality of this prompt for generating content that meets the specified requirements.

        Requirements: {requirements}

        Prompt to evaluate: {prompt}

        Please rate the prompt on a scale of 0.0 to 1.0 based on:
        - Clarity and specificity
        - Alignment with requirements
        - Actionability and structure
        - Likelihood to produce quality results

        Respond with just a number between 0.0 and 1.0.
        """
        
        try:
            response = await self.unified_api.agenerate(
                evaluation_prompt,
                llm_config,
                temperature=0.1,  # Low temperature for consistent evaluation
                max_tokens=10
            )
            
            if response.error:
                raise Exception(f"LLM evaluation error: {response.error}")
            
            # Extract numeric score from response
            score_text = response.content.strip()
            try:
                score = float(score_text)
                return max(0.0, min(1.0, score))  # Clamp to [0,1]
            except ValueError:
                # Try to extract first number from response
                import re
                numbers = re.findall(r'(\d+\.?\d*)', score_text)
                if numbers:
                    score = float(numbers[0])
                    # If score > 1, assume it's out of 10 or 100
                    if score > 1:
                        if score <= 10:
                            score = score / 10.0
                        else:
                            score = score / 100.0
                    return max(0.0, min(1.0, score))
                else:
                    raise ValueError("No numeric score found in response")
                    
        except Exception as e:
            logger.warning(f"LLM quality evaluation failed: {e}")
            raise
    
    async def optimize_prompt(
        self,
        original_prompt: str,
        feedback: Dict[str, Any],
        optimization_goals: List[str] = None,
        llm_config: Optional[ModelConfig] = None
    ) -> Dict[str, Any]:
        """Optimize a prompt based on feedback using LLM-enhanced or rule-based methods."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            # Use LLM-enhanced optimization if available
            if self.unified_api and llm_config:
                return await self._llm_enhanced_prompt_optimization(
                    original_prompt, feedback, optimization_goals, llm_config
                )
            else:
                return await self._rule_based_prompt_optimization(
                    original_prompt, feedback, optimization_goals
                )
                
        except Exception as e:
            logger.error("Prompt optimization failed", error=str(e))
            raise ValidationError(f"Prompt optimization failed: {str(e)}")
    
    async def _llm_enhanced_prompt_optimization(
        self,
        original_prompt: str,
        feedback: Dict[str, Any],
        optimization_goals: List[str],
        llm_config: ModelConfig
    ) -> Dict[str, Any]:
        """Use LLM to optimize prompt based on feedback."""
        
        goals_text = ", ".join(optimization_goals) if optimization_goals else "improve overall quality"
        feedback_text = feedback.get("feedback_text", "No specific feedback provided")
        
        optimization_prompt = f"""
        Optimize this prompt based on the provided feedback and goals.

        Original prompt: {original_prompt}

        Feedback: {feedback_text}

        Optimization goals: {goals_text}

        Please provide an improved version of the prompt that addresses the feedback and achieves the optimization goals. 
        Respond with just the optimized prompt, no additional explanation.
        """
        
        try:
            response = await self.unified_api.agenerate(
                optimization_prompt,
                llm_config,
                temperature=0.3,  # Some creativity but not too much
                max_tokens=500
            )
            
            if response.error:
                raise Exception(f"LLM optimization error: {response.error}")
            
            optimized_prompt = response.content.strip()
            
            # Evaluate improvement
            original_score = await self._evaluate_prompt_quality(original_prompt, "", llm_config)
            optimized_score = await self._evaluate_prompt_quality(optimized_prompt, "", llm_config)
            
            return {
                "optimized_prompt": optimized_prompt,
                "original_prompt": original_prompt,
                "improvement_score": optimized_score - original_score,
                "optimization_reasoning": f"Applied LLM-based optimization with goals: {goals_text}",
                "method": "llm_enhanced",
                "llm_model": llm_config.model_id,
                "llm_provider": llm_config.provider
            }
            
        except Exception as e:
            logger.warning(f"LLM optimization failed, falling back to rule-based: {e}")
            return await self._rule_based_prompt_optimization(original_prompt, feedback, optimization_goals)
    
    async def _rule_based_prompt_optimization(
        self,
        original_prompt: str,
        feedback: Dict[str, Any],
        optimization_goals: List[str]
    ) -> Dict[str, Any]:
        """Rule-based prompt optimization."""
        
        optimized = original_prompt
        applied_optimizations = []
        
        # Apply optimization based on goals
        if not optimization_goals:
            optimization_goals = ["clarity", "specificity"]
        
        for goal in optimization_goals:
            if goal.lower() in ["clarity", "clear"]:
                if "specific" not in optimized.lower():
                    optimized = optimized.replace("detailed", "specific and detailed")
                    applied_optimizations.append("Enhanced clarity with specific language")
            
            elif goal.lower() in ["specificity", "specific"]:
                if "example" not in optimized.lower():
                    optimized += " Include specific examples."
                    applied_optimizations.append("Added example requirement")
            
            elif goal.lower() in ["structure", "organization"]:
                if "step" not in optimized.lower():
                    optimized = optimized.replace("explain", "explain step by step")
                    applied_optimizations.append("Enhanced structure with step-by-step approach")
        
        # Apply feedback-based improvements
        feedback_text = feedback.get("feedback_text", "").lower()
        if "too long" in feedback_text:
            # Simplify language
            optimized = optimized.replace("comprehensive", "complete")
            optimized = optimized.replace("utilize", "use")
            applied_optimizations.append("Simplified language based on feedback")
        
        elif "unclear" in feedback_text or "confusing" in feedback_text:
            optimized = f"Please {optimized.lower()}" if not optimized.lower().startswith("please") else optimized
            applied_optimizations.append("Added polite instruction based on feedback")
        
        return {
            "optimized_prompt": optimized,
            "original_prompt": original_prompt,
            "optimization_reasoning": "; ".join(applied_optimizations) if applied_optimizations else "Applied basic optimization patterns",
            "method": "rule_based",
            "applied_optimizations": applied_optimizations
        }
    
    async def analyze_thinking_trace(self, prompt_id: str) -> Dict[str, Any]:
        """Analyze thinking trace for a prompt."""
        try:
            # Get cached thinking trace
            cache_key = f"thinking_trace:{prompt_id}"
            trace_data = await redis_client.get_json(cache_key)
            
            if not trace_data:
                return {
                    "analysis": "No thinking trace found for this prompt",
                    "insights": [],
                    "recommendations": []
                }
            
            # Basic analysis of thinking trace
            analysis = {
                "analysis": "Thinking trace analysis completed",
                "trace_length": len(str(trace_data)),
                "insights": [
                    "Prompt generation followed systematic approach",
                    "Quality evaluation was performed"
                ],
                "recommendations": [
                    "Consider using LLM-enhanced evaluation for better quality assessment",
                    "Try different optimization parameters for varied results"
                ],
                "trace_summary": trace_data
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Thinking trace analysis failed: {e}")
            return {
                "analysis": f"Analysis failed: {str(e)}",
                "insights": [],
                "recommendations": []
            }
    
    async def close(self):
        """Close the J1 service."""
        logger.info("J1 service closed")

# Global instance
j1_service = J1Service()