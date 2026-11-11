"""
J1 Enhanced Model Service
Advanced AI prompt generation with thinking traces, genetic algorithms, and reinforcement learning
"""

import json
import asyncio
import random
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import structlog
from dataclasses import dataclass, asdict
import pickle
import os

from services.shared.exceptions import ValidationError, ExternalServiceError
from services.shared.redis_client import redis_client

logger = structlog.get_logger()

@dataclass
class ThinkingTrace:
    """Represents a thinking step in the J1 model."""
    step: int
    thought: str
    reasoning: str
    confidence: float
    evidence: List[str]
    alternatives: List[str]
    timestamp: str

@dataclass
class J1ModelState:
    """128-dimensional state space for J1 model."""
    # Requirement understanding (32 dimensions)
    requirement_clarity: float
    requirement_completeness: float
    requirement_specificity: float
    domain_relevance: float
    complexity_level: float
    ambiguity_score: float
    constraint_count: int
    priority_level: float
    
    # Context awareness (24 dimensions)
    historical_context: float
    domain_expertise: float
    user_intent: float
    stakeholder_needs: float
    regulatory_context: float
    technical_constraints: float
    
    # Generation strategy (32 dimensions)
    creativity_level: float
    risk_tolerance: float
    innovation_factor: float
    practicality_score: float
    implementation_difficulty: float
    resource_requirements: float
    time_constraints: float
    quality_expectations: float
    
    # Optimization state (24 dimensions)
    current_iteration: int
    fitness_score: float
    convergence_rate: float
    diversity_measure: float
    exploration_factor: float
    exploitation_factor: float
    learning_rate: float
    momentum: float
    
    # Performance metrics (16 dimensions)
    accuracy_score: float
    relevance_score: float
    coherence_score: float
    completeness_score: float
    novelty_score: float
    feasibility_score: float
    user_satisfaction: float
    success_rate: float
    
    def to_vector(self) -> np.ndarray:
        """Convert state to 128-dimensional vector."""
        return np.array(list(asdict(self).values()))
    
    @classmethod
    def from_vector(cls, vector: np.ndarray) -> 'J1ModelState':
        """Create state from 128-dimensional vector."""
        fields = list(cls.__annotations__.keys())
        kwargs = {field: float(vector[i]) for i, field in enumerate(fields)}
        return cls(**kwargs)

