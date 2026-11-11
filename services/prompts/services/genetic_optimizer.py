"""Genetic algorithm optimization for J1 prompt generation."""

import asyncio
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

from services.shared.exceptions import ValidationError

logger = structlog.get_logger()

@dataclass
class PromptGene:
    """Individual gene in the genetic algorithm."""
    text: str
    fitness_score: float = 0.0
    generation: int = 0
    parent_ids: List[str] = None
    mutations: List[str] = None
    
    def __post_init__(self):
        if self.parent_ids is None:
            self.parent_ids = []
        if self.mutations is None:
            self.mutations = []

class GeneticOptimizer:
    """Genetic algorithm optimizer for prompt evolution."""
    
    def __init__(self):
        self.population_size = 20
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
        self.elite_size = 4
        self.max_generations = 10
        self.fitness_threshold = 0.9
        self.diversity_weight = 0.2
        
        # Mutation strategies
        self.mutation_strategies = [
            self._word_substitution,
            self._phrase_insertion,
            self._sentence_reordering,
            self._style_modification,
            self._length_adjustment
        ]
        
        # Crossover strategies
        self.crossover_strategies = [
            self._single_point_crossover,
            self._two_point_crossover,
            self._uniform_crossover,
            self._semantic_crossover
        ]
    
    async def optimize_prompt(
        self,
        initial_prompt: str,
        requirements: str,
        fitness_function: callable,
        target_fitness: float = 0.9,
        max_generations: int = None
    ) -> Dict[str, Any]:
        """Optimize a prompt using genetic algorithm."""
        
        try:
            logger.info("Starting genetic optimization", 
                       initial_prompt=initial_prompt[:100],
                       target_fitness=target_fitness)
            
            max_generations = max_generations or self.max_generations
            
            # Initialize population
            population = await self._initialize_population(initial_prompt, requirements)
            
            # Evolution loop
            best_fitness_history = []
            diversity_history = []
            
            for generation in range(max_generations):
                # Evaluate fitness
                await self._evaluate_population(population, fitness_function)
                
                # Track metrics
                best_fitness = max(gene.fitness_score for gene in population)
                diversity = self._calculate_diversity(population)
                
                best_fitness_history.append(best_fitness)
                diversity_history.append(diversity)
                
                logger.debug("Generation completed", 
                           generation=generation,
                           best_fitness=best_fitness,
                           diversity=diversity)
                
                # Check termination conditions
                if best_fitness >= target_fitness:
                    logger.info("Target fitness reached", 
                               generation=generation, fitness=best_fitness)
                    break
                
                # Create next generation
                population = await self._create_next_generation(population, generation + 1)
            
            # Get best result
            best_gene = max(population, key=lambda g: g.fitness_score)
            
            result = {
                "optimized_prompt": best_gene.text,
                "final_fitness": best_gene.fitness_score,
                "generations": generation + 1,
                "fitness_history": best_fitness_history,
                "diversity_history": diversity_history,
                "evolution_metadata": {
                    "initial_prompt": initial_prompt,
                    "population_size": self.population_size,
                    "mutation_rate": self.mutation_rate,
                    "crossover_rate": self.crossover_rate,
                    "mutations_applied": best_gene.mutations,
                    "parent_lineage": best_gene.parent_ids
                }
            }
            
            logger.info("Genetic optimization completed", 
                       final_fitness=best_gene.fitness_score,
                       generations=generation + 1)
            
            return result
            
        except Exception as e:
            logger.error("Genetic optimization failed", error=str(e))
            raise ValidationError(f"Genetic optimization failed: {str(e)}")
    
    async def _initialize_population(
        self, 
        initial_prompt: str, 
        requirements: str
    ) -> List[PromptGene]:
        """Initialize the population with diverse variants."""
        
        population = []
        
        # Add the original prompt
        population.append(PromptGene(text=initial_prompt, generation=0))
        
        # Generate variants
        for i in range(self.population_size - 1):
            variant = await self._generate_variant(initial_prompt, requirements)
            population.append(PromptGene(text=variant, generation=0))
        
        return population
    
    async def _generate_variant(self, base_prompt: str, requirements: str) -> str:
        """Generate a variant of the base prompt."""
        
        # Simple variant generation strategies
        strategies = [
            self._add_context_variant,
            self._rephrase_variant,
            self._add_constraints_variant,
            self._change_tone_variant,
            self._add_examples_variant
        ]
        
        strategy = random.choice(strategies)
        return await strategy(base_prompt, requirements)
    
    async def _add_context_variant(self, prompt: str, requirements: str) -> str:
        """Add contextual information to the prompt."""
        contexts = [
            "Please consider the following context: ",
            "Given the requirements: ",
            "In the context of compliance testing: ",
            "For enterprise applications: ",
            "Considering best practices: "
        ]
        context = random.choice(contexts)
        return f"{context}{prompt}"
    
    async def _rephrase_variant(self, prompt: str, requirements: str) -> str:
        """Rephrase the prompt with different wording."""
        # Simple rephrasing by changing some words
        replacements = {
            "generate": "create",
            "provide": "give",
            "ensure": "make sure",
            "consider": "think about",
            "analyze": "examine"
        }
        
        variant = prompt
        for old, new in replacements.items():
            if old in variant.lower():
                variant = variant.replace(old, new)
                break
        
        return variant
    
    async def _add_constraints_variant(self, prompt: str, requirements: str) -> str:
        """Add constraints to make the prompt more specific."""
        constraints = [
            "Be specific and detailed in your response.",
            "Provide examples where applicable.",
            "Consider edge cases and limitations.",
            "Ensure accuracy and reliability.",
            "Focus on practical implementation."
        ]
        constraint = random.choice(constraints)
        return f"{prompt} {constraint}"
    
    async def _change_tone_variant(self, prompt: str, requirements: str) -> str:
        """Change the tone of the prompt."""
        tones = [
            "Please respond in a professional manner: ",
            "Provide a comprehensive analysis: ",
            "Give a concise and clear answer: ",
            "Explain in technical detail: ",
            "Summarize the key points: "
        ]
        tone = random.choice(tones)
        return f"{tone}{prompt}"
    
    async def _add_examples_variant(self, prompt: str, requirements: str) -> str:
        """Add request for examples."""
        example_requests = [
            "Include relevant examples.",
            "Provide concrete examples.",
            "Give specific use cases.",
            "Show practical applications.",
            "Demonstrate with examples."
        ]
        example_req = random.choice(example_requests)
        return f"{prompt} {example_req}"
    
    async def _evaluate_population(
        self, 
        population: List[PromptGene], 
        fitness_function: callable
    ):
        """Evaluate fitness for all genes in the population."""
        
        tasks = []
        for gene in population:
            if gene.fitness_score == 0.0:  # Only evaluate if not already evaluated
                tasks.append(self._evaluate_gene(gene, fitness_function))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    async def _evaluate_gene(self, gene: PromptGene, fitness_function: callable):
        """Evaluate fitness for a single gene."""
        
        try:
            fitness = await fitness_function(gene.text)
            gene.fitness_score = fitness
        except Exception as e:
            logger.warning("Fitness evaluation failed", error=str(e))
            gene.fitness_score = 0.0
    
    async def _create_next_generation(
        self, 
        population: List[PromptGene], 
        generation: int
    ) -> List[PromptGene]:
        """Create the next generation through selection, crossover, and mutation."""
        
        # Sort by fitness
        population.sort(key=lambda g: g.fitness_score, reverse=True)
        
        next_generation = []
        
        # Elitism: Keep best individuals
        for i in range(self.elite_size):
            elite = population[i]
            elite_copy = PromptGene(
                text=elite.text,
                fitness_score=elite.fitness_score,
                generation=generation,
                parent_ids=elite.parent_ids.copy(),
                mutations=elite.mutations.copy()
            )
            next_generation.append(elite_copy)
        
        # Generate offspring
        while len(next_generation) < self.population_size:
            # Selection
            parent1 = self._tournament_selection(population)
            parent2 = self._tournament_selection(population)
            
            # Crossover
            if random.random() < self.crossover_rate:
                child1, child2 = await self._crossover(parent1, parent2, generation)
            else:
                child1 = self._copy_gene(parent1, generation)
                child2 = self._copy_gene(parent2, generation)
            
            # Mutation
            if random.random() < self.mutation_rate:
                child1 = await self._mutate(child1)
            if random.random() < self.mutation_rate:
                child2 = await self._mutate(child2)
            
            next_generation.extend([child1, child2])
        
        # Trim to population size
        return next_generation[:self.population_size]
    
    def _tournament_selection(self, population: List[PromptGene], tournament_size: int = 3) -> PromptGene:
        """Select a parent using tournament selection."""
        
        tournament = random.sample(population, min(tournament_size, len(population)))
        return max(tournament, key=lambda g: g.fitness_score)
    
    async def _crossover(
        self, 
        parent1: PromptGene, 
        parent2: PromptGene, 
        generation: int
    ) -> Tuple[PromptGene, PromptGene]:
        """Perform crossover between two parents."""
        
        strategy = random.choice(self.crossover_strategies)
        child1_text, child2_text = await strategy(parent1.text, parent2.text)
        
        child1 = PromptGene(
            text=child1_text,
            generation=generation,
            parent_ids=[f"gen{parent1.generation}", f"gen{parent2.generation}"]
        )
        
        child2 = PromptGene(
            text=child2_text,
            generation=generation,
            parent_ids=[f"gen{parent1.generation}", f"gen{parent2.generation}"]
        )
        
        return child1, child2
    
    async def _single_point_crossover(self, text1: str, text2: str) -> Tuple[str, str]:
        """Single point crossover."""
        
        words1 = text1.split()
        words2 = text2.split()
        
        if len(words1) <= 1 or len(words2) <= 1:
            return text1, text2
        
        point1 = random.randint(1, len(words1) - 1)
        point2 = random.randint(1, len(words2) - 1)
        
        child1 = " ".join(words1[:point1] + words2[point2:])
        child2 = " ".join(words2[:point2] + words1[point1:])
        
        return child1, child2
    
    async def _two_point_crossover(self, text1: str, text2: str) -> Tuple[str, str]:
        """Two point crossover."""
        
        words1 = text1.split()
        words2 = text2.split()
        
        if len(words1) <= 2 or len(words2) <= 2:
            return await self._single_point_crossover(text1, text2)
        
        p1_start, p1_end = sorted(random.sample(range(len(words1)), 2))
        p2_start, p2_end = sorted(random.sample(range(len(words2)), 2))
        
        child1 = " ".join(words1[:p1_start] + words2[p2_start:p2_end] + words1[p1_end:])
        child2 = " ".join(words2[:p2_start] + words1[p1_start:p1_end] + words2[p2_end:])
        
        return child1, child2
    
    async def _uniform_crossover(self, text1: str, text2: str) -> Tuple[str, str]:
        """Uniform crossover."""
        
        words1 = text1.split()
        words2 = text2.split()
        
        child1_words = []
        child2_words = []
        
        max_len = max(len(words1), len(words2))
        
        for i in range(max_len):
            if random.random() < 0.5:
                if i < len(words1):
                    child1_words.append(words1[i])
                if i < len(words2):
                    child2_words.append(words2[i])
            else:
                if i < len(words2):
                    child1_words.append(words2[i])
                if i < len(words1):
                    child2_words.append(words1[i])
        
        return " ".join(child1_words), " ".join(child2_words)
    
    async def _semantic_crossover(self, text1: str, text2: str) -> Tuple[str, str]:
        """Semantic-based crossover."""
        
        # Simple semantic crossover by combining sentences
        sentences1 = text1.split('.')
        sentences2 = text2.split('.')
        
        # Mix sentences from both parents
        all_sentences = sentences1 + sentences2
        random.shuffle(all_sentences)
        
        mid = len(all_sentences) // 2
        child1 = '. '.join(all_sentences[:mid]).strip()
        child2 = '. '.join(all_sentences[mid:]).strip()
        
        return child1, child2
    
    async def _mutate(self, gene: PromptGene) -> PromptGene:
        """Apply mutation to a gene."""
        
        strategy = random.choice(self.mutation_strategies)
        mutated_text = await strategy(gene.text)
        
        mutation_name = strategy.__name__
        gene.text = mutated_text
        gene.mutations.append(mutation_name)
        
        return gene
    
    async def _word_substitution(self, text: str) -> str:
        """Substitute random words with synonyms."""
        
        words = text.split()
        if not words:
            return text
        
        # Simple synonym mapping
        synonyms = {
            "good": "excellent",
            "bad": "poor",
            "big": "large",
            "small": "tiny",
            "fast": "quick",
            "slow": "gradual",
            "important": "crucial",
            "simple": "straightforward"
        }
        
        word_idx = random.randint(0, len(words) - 1)
        word = words[word_idx].lower()
        
        if word in synonyms:
            words[word_idx] = synonyms[word]
        
        return " ".join(words)
    
    async def _phrase_insertion(self, text: str) -> str:
        """Insert additional phrases."""
        
        phrases = [
            "please note that",
            "it's important to",
            "consider that",
            "keep in mind",
            "furthermore"
        ]
        
        phrase = random.choice(phrases)
        words = text.split()
        
        if words:
            insert_pos = random.randint(0, len(words))
            words.insert(insert_pos, phrase)
        
        return " ".join(words)
    
    async def _sentence_reordering(self, text: str) -> str:
        """Reorder sentences."""
        
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        if len(sentences) > 1:
            random.shuffle(sentences)
        
        return '. '.join(sentences)
    
    async def _style_modification(self, text: str) -> str:
        """Modify the style of the text."""
        
        style_modifiers = [
            "In a professional manner: ",
            "Clearly and concisely: ",
            "With attention to detail: ",
            "Comprehensively: ",
            "Systematically: "
        ]
        
        modifier = random.choice(style_modifiers)
        return f"{modifier}{text}"
    
    async def _length_adjustment(self, text: str) -> str:
        """Adjust the length of the text."""
        
        if random.random() < 0.5:
            # Expand
            expansions = [
                "Please provide detailed information.",
                "Include comprehensive analysis.",
                "Consider all relevant factors.",
                "Ensure thorough coverage."
            ]
            expansion = random.choice(expansions)
            return f"{text} {expansion}"
        else:
            # Contract (remove some words)
            words = text.split()
            if len(words) > 5:
                remove_count = random.randint(1, min(3, len(words) // 4))
                for _ in range(remove_count):
                    if words:
                        words.pop(random.randint(0, len(words) - 1))
            return " ".join(words)
    
    def _copy_gene(self, gene: PromptGene, generation: int) -> PromptGene:
        """Create a copy of a gene for the next generation."""
        
        return PromptGene(
            text=gene.text,
            fitness_score=0.0,  # Reset fitness for re-evaluation
            generation=generation,
            parent_ids=gene.parent_ids.copy(),
            mutations=gene.mutations.copy()
        )
    
    def _calculate_diversity(self, population: List[PromptGene]) -> float:
        """Calculate population diversity."""
        
        if len(population) <= 1:
            return 0.0
        
        # Simple diversity measure based on text length variance
        lengths = [len(gene.text.split()) for gene in population]
        mean_length = np.mean(lengths)
        variance = np.var(lengths)
        
        # Normalize diversity score
        diversity = min(variance / (mean_length + 1), 1.0)
        
        return diversity

# Global genetic optimizer instance
genetic_optimizer = GeneticOptimizer()