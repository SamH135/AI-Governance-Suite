"""J1 Reinforcement Learning Service for advanced prompt optimization."""

import asyncio
import json
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import random
from collections import defaultdict, deque

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

class ActionType(Enum):
    """Types of optimization actions the RL agent can take."""
    ENHANCE_CLARITY = "enhance_clarity"
    IMPROVE_STRUCTURE = "improve_structure"
    INCREASE_SPECIFICITY = "increase_specificity"
    ADJUST_TONE = "adjust_tone"
    ADD_EXAMPLES = "add_examples"
    SIMPLIFY_LANGUAGE = "simplify_language"
    EXPAND_CONTEXT = "expand_context"
    REFINE_INSTRUCTIONS = "refine_instructions"

@dataclass
class State:
    """Represents the current state of a prompt optimization."""
    complexity: float
    clarity_score: float
    structure_score: float
    specificity_score: float
    tone_score: float
    length: int
    example_count: int
    instruction_count: int
    
    def to_vector(self) -> np.ndarray:
        """Convert state to 128-dimensional vector for RL processing."""
        # Base features (8 dimensions)
        base_features = np.array([
            self.complexity,
            self.clarity_score,
            self.structure_score,
            self.specificity_score,
            self.tone_score,
            min(self.length / 1000.0, 1.0),  # Normalized length
            min(self.example_count / 10.0, 1.0),  # Normalized example count
            min(self.instruction_count / 20.0, 1.0)  # Normalized instruction count
        ])
        
        # Extended features through polynomial expansion and interactions
        extended_features = []
        
        # Polynomial features (degree 2)
        for i in range(len(base_features)):
            for j in range(i, len(base_features)):
                extended_features.append(base_features[i] * base_features[j])
        
        # Trigonometric features for cyclical patterns
        for feature in base_features:
            extended_features.extend([
                np.sin(2 * np.pi * feature),
                np.cos(2 * np.pi * feature)
            ])
        
        # Statistical features
        extended_features.extend([
            np.mean(base_features),
            np.std(base_features),
            np.max(base_features),
            np.min(base_features)
        ])
        
        # Pad or truncate to exactly 128 dimensions
        extended_array = np.array(extended_features)
        if len(extended_array) < 128:
            # Pad with zeros
            padding = np.zeros(128 - len(extended_array))
            extended_array = np.concatenate([extended_array, padding])
        else:
            # Truncate to 128
            extended_array = extended_array[:128]
        
        return extended_array

@dataclass
class Action:
    """Represents an optimization action."""
    type: ActionType
    intensity: float  # 0.0 to 1.0
    parameters: Dict[str, Any]

@dataclass
class Experience:
    """Represents an experience tuple for RL learning."""
    state: State
    action: Action
    reward: float
    next_state: State
    done: bool
    timestamp: datetime