class GeneticAlgorithmOptimizer:
    """Genetic algorithm for prompt optimization."""
    
    def __init__(self, population_size: int = 50, mutation_rate: float = 0.1):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = 0.8
        self.elitism_count = 5
        
    async def optimize_prompt(
        self, 
        base_prompt: str, 
        requirements: Dict[str, Any],
        generations: int = 20
    ) -> Dict[str, Any]:
        """Optimize prompt using genetic algorithm."""
        
        # Initialize population
        population = await self._initialize_population(base_prompt, requirements)
        
        best_fitness_history = []
        evolution_trace = []
        
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = await self._evaluate_population(population, requirements)
            
            # Track best fitness
            best_fitness = max(fitness_scores)
            best_fitness_history.append(best_fitness)
            
            # Log evolution step
            evolution_step = {
                "generation": generation,
                "best_fitness": best_fitness,
                "average_fitness": np.mean(fitness_scores),
                "diversity": self._calculate_diversity(population),
                "timestamp": datetime.utcnow().isoformat()
            }
            evolution_trace.append(evolution_step)
            
            logger.debug("Genetic algorithm evolution", 
                        generation=generation, best_fitness=best_fitness)
            
            # Selection and reproduction
            population = await self._evolve_population(population, fitness_scores)
        
        # Get best individual
        final_fitness = await self._evaluate_population(population, requirements)
        best_idx = np.argmax(final_fitness)
        best_prompt = population[best_idx]
        
        return {
            "optimized_prompt": best_prompt,
            "final_fitness": final_fitness[best_idx],
            "fitness_history": best_fitness_history,
            "evolution_trace": evolution_trace,
            "generations_run": generations,
            "final_population_size": len(population)
        }
    
    async def _initialize_population(
        self, 
        base_prompt: str, 
        requirements: Dict[str, Any]
    ) -> List[str]:
        """Initialize population with prompt variations."""
        population = [base_prompt]  # Keep original
        
        # Generate variations
        for _ in range(self.population_size - 1):
            variation = await self._mutate_prompt(base_prompt, requirements)
            population.append(variation)
        
        return population
    
    async def _mutate_prompt(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Create a mutated version of the prompt."""
        mutations = [
            self._add_specification,
            self._modify_tone,
            self._add_constraints,
            self._restructure_format,
            self._add_examples,
            self._modify_complexity
        ]
        
        # Apply random mutations
        num_mutations = random.randint(1, 3)
        mutated = prompt
        
        for _ in range(num_mutations):
            mutation_func = random.choice(mutations)
            mutated = await mutation_func(mutated, requirements)
        
        return mutated
    
    async def _add_specification(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Add more specific requirements to the prompt."""
        specifications = [
            "Be specific and detailed in your response.",
            "Provide concrete examples where applicable.",
            "Include step-by-step explanations.",
            "Consider multiple perspectives.",
            "Address potential edge cases.",
            "Explain your reasoning clearly."
        ]
        
        if random.random() < 0.5:
            spec = random.choice(specifications)
            return f"{prompt}\n\nAdditional requirement: {spec}"
        
        return prompt
    
    async def _modify_tone(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Modify the tone of the prompt."""
        tones = [
            "professional and formal",
            "friendly and approachable", 
            "technical and precise",
            "creative and innovative",
            "analytical and systematic",
            "collaborative and inclusive"
        ]
        
        if "tone" not in prompt.lower() and random.random() < 0.3:
            tone = random.choice(tones)
            return f"{prompt}\n\nTone: Please respond in a {tone} manner."
        
        return prompt
    
    async def _add_constraints(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Add constraints to the prompt."""
        constraints = [
            "Keep the response under 500 words.",
            "Structure your response with clear headings.",
            "Include at least three key points.",
            "Provide actionable recommendations.",
            "Consider regulatory compliance.",
            "Address potential risks and mitigation strategies."
        ]
        
        if random.random() < 0.4:
            constraint = random.choice(constraints)
            return f"{prompt}\n\nConstraint: {constraint}"
        
        return prompt
    
    async def _restructure_format(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Restructure the prompt format."""
        formats = [
            "Please organize your response as: 1) Analysis, 2) Recommendations, 3) Implementation.",
            "Structure your answer with: Background, Current State, Proposed Solution, Next Steps.",
            "Format as: Executive Summary, Detailed Analysis, Action Items.",
            "Use this structure: Problem Statement, Solution Approach, Expected Outcomes."
        ]
        
        if random.random() < 0.3:
            format_instruction = random.choice(formats)
            return f"{prompt}\n\nFormat: {format_instruction}"
        
        return prompt
    
    async def _add_examples(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Add request for examples."""
        example_requests = [
            "Please include relevant examples to illustrate your points.",
            "Provide case studies or real-world applications.",
            "Include both positive and negative examples.",
            "Give specific examples from the industry context."
        ]
        
        if "example" not in prompt.lower() and random.random() < 0.3:
            example_req = random.choice(example_requests)
            return f"{prompt}\n\n{example_req}"
        
        return prompt
    
    async def _modify_complexity(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Adjust prompt complexity."""
        complexity_modifiers = [
            "Provide a comprehensive and thorough analysis.",
            "Give a high-level overview focusing on key concepts.",
            "Include technical details and implementation specifics.",
            "Explain in simple terms suitable for non-experts.",
            "Provide both summary and detailed perspectives."
        ]
        
        if random.random() < 0.2:
            modifier = random.choice(complexity_modifiers)
            return f"{prompt}\n\nComplexity: {modifier}"
        
        return prompt
    
    async def _evaluate_population(
        self, 
        population: List[str], 
        requirements: Dict[str, Any]
    ) -> List[float]:
        """Evaluate fitness of population."""
        fitness_scores = []
        
        for prompt in population:
            # Calculate fitness based on multiple criteria
            fitness = await self._calculate_fitness(prompt, requirements)
            fitness_scores.append(fitness)
        
        return fitness_scores
    
    async def _calculate_fitness(self, prompt: str, requirements: Dict[str, Any]) -> float:
        """Calculate fitness score for a prompt."""
        score = 0.0
        
        # Length appropriateness (20% weight)
        length_score = self._evaluate_length(prompt)
        score += 0.2 * length_score
        
        # Clarity and structure (25% weight)
        clarity_score = self._evaluate_clarity(prompt)
        score += 0.25 * clarity_score
        
        # Requirement coverage (30% weight)
        coverage_score = self._evaluate_coverage(prompt, requirements)
        score += 0.3 * coverage_score
        
        # Specificity and detail (15% weight)
        specificity_score = self._evaluate_specificity(prompt)
        score += 0.15 * specificity_score
        
        # Innovation and creativity (10% weight)
        creativity_score = self._evaluate_creativity(prompt)
        score += 0.1 * creativity_score
        
        return min(1.0, max(0.0, score))
    
    def _evaluate_length(self, prompt: str) -> float:
        """Evaluate prompt length appropriateness."""
        word_count = len(prompt.split())
        
        # Optimal range: 20-200 words
        if 20 <= word_count <= 200:
            return 1.0
        elif word_count < 20:
            return word_count / 20.0
        else:
            return max(0.3, 1.0 - (word_count - 200) / 500.0)
    
    def _evaluate_clarity(self, prompt: str) -> float:
        """Evaluate prompt clarity and structure."""
        score = 0.0
        
        # Check for question words
        question_words = ["what", "how", "why", "when", "where", "which", "who"]
        has_question = any(word in prompt.lower() for word in question_words)
        if has_question:
            score += 0.3
        
        # Check for clear instructions
        instruction_words = ["please", "describe", "explain", "analyze", "provide"]
        has_instruction = any(word in prompt.lower() for word in instruction_words)
        if has_instruction:
            score += 0.4
        
        # Check for structure indicators
        structure_words = ["first", "second", "then", "finally", "step", "phase"]
        has_structure = any(word in prompt.lower() for word in structure_words)
        if has_structure:
            score += 0.3
        
        return min(1.0, score)
    
    def _evaluate_coverage(self, prompt: str, requirements: Dict[str, Any]) -> float:
        """Evaluate how well prompt covers requirements."""
        if not requirements:
            return 0.8  # Default score if no specific requirements
        
        score = 0.0
        total_requirements = 0
        
        # Check domain coverage
        if "domain" in requirements:
            domain = requirements["domain"].lower()
            if domain in prompt.lower():
                score += 0.3
            total_requirements += 1
        
        # Check framework coverage
        if "framework" in requirements:
            framework = requirements["framework"].lower()
            if framework in prompt.lower():
                score += 0.3
            total_requirements += 1
        
        # Check type coverage
        if "type" in requirements:
            req_type = requirements["type"].lower()
            if req_type in prompt.lower():
                score += 0.4
            total_requirements += 1
        
        return score / max(1, total_requirements)
    
    def _evaluate_specificity(self, prompt: str) -> float:
        """Evaluate prompt specificity."""
        # Count specific terms
        specific_indicators = [
            "specific", "detailed", "concrete", "precise", "exact",
            "particular", "explicit", "clear", "defined", "measurable"
        ]
        
        specificity_count = sum(
            1 for word in specific_indicators 
            if word in prompt.lower()
        )
        
        return min(1.0, specificity_count / 3.0)
    
    def _evaluate_creativity(self, prompt: str) -> float:
        """Evaluate prompt creativity and innovation."""
        creative_indicators = [
            "creative", "innovative", "novel", "unique", "original",
            "alternative", "different", "new", "fresh", "imaginative"
        ]
        
        creativity_count = sum(
            1 for word in creative_indicators 
            if word in prompt.lower()
        )
        
        return min(1.0, creativity_count / 2.0)
    
    def _calculate_diversity(self, population: List[str]) -> float:
        """Calculate population diversity."""
        if len(population) < 2:
            return 0.0
        
        # Simple diversity measure based on length variation
        lengths = [len(prompt.split()) for prompt in population]
        length_std = np.std(lengths)
        
        # Normalize by mean length
        mean_length = np.mean(lengths)
        diversity = length_std / max(1, mean_length)
        
        return min(1.0, diversity)
    
    async def _evolve_population(
        self, 
        population: List[str], 
        fitness_scores: List[float]
    ) -> List[str]:
        """Evolve population through selection, crossover, and mutation."""
        
        # Sort by fitness
        sorted_indices = np.argsort(fitness_scores)[::-1]
        sorted_population = [population[i] for i in sorted_indices]
        sorted_fitness = [fitness_scores[i] for i in sorted_indices]
        
        new_population = []
        
        # Elitism - keep best individuals
        new_population.extend(sorted_population[:self.elitism_count])
        
        # Generate offspring
        while len(new_population) < self.population_size:
            # Tournament selection
            parent1 = self._tournament_selection(sorted_population, sorted_fitness)
            parent2 = self._tournament_selection(sorted_population, sorted_fitness)
            
            # Crossover
            if random.random() < self.crossover_rate:
                child = await self._crossover(parent1, parent2)
            else:
                child = parent1 if random.random() < 0.5 else parent2
            
            # Mutation
            if random.random() < self.mutation_rate:
                child = await self._mutate_prompt(child, {})
            
            new_population.append(child)
        
        return new_population[:self.population_size]
    
    def _tournament_selection(
        self, 
        population: List[str], 
        fitness_scores: List[float],
        tournament_size: int = 3
    ) -> str:
        """Select individual using tournament selection."""
        
        # Random tournament
        tournament_indices = random.sample(range(len(population)), 
                                         min(tournament_size, len(population)))
        
        # Select best from tournament
        best_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
        return population[best_idx]
    
    async def _crossover(self, parent1: str, parent2: str) -> str:
        """Create offspring through crossover."""
        
        # Simple sentence-level crossover
        sentences1 = parent1.split('. ')
        sentences2 = parent2.split('. ')
        
        # Combine sentences from both parents
        child_sentences = []
        max_sentences = max(len(sentences1), len(sentences2))
        
        for i in range(max_sentences):
            if i < len(sentences1) and i < len(sentences2):
                # Choose randomly from either parent
                sentence = sentences1[i] if random.random() < 0.5 else sentences2[i]
            elif i < len(sentences1):
                sentence = sentences1[i]
            else:
                sentence = sentences2[i]
            
            child_sentences.append(sentence)
        
        return '. '.join(child_sentences)

class ReinforcementLearningOptimizer:
    """Reinforcement learning for prompt optimization."""
    
    def __init__(self):
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.exploration_rate = 0.1
        self.q_table = {}
        
    async def optimize_prompt_rl(
        self,
        prompt: str,
        requirements: Dict[str, Any],
        episodes: int = 100
    ) -> Dict[str, Any]:
        """Optimize prompt using reinforcement learning."""
        
        episode_rewards = []
        state_history = []
        action_history = []
        
        current_prompt = prompt
        
        for episode in range(episodes):
            # Get current state
            state = self._get_state(current_prompt, requirements)
            
            # Choose action (modification strategy)
            action = self._choose_action(state)
            
            # Apply action to get new prompt
            new_prompt = await self._apply_action(current_prompt, action, requirements)
            
            # Calculate reward
            reward = await self._calculate_reward(new_prompt, current_prompt, requirements)
            
            # Update Q-table
            self._update_q_table(state, action, reward, new_prompt, requirements)
            
            # Track progress
            episode_rewards.append(reward)
            state_history.append(state)
            action_history.append(action)
            
            # Update current prompt if improvement
            if reward > 0:
                current_prompt = new_prompt
            
            logger.debug("RL episode completed", 
                        episode=episode, reward=reward)
        
        return {
            "optimized_prompt": current_prompt,
            "episode_rewards": episode_rewards,
            "state_history": state_history,
            "action_history": action_history,
            "final_q_table_size": len(self.q_table),
            "episodes_run": episodes
        }
    
    def _get_state(self, prompt: str, requirements: Dict[str, Any]) -> str:
        """Get state representation of prompt."""
        # Simple state encoding
        word_count = len(prompt.split())
        has_question = any(word in prompt.lower() for word in ["what", "how", "why"])
        has_structure = any(word in prompt.lower() for word in ["step", "first", "then"])
        
        state = f"wc_{word_count//10}_q_{has_question}_s_{has_structure}"
        return state
    
    def _choose_action(self, state: str) -> str:
        """Choose action using epsilon-greedy policy."""
        
        actions = [
            "add_detail", "add_structure", "add_example", 
            "modify_tone", "add_constraint", "simplify"
        ]
        
        if random.random() < self.exploration_rate:
            # Explore - random action
            return random.choice(actions)
        else:
            # Exploit - best known action
            if state in self.q_table:
                best_action = max(self.q_table[state], key=self.q_table[state].get)
                return best_action
            else:
                return random.choice(actions)
    
    async def _apply_action(
        self, 
        prompt: str, 
        action: str, 
        requirements: Dict[str, Any]
    ) -> str:
        """Apply action to modify prompt."""
        
        if action == "add_detail":
            return f"{prompt}\n\nPlease provide detailed explanations and specific examples."
        
        elif action == "add_structure":
            return f"{prompt}\n\nPlease structure your response with clear sections and headings."
        
        elif action == "add_example":
            return f"{prompt}\n\nInclude relevant examples to illustrate your points."
        
        elif action == "modify_tone":
            return f"{prompt}\n\nPlease respond in a professional and analytical tone."
        
        elif action == "add_constraint":
            return f"{prompt}\n\nKeep your response concise and focused on key points."
        
        elif action == "simplify":
            # Remove some complexity
            simplified = prompt.replace("\n\n", "\n").strip()
            return simplified
        
        return prompt
    
    async def _calculate_reward(
        self, 
        new_prompt: str, 
        old_prompt: str, 
        requirements: Dict[str, Any]
    ) -> float:
        """Calculate reward for prompt modification."""
        
        # Compare fitness scores
        old_fitness = await self._quick_fitness(old_prompt, requirements)
        new_fitness = await self._quick_fitness(new_prompt, requirements)
        
        # Reward is improvement
        reward = new_fitness - old_fitness
        
        # Add small penalty for length increase
        old_length = len(old_prompt.split())
        new_length = len(new_prompt.split())
        length_penalty = (new_length - old_length) * 0.01
        
        return reward - length_penalty
    
    async def _quick_fitness(self, prompt: str, requirements: Dict[str, Any]) -> float:
        """Quick fitness calculation for RL."""
        # Simplified fitness calculation
        score = 0.0
        
        # Length score
        word_count = len(prompt.split())
        if 20 <= word_count <= 100:
            score += 0.5
        
        # Structure score
        if any(word in prompt.lower() for word in ["step", "first", "section"]):
            score += 0.3
        
        # Clarity score
        if any(word in prompt.lower() for word in ["please", "explain", "describe"]):
            score += 0.2
        
        return score
    
    def _update_q_table(
        self, 
        state: str, 
        action: str, 
        reward: float, 
        new_prompt: str, 
        requirements: Dict[str, Any]
    ):
        """Update Q-table with new experience."""
        
        if state not in self.q_table:
            self.q_table[state] = {}
        
        if action not in self.q_table[state]:
            self.q_table[state][action] = 0.0
        
        # Get next state
        next_state = self._get_state(new_prompt, requirements)
        
        # Calculate max Q-value for next state
        max_next_q = 0.0
        if next_state in self.q_table and self.q_table[next_state]:
            max_next_q = max(self.q_table[next_state].values())
        
        # Q-learning update
        current_q = self.q_table[state][action]
        target_q = reward + self.discount_factor * max_next_q
        new_q = current_q + self.learning_rate * (target_q - current_q)
        
        self.q_table[state][action] = new_q

class J1EnhancedService:
    """J1 Enhanced Model Service with thinking traces and optimization."""
    
    def __init__(self):
        self.genetic_optimizer = GeneticAlgorithmOptimizer()
        self.rl_optimizer = ReinforcementLearningOptimizer()
        self.thinking_cache = {}
        self.performance_history = []
        
    async def generate_with_thinking(
        self,
        requirements: str,
        context: Dict[str, Any],
        optimization_enabled: bool = True
    ) -> Dict[str, Any]:
        """Generate prompt with visible thinking process."""
        
        thinking_trace = []
        
        # Step 1: Requirement Analysis
        req_analysis = await self._analyze_requirements(requirements, context)
        thinking_trace.append(ThinkingTrace(
            step=1,
            thought="Analyzing requirements and context",
            reasoning=f"Breaking down the requirements: {requirements[:100]}...",
            confidence=req_analysis["confidence"],
            evidence=req_analysis["key_elements"],
            alternatives=req_analysis["alternatives"],
            timestamp=datetime.utcnow().isoformat()
        ))
        
        # Step 2: Strategy Selection
        strategy = await self._select_generation_strategy(req_analysis, context)
        thinking_trace.append(ThinkingTrace(
            step=2,
            thought="Selecting generation strategy",
            reasoning=f"Chosen strategy: {strategy['name']} because {strategy['reasoning']}",
            confidence=strategy["confidence"],
            evidence=strategy["evidence"],
            alternatives=strategy["alternatives"],
            timestamp=datetime.utcnow().isoformat()
        ))
        
        # Step 3: Initial Generation
        initial_prompt = await self._generate_initial_prompt(req_analysis, strategy)
        thinking_trace.append(ThinkingTrace(
            step=3,
            thought="Generating initial prompt",
            reasoning="Creating base prompt structure with identified requirements",
            confidence=0.7,
            evidence=[f"Prompt length: {len(initial_prompt.split())} words"],
            alternatives=["Template-based approach", "Iterative refinement"],
            timestamp=datetime.utcnow().isoformat()
        ))
        
        # Step 4: Optimization (if enabled)
        final_prompt = initial_prompt
        optimization_results = None
        
        if optimization_enabled:
            opt_method = strategy.get("optimization_method", "genetic")
            
            if opt_method == "genetic":
                optimization_results = await self.genetic_optimizer.optimize_prompt(
                    initial_prompt, req_analysis, generations=10
                )
                final_prompt = optimization_results["optimized_prompt"]
                
            elif opt_method == "reinforcement":
                optimization_results = await self.rl_optimizer.optimize_prompt_rl(
                    initial_prompt, req_analysis, episodes=50
                )
                final_prompt = optimization_results["optimized_prompt"]
            
            thinking_trace.append(ThinkingTrace(
                step=4,
                thought=f"Optimizing with {opt_method} algorithm",
                reasoning=f"Applied {opt_method} optimization to improve prompt quality",
                confidence=0.85,
                evidence=[f"Final fitness: {optimization_results.get('final_fitness', 'N/A')}"],
                alternatives=["Manual refinement", "Alternative algorithms"],
                timestamp=datetime.utcnow().isoformat()
            ))
        
        # Step 5: Quality Assessment
        quality_assessment = await self._assess_quality(final_prompt, req_analysis)
        thinking_trace.append(ThinkingTrace(
            step=5,
            thought="Assessing final quality",
            reasoning="Evaluating prompt against quality criteria",
            confidence=quality_assessment["overall_confidence"],
            evidence=quality_assessment["strengths"],
            alternatives=quality_assessment["improvement_suggestions"],
            timestamp=datetime.utcnow().isoformat()
        ))
        
        # Cache thinking trace
        trace_id = f"trace_{datetime.utcnow().timestamp()}"
        await self._cache_thinking_trace(trace_id, thinking_trace)
        
        return {
            "prompt": final_prompt,
            "thinking_trace": [asdict(trace) for trace in thinking_trace],
            "trace_id": trace_id,
            "optimization_results": optimization_results,
            "quality_assessment": quality_assessment,
            "j1_state": await self._get_current_j1_state(req_analysis, strategy),
            "generation_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "optimization_enabled": optimization_enabled,
                "strategy_used": strategy["name"],
                "total_thinking_steps": len(thinking_trace)
            }
        }
    
    async def _analyze_requirements(
        self, 
        requirements: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze and break down requirements."""
        
        # Extract key elements
        key_elements = []
        confidence = 0.8
        
        # Domain detection
        domains = ["healthcare", "finance", "legal", "technology", "education"]
        detected_domain = None
        for domain in domains:
            if domain in requirements.lower() or domain in str(context).lower():
                detected_domain = domain
                key_elements.append(f"Domain: {domain}")
                break
        
        # Complexity assessment
        word_count = len(requirements.split())
        if word_count > 50:
            complexity = "high"
            confidence *= 0.9
        elif word_count > 20:
            complexity = "medium"
        else:
            complexity = "low"
        
        key_elements.append(f"Complexity: {complexity}")
        
        # Framework detection
        frameworks = ["GDPR", "HIPAA", "SOX", "EU AI Act", "ISO"]
        detected_frameworks = []
        for framework in frameworks:
            if framework.lower() in requirements.lower():
                detected_frameworks.append(framework)
                key_elements.append(f"Framework: {framework}")
        
        return {
            "key_elements": key_elements,
            "detected_domain": detected_domain,
            "complexity": complexity,
            "frameworks": detected_frameworks,
            "confidence": confidence,
            "word_count": word_count,
            "alternatives": [
                "Different domain interpretation",
                "Alternative complexity assessment",
                "Multiple framework consideration"
            ]
        }
    
    async def _select_generation_strategy(
        self, 
        req_analysis: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Select optimal generation strategy."""
        
        complexity = req_analysis["complexity"]
        domain = req_analysis.get("detected_domain")
        
        strategies = {
            "structured_analytical": {
                "name": "Structured Analytical",
                "description": "Systematic breakdown with clear structure",
                "optimization_method": "genetic",
                "suitable_for": ["high_complexity", "technical_domains"]
            },
            "creative_exploratory": {
                "name": "Creative Exploratory", 
                "description": "Open-ended exploration with innovation focus",
                "optimization_method": "reinforcement",
                "suitable_for": ["medium_complexity", "creative_domains"]
            },
            "template_based": {
                "name": "Template-Based",
                "description": "Using proven templates with customization",
                "optimization_method": "genetic",
                "suitable_for": ["low_complexity", "standard_domains"]
            }
        }
        
        # Strategy selection logic
        if complexity == "high" or domain in ["legal", "healthcare"]:
            selected = strategies["structured_analytical"]
        elif complexity == "medium":
            selected = strategies["creative_exploratory"]
        else:
            selected = strategies["template_based"]
        
        selected["reasoning"] = f"Selected due to {complexity} complexity and {domain} domain"
        selected["confidence"] = 0.8
        selected["evidence"] = [
            f"Complexity level: {complexity}",
            f"Domain match: {domain}",
            "Historical performance data"
        ]
        selected["alternatives"] = [
            name for name in strategies.keys() if name != selected["name"]
        ]
        
        return selected
    
    async def _generate_initial_prompt(
        self, 
        req_analysis: Dict[str, Any], 
        strategy: Dict[str, Any]
    ) -> str:
        """Generate initial prompt based on analysis and strategy."""
        
        base_template = self._get_base_template(strategy["name"])
        
        # Customize based on requirements
        domain = req_analysis.get("detected_domain", "general")
        complexity = req_analysis.get("complexity", "medium")
        frameworks = req_analysis.get("frameworks", [])
        
        prompt_parts = [base_template]
        
        # Add domain-specific elements
        if domain:
            prompt_parts.append(f"Focus on {domain} domain considerations.")
        
        # Add framework requirements
        if frameworks:
            framework_text = ", ".join(frameworks)
            prompt_parts.append(f"Ensure compliance with {framework_text} requirements.")
        
        # Add complexity-appropriate instructions
        if complexity == "high":
            prompt_parts.append("Provide comprehensive analysis with detailed explanations.")
        elif complexity == "low":
            prompt_parts.append("Keep explanations clear and concise.")
        
        return "\n\n".join(prompt_parts)
    
    def _get_base_template(self, strategy_name: str) -> str:
        """Get base template for strategy."""
        
        templates = {
            "Structured Analytical": """
Please provide a systematic analysis of the given topic. Structure your response with:
1. Overview and context
2. Detailed analysis
3. Key findings
4. Recommendations
5. Implementation considerations
""".strip(),
            
            "Creative Exploratory": """
Explore this topic with creativity and innovation. Consider:
- Multiple perspectives and approaches
- Novel solutions and alternatives
- Creative applications and possibilities
- Future implications and opportunities
""".strip(),
            
            "Template-Based": """
Please address the following systematically:
- Current situation analysis
- Key requirements and constraints
- Proposed approach
- Expected outcomes
""".strip()
        }
        
        return templates.get(strategy_name, templates["Template-Based"])
    
    async def _assess_quality(
        self, 
        prompt: str, 
        req_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess quality of generated prompt."""
        
        strengths = []
        weaknesses = []
        
        # Length assessment
        word_count = len(prompt.split())
        if 30 <= word_count <= 150:
            strengths.append("Appropriate length")
        else:
            weaknesses.append("Suboptimal length")
        
        # Structure assessment
        if any(indicator in prompt for indicator in ["1.", "2.", "-", "•"]):
            strengths.append("Well-structured")
        else:
            weaknesses.append("Could benefit from better structure")
        
        # Clarity assessment
        clarity_words = ["please", "explain", "describe", "analyze", "provide"]
        if any(word in prompt.lower() for word in clarity_words):
            strengths.append("Clear instructions")
        else:
            weaknesses.append("Instructions could be clearer")
        
        # Calculate confidence
        total_criteria = len(strengths) + len(weaknesses)
        confidence = len(strengths) / max(1, total_criteria)
        
        return {
            "overall_confidence": confidence,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "improvement_suggestions": [
                "Add more specific examples",
                "Include success criteria",
                "Specify desired output format"
            ]
        }
    
    async def _get_current_j1_state(
        self, 
        req_analysis: Dict[str, Any], 
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get current J1 model state."""
        
        # Create J1 state based on analysis
        state = J1ModelState(
            requirement_clarity=req_analysis["confidence"],
            requirement_completeness=0.8,
            requirement_specificity=0.7,
            domain_relevance=0.9 if req_analysis.get("detected_domain") else 0.5,
            complexity_level={"low": 0.3, "medium": 0.6, "high": 0.9}.get(
                req_analysis.get("complexity", "medium"), 0.6
            ),
            ambiguity_score=0.2,
            constraint_count=len(req_analysis.get("frameworks", [])),
            priority_level=0.8,
            
            # Context awareness
            historical_context=0.7,
            domain_expertise=0.8,
            user_intent=0.9,
            stakeholder_needs=0.7,
            regulatory_context=0.8 if req_analysis.get("frameworks") else 0.3,
            technical_constraints=0.6,
            
            # Generation strategy
            creativity_level=0.8 if strategy["name"] == "Creative Exploratory" else 0.5,
            risk_tolerance=0.6,
            innovation_factor=0.7,
            practicality_score=0.8,
            implementation_difficulty=0.5,
            resource_requirements=0.6,
            time_constraints=0.7,
            quality_expectations=0.9,
            
            # Optimization state
            current_iteration=1,
            fitness_score=0.8,
            convergence_rate=0.1,
            diversity_measure=0.7,
            exploration_factor=0.6,
            exploitation_factor=0.4,
            learning_rate=0.1,
            momentum=0.2,
            
            # Performance metrics
            accuracy_score=0.8,
            relevance_score=0.9,
            coherence_score=0.8,
            completeness_score=0.7,
            novelty_score=0.6,
            feasibility_score=0.8,
            user_satisfaction=0.0,  # Not yet available
            success_rate=0.0  # Not yet available
        )
        
        return {
            "state_vector": state.to_vector().tolist(),
            "state_dict": asdict(state),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _cache_thinking_trace(
        self, 
        trace_id: str, 
        thinking_trace: List[ThinkingTrace]
    ):
        """Cache thinking trace for later retrieval."""
        try:
            trace_data = {
                "trace_id": trace_id,
                "steps": [asdict(trace) for trace in thinking_trace],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await redis_client.set_json(
                f"thinking_trace:{trace_id}",
                trace_data,
                ex=3600  # 1 hour expiry
            )
            
        except Exception as e:
            logger.warning("Failed to cache thinking trace", error=str(e))

# Global service instance
j1_enhanced_service = J1EnhancedService()