class QLearningAgent:
    """Q-Learning agent for prompt optimization."""
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01
    ):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Q-table: state_hash -> action_type -> q_value
        self.q_table: Dict[str, Dict[ActionType, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        
        # Experience replay buffer
        self.memory: deque = deque(maxlen=10000)
        
        # Action space
        self.action_space = list(ActionType)
        
        # Performance tracking
        self.episode_rewards = []
        self.episode_lengths = []
        
    def _state_to_hash(self, state: State) -> str:
        """Convert state to hash for Q-table indexing."""
        # Discretize continuous values for Q-table
        discretized = [
            round(state.complexity, 1),
            round(state.clarity_score, 1),
            round(state.structure_score, 1),
            round(state.specificity_score, 1),
            round(state.tone_score, 1),
            min(state.length // 100, 10),  # Bucket length
            min(state.example_count, 5),
            min(state.instruction_count, 10)
        ]
        return str(tuple(discretized))
    
    def select_action(self, state: State) -> Action:
        """Select action using epsilon-greedy policy."""
        state_hash = self._state_to_hash(state)
        
        if random.random() < self.epsilon:
            # Exploration: random action
            action_type = random.choice(self.action_space)
        else:
            # Exploitation: best known action
            q_values = self.q_table[state_hash]
            if not q_values:
                action_type = random.choice(self.action_space)
            else:
                action_type = max(q_values.keys(), key=lambda a: q_values[a])
        
        # Generate action parameters based on type and state
        intensity = random.uniform(0.3, 1.0)
        parameters = self._generate_action_parameters(action_type, state, intensity)
        
        return Action(type=action_type, intensity=intensity, parameters=parameters)
    
    def _generate_action_parameters(
        self, 
        action_type: ActionType, 
        state: State, 
        intensity: float
    ) -> Dict[str, Any]:
        """Generate parameters for a specific action type."""
        
        if action_type == ActionType.ENHANCE_CLARITY:
            return {
                "simplify_vocabulary": intensity > 0.7,
                "add_transitions": intensity > 0.5,
                "remove_ambiguity": True
            }
        
        elif action_type == ActionType.IMPROVE_STRUCTURE:
            return {
                "add_headers": intensity > 0.6,
                "use_bullet_points": intensity > 0.4,
                "logical_flow": True
            }
        
        elif action_type == ActionType.INCREASE_SPECIFICITY:
            return {
                "add_details": intensity > 0.5,
                "quantify_statements": intensity > 0.7,
                "provide_context": True
            }
        
        elif action_type == ActionType.ADJUST_TONE:
            target_formality = 0.5 + (intensity - 0.5) * 0.5
            return {
                "target_formality": target_formality,
                "maintain_consistency": True
            }
        
        elif action_type == ActionType.ADD_EXAMPLES:
            return {
                "example_count": int(intensity * 3) + 1,
                "relevant_examples": True,
                "diverse_examples": intensity > 0.6
            }
        
        elif action_type == ActionType.SIMPLIFY_LANGUAGE:
            return {
                "reduce_complexity": intensity,
                "use_common_words": intensity > 0.5,
                "shorter_sentences": intensity > 0.7
            }
        
        elif action_type == ActionType.EXPAND_CONTEXT:
            return {
                "add_background": intensity > 0.6,
                "explain_assumptions": intensity > 0.4,
                "provide_rationale": True
            }
        
        elif action_type == ActionType.REFINE_INSTRUCTIONS:
            return {
                "make_actionable": True,
                "add_steps": intensity > 0.5,
                "clarify_expectations": intensity > 0.7
            }
        
        return {}
    
    def update_q_value(
        self, 
        state: State, 
        action: Action, 
        reward: float, 
        next_state: State, 
        done: bool
    ):
        """Update Q-value using Q-learning update rule."""
        
        state_hash = self._state_to_hash(state)
        next_state_hash = self._state_to_hash(next_state)
        
        # Current Q-value
        current_q = self.q_table[state_hash][action.type]
        
        # Maximum Q-value for next state
        if done:
            max_next_q = 0.0
        else:
            next_q_values = self.q_table[next_state_hash]
            max_next_q = max(next_q_values.values()) if next_q_values else 0.0
        
        # Q-learning update
        target_q = reward + self.discount_factor * max_next_q
        new_q = current_q + self.learning_rate * (target_q - current_q)
        
        self.q_table[state_hash][action.type] = new_q
        
        # Store experience for replay
        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            timestamp=datetime.utcnow()
        )
        self.memory.append(experience)
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "q_table_size": len(self.q_table),
            "memory_size": len(self.memory),
            "current_epsilon": self.epsilon,
            "learning_rate": self.learning_rate,
            "action_space_size": len(self.action_space),
            "total_episodes": len(self.episode_rewards),
            "average_reward": np.mean(self.episode_rewards) if self.episode_rewards else 0.0,
            "average_episode_length": np.mean(self.episode_lengths) if self.episode_lengths else 0.0
        }

class J1Service:
    """J1 Reinforcement Learning Service for prompt optimization with Unified API support."""
    
    def __init__(self):
        self.initialized = False
        self.rl_agent = QLearningAgent()
        self.optimization_history = []
        
        # Unified API for LLM interactions
        self.unified_api = None
        
        # Thinking traces for transparency
        self.thinking_traces = []
        
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
            
            # Load any saved Q-table from Redis
            await self._load_q_table()
            
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
    
    async def optimize_prompt_with_rl(
        self,
        initial_prompt: str,
        context: Dict[str, Any],
        max_iterations: int = 10,
        target_reward: float = 0.8
    ) -> Dict[str, Any]:
        """Optimize prompt using reinforcement learning."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            current_prompt = initial_prompt
            current_state = self._prompt_to_state(current_prompt, context)
            
            optimization_history = []
            total_reward = 0.0
            
            # Add thinking trace
            thinking_trace = {
                "initial_analysis": f"Starting optimization of prompt with {len(initial_prompt.split())} words",
                "context_analysis": f"Context complexity: {context.get('complexity', 0.5):.2f}",
                "optimization_goal": f"Target reward: {target_reward}"
            }
            
            for iteration in range(max_iterations):
                # Select action using RL agent
                action = self.rl_agent.select_action(current_state)
                
                # Apply action to prompt
                new_prompt = await self._apply_action(current_prompt, action, context)
                new_state = self._prompt_to_state(new_prompt, context)
                
                # Calculate reward
                reward = await self._calculate_reward(
                    current_prompt, new_prompt, context, action
                )
                
                # Update Q-learning
                done = (reward >= target_reward) or (iteration == max_iterations - 1)
                self.rl_agent.update_q_value(
                    current_state, action, reward, new_state, done
                )
                
                # Record history
                history_entry = {
                    "iteration": iteration + 1,
                    "action": {
                        "type": action.type.value,
                        "intensity": action.intensity,
                        "parameters": action.parameters
                    },
                    "reward": reward,
                    "prompt_length": len(new_prompt.split()),
                    "epsilon": self.rl_agent.epsilon
                }
                optimization_history.append(history_entry)
                
                # Update thinking trace
                thinking_trace[f"iteration_{iteration + 1}"] = {
                    "action_taken": action.type.value,
                    "reasoning": f"Applied {action.type.value} with intensity {action.intensity:.2f}",
                    "reward_received": reward,
                    "improvement": reward > 0.5
                }
                
                total_reward += reward
                current_prompt = new_prompt
                current_state = new_state
                
                # Early stopping if target reached
                if reward >= target_reward:
                    break
            
            # Final analysis
            final_reward = optimization_history[-1]["reward"] if optimization_history else 0.0
            average_reward = total_reward / len(optimization_history) if optimization_history else 0.0
            
            # J1 analysis
            j1_analysis = await self._generate_j1_analysis(
                initial_prompt, current_prompt, optimization_history, context
            )
            
            # Store thinking trace
            self.thinking_traces.append({
                "timestamp": datetime.utcnow().isoformat(),
                "optimization_id": f"opt_{len(self.thinking_traces)}",
                "trace": thinking_trace
            })
            
            # Save Q-table periodically
            if len(optimization_history) > 0:
                await self._save_q_table()
            
            result = {
                "optimized_prompt": current_prompt,
                "initial_prompt": initial_prompt,
                "final_reward": final_reward,
                "average_reward": average_reward,
                "total_iterations": len(optimization_history),
                "optimization_history": optimization_history,
                "j1_analysis": j1_analysis,
                "thinking_trace": thinking_trace,
                "rl_statistics": self.rl_agent.get_statistics()
            }
            
            logger.info(
                "RL optimization completed",
                final_reward=final_reward,
                iterations=len(optimization_history)
            )
            
            return result
            
        except Exception as e:
            logger.error("RL optimization failed", error=str(e))
            raise ValidationError(f"RL optimization failed: {str(e)}")
    
    def _prompt_to_state(self, prompt: str, context: Dict[str, Any]) -> State:
        """Convert prompt and context to RL state representation."""
        
        words = prompt.split()
        
        # Calculate basic metrics
        complexity = context.get("complexity", 0.5)
        
        # Heuristic scoring (in real implementation, use ML models)
        clarity_score = min(1.0, len([w for w in words if len(w) <= 6]) / len(words))
        structure_score = min(1.0, len([w for w in words if w.lower() in ["first", "then", "next", "finally"]]) / 4)
        specificity_score = min(1.0, len([w for w in words if len(w) > 8]) / max(1, len(words) // 10))
        tone_score = context.get("formality", 0.7)
        
        example_count = prompt.lower().count("example") + prompt.lower().count("instance")
        instruction_count = len([w for w in words if w.lower() in ["create", "write", "develop", "include"]])
        
        return State(
            complexity=complexity,
            clarity_score=clarity_score,
            structure_score=structure_score,
            specificity_score=specificity_score,
            tone_score=tone_score,
            length=len(words),
            example_count=example_count,
            instruction_count=instruction_count
        )
    
    async def _apply_action(
        self, 
        prompt: str, 
        action: Action, 
        context: Dict[str, Any]
    ) -> str:
        """Apply RL action to modify the prompt."""
        
        if action.type == ActionType.ENHANCE_CLARITY:
            return self._enhance_clarity(prompt, action.parameters)
        
        elif action.type == ActionType.IMPROVE_STRUCTURE:
            return self._improve_structure(prompt, action.parameters)
        
        elif action.type == ActionType.INCREASE_SPECIFICITY:
            return self._increase_specificity(prompt, action.parameters)
        
        elif action.type == ActionType.ADJUST_TONE:
            return self._adjust_tone(prompt, action.parameters)
        
        elif action.type == ActionType.ADD_EXAMPLES:
            return self._add_examples(prompt, action.parameters)
        
        elif action.type == ActionType.SIMPLIFY_LANGUAGE:
            return self._simplify_language(prompt, action.parameters)
        
        elif action.type == ActionType.EXPAND_CONTEXT:
            return self._expand_context(prompt, action.parameters)
        
        elif action.type == ActionType.REFINE_INSTRUCTIONS:
            return self._refine_instructions(prompt, action.parameters)
        
        return prompt
    
    def _enhance_clarity(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Enhance prompt clarity."""
        enhanced = prompt
        
        if parameters.get("add_transitions"):
            if "then" not in enhanced.lower():
                enhanced = enhanced.replace(". ", ". Then, ")
        
        if parameters.get("remove_ambiguity"):
            enhanced = enhanced.replace("it", "the content")
            enhanced = enhanced.replace("this", "the task")
        
        return enhanced
    
    def _improve_structure(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Improve prompt structure."""
        structured = prompt
        
        if parameters.get("add_headers") and ":" not in structured:
            structured = f"Task: {structured}"
        
        if parameters.get("use_bullet_points") and "include" in structured.lower():
            structured = structured.replace("include", "include:\n- ")
        
        return structured
    
    def _increase_specificity(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Increase prompt specificity."""
        specific = prompt
        
        if parameters.get("add_details"):
            specific = specific.replace("comprehensive", "comprehensive and detailed")
            specific = specific.replace("guide", "step-by-step guide")
        
        if parameters.get("quantify_statements"):
            specific = specific.replace("examples", "at least 3 examples")
            specific = specific.replace("steps", "5-7 clear steps")
        
        return specific
    
    def _adjust_tone(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Adjust prompt tone."""
        adjusted = prompt
        target_formality = parameters.get("target_formality", 0.7)
        
        if target_formality > 0.7:
            # More formal
            adjusted = adjusted.replace("you", "the user")
            adjusted = adjusted.replace("your", "the user's")
        else:
            # Less formal
            adjusted = adjusted.replace("the user", "you")
            adjusted = adjusted.replace("one should", "you should")
        
        return adjusted
    
    def _add_examples(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Add examples to prompt."""
        example_count = parameters.get("example_count", 1)
        
        if "example" not in prompt.lower():
            addition = f" Include {example_count} relevant example{'s' if example_count > 1 else ''}."
            return prompt + addition
        
        return prompt
    
    def _simplify_language(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Simplify prompt language."""
        simplified = prompt
        
        # Replace complex words with simpler alternatives
        replacements = {
            "comprehensive": "complete",
            "utilize": "use",
            "demonstrate": "show",
            "facilitate": "help",
            "implement": "do"
        }
        
        for complex_word, simple_word in replacements.items():
            simplified = simplified.replace(complex_word, simple_word)
        
        return simplified
    
    def _expand_context(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Expand prompt context."""
        expanded = prompt
        
        if parameters.get("add_background"):
            expanded = f"Background: This task requires understanding of the subject matter. {expanded}"
        
        if parameters.get("provide_rationale"):
            expanded = f"{expanded} This will help ensure accuracy and usefulness."
        
        return expanded
    
    def _refine_instructions(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """Refine prompt instructions."""
        refined = prompt
        
        if parameters.get("make_actionable"):
            if not any(word in refined.lower() for word in ["create", "write", "develop", "make"]):
                refined = f"Create {refined.lower()}"
        
        if parameters.get("clarify_expectations"):
            refined = f"{refined} Ensure the output is clear, accurate, and well-organized."
        
        return refined
    
    async def _calculate_reward(
        self,
        old_prompt: str,
        new_prompt: str,
        context: Dict[str, Any],
        action: Action
    ) -> float:
        """Calculate reward for the RL action."""
        
        # Evaluate both prompts
        old_quality = await self._evaluate_prompt_quality(old_prompt, context.get("requirements", ""))
        new_quality = await self._evaluate_prompt_quality(new_prompt, context.get("requirements", ""))
        
        # Base reward is improvement
        improvement = new_quality - old_quality
        
        # Bonus for reaching quality thresholds
        if new_quality > 0.8:
            improvement += 0.2
        elif new_quality > 0.6:
            improvement += 0.1
        
        # Penalty for making prompt too long
        if len(new_prompt.split()) > len(old_prompt.split()) * 1.5:
            improvement -= 0.1
        
        # Action-specific bonuses
        if action.type == ActionType.ENHANCE_CLARITY and "clear" in new_prompt.lower():
            improvement += 0.05
        
        if action.type == ActionType.ADD_EXAMPLES and "example" in new_prompt.lower():
            improvement += 0.05
        
        return max(-1.0, min(1.0, improvement))  # Clamp to [-1, 1]
    
    async def _generate_j1_analysis(
        self,
        initial_prompt: str,
        final_prompt: str,
        history: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive J1 analysis of the optimization process."""
        
        initial_quality = await self._evaluate_prompt_quality(initial_prompt, context.get("requirements", ""))
        final_quality = await self._evaluate_prompt_quality(final_prompt, context.get("requirements", ""))
        
        # Analyze improvement areas
        improvement_areas = []
        if final_quality > initial_quality:
            improvement_areas.append("overall_quality")
        
        if len(final_prompt.split()) > len(initial_prompt.split()):
            improvement_areas.append("detail_level")
        
        if "example" in final_prompt.lower() and "example" not in initial_prompt.lower():
            improvement_areas.append("example_inclusion")
        
        # Analyze RL effectiveness
        rewards = [entry["reward"] for entry in history]
        convergence_analysis = "converged" if len(rewards) > 3 and np.std(rewards[-3:]) < 0.1 else "still_learning"
        
        # Action effectiveness
        action_counts = defaultdict(int)
        action_rewards = defaultdict(list)
        
        for entry in history:
            action_type = entry["action"]["type"]
            reward = entry["reward"]
            action_counts[action_type] += 1
            action_rewards[action_type].append(reward)
        
        best_actions = sorted(
            action_rewards.keys(),
            key=lambda a: np.mean(action_rewards[a]),
            reverse=True
        )[:3]
        
        return {
            "improvement_summary": f"Quality improved from {initial_quality:.3f} to {final_quality:.3f}",
            "quality_comparison": {
                "initial_quality": initial_quality,
                "final_quality": final_quality,
                "improvement": final_quality - initial_quality,
                "improvement_areas": improvement_areas
            },
            "rl_effectiveness": {
                "convergence_analysis": convergence_analysis,
                "action_effectiveness": best_actions,
                "exploration_rate": self.rl_agent.epsilon,
                "learning_progress": "positive" if np.mean(rewards) > 0 else "needs_improvement"
            },
            "5_dimensional_analysis": {
                "clarity": self._analyze_dimension(initial_prompt, final_prompt, "clarity"),
                "structure": self._analyze_dimension(initial_prompt, final_prompt, "structure"),
                "specificity": self._analyze_dimension(initial_prompt, final_prompt, "specificity"),
                "tone_appropriateness": self._analyze_dimension(initial_prompt, final_prompt, "tone"),
                "actionability": self._analyze_dimension(initial_prompt, final_prompt, "actionability")
            }
        }
    
    def _analyze_dimension(self, initial: str, final: str, dimension: str) -> Dict[str, Any]:
        """Analyze improvement in a specific dimension."""
        
        if dimension == "clarity":
            initial_score = len([w for w in initial.split() if len(w) <= 6]) / len(initial.split())
            final_score = len([w for w in final.split() if len(w) <= 6]) / len(final.split())
        
        elif dimension == "structure":
            structure_words = ["first", "then", "next", "finally", "include"]
            initial_score = sum(1 for w in structure_words if w in initial.lower()) / len(structure_words)
            final_score = sum(1 for w in structure_words if w in final.lower()) / len(structure_words)
        
        elif dimension == "specificity":
            initial_score = len([w for w in initial.split() if len(w) > 8]) / max(1, len(initial.split()) // 10)
            final_score = len([w for w in final.split() if len(w) > 8]) / max(1, len(final.split()) // 10)
        
        elif dimension == "tone":
            formal_words = ["comprehensive", "utilize", "demonstrate", "facilitate"]
            initial_score = sum(1 for w in formal_words if w in initial.lower()) / len(formal_words)
            final_score = sum(1 for w in formal_words if w in final.lower()) / len(formal_words)
        
        elif dimension == "actionability":
            action_words = ["create", "write", "develop", "include", "provide"]
            initial_score = sum(1 for w in action_words if w in initial.lower()) / len(action_words)
            final_score = sum(1 for w in action_words if w in final.lower()) / len(action_words)
        
        else:
            initial_score = final_score = 0.5
        
        return {
            "initial_score": initial_score,
            "final_score": final_score,
            "improvement": final_score - initial_score,
            "status": "improved" if final_score > initial_score else "maintained" if final_score == initial_score else "declined"
        }
    
    async def get_rl_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive RL optimization statistics."""
        
        rl_stats = self.rl_agent.get_statistics()
        
        return {
            "rl_stats": rl_stats,
            "optimization_history_count": len(self.optimization_history),
            "thinking_traces_count": len(self.thinking_traces),
            "service_status": "initialized" if self.initialized else "not_initialized",
            "performance_dimensions": self.performance_dimensions
        }
    
    async def _load_q_table(self):
        """Load Q-table from Redis if available."""
        try:
            q_table_data = await redis_client.get("j1_service:q_table")
            if q_table_data:
                # Convert back to proper format
                loaded_data = json.loads(q_table_data)
                for state_hash, actions in loaded_data.items():
                    for action_str, q_value in actions.items():
                        action_type = ActionType(action_str)
                        self.rl_agent.q_table[state_hash][action_type] = q_value
                
                logger.info("Q-table loaded from Redis", size=len(self.rl_agent.q_table))
        except Exception as e:
            logger.warning("Failed to load Q-table from Redis", error=str(e))
    
    async def _save_q_table(self):
        """Save Q-table to Redis."""
        try:
            # Convert Q-table to JSON-serializable format
            serializable_q_table = {}
            for state_hash, actions in self.rl_agent.q_table.items():
                serializable_q_table[state_hash] = {
                    action_type.value: q_value 
                    for action_type, q_value in actions.items()
                }
            
            await redis_client.setex(
                "j1_service:q_table",
                3600 * 24,  # 24 hours
                json.dumps(serializable_q_table)
            )
            
            logger.debug("Q-table saved to Redis")
        except Exception as e:
            logger.warning("Failed to save Q-table to Redis", error=str(e))
    
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
        try:
            # Save Q-table before closing
            await self._save_q_table()
            
            logger.info("J1 service closed")
        except Exception as e:
            logger.error("J1 service close failed", error=str(e))

# Global instance
j1_service = J1Service()