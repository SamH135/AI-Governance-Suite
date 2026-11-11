"""Reinforcement Learning optimizer for J1 prompt generation."""

import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque
import random
import json
from datetime import datetime
import structlog

from services.shared.exceptions import ValidationError
from services.shared.redis_client import redis_client

logger = structlog.get_logger()

@dataclass
class RLState:
    """State representation for RL optimization."""
    prompt_features: List[float]
    context_features: List[float]
    user_feedback: float
    performance_metrics: Dict[str, float]
    timestamp: str

@dataclass
class RLAction:
    """Action representation for RL optimization."""
    action_type: str  # 'modify', 'expand', 'simplify', 'rephrase'
    parameters: Dict[str, Any]
    confidence: float

@dataclass
class RLExperience:
    """Experience tuple for RL learning."""
    state: RLState
    action: RLAction
    reward: float
    next_state: RLState
    done: bool

class QLearningAgent:
    """Q-Learning agent for prompt optimization."""
    
    def __init__(self):
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.epsilon = 0.1  # Exploration rate
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01
        
        # Q-table (simplified - in practice would use neural network)
        self.q_table = {}
        
        # Experience replay
        self.memory = deque(maxlen=10000)
        self.batch_size = 32
        
        # Action space
        self.actions = [
            {'type': 'modify', 'params': {'intensity': 0.1}},
            {'type': 'modify', 'params': {'intensity': 0.3}},
            {'type': 'modify', 'params': {'intensity': 0.5}},
            {'type': 'expand', 'params': {'length_factor': 1.2}},
            {'type': 'expand', 'params': {'length_factor': 1.5}},
            {'type': 'simplify', 'params': {'reduction_factor': 0.8}},
            {'type': 'simplify', 'params': {'reduction_factor': 0.6}},
            {'type': 'rephrase', 'params': {'style': 'formal'}},
            {'type': 'rephrase', 'params': {'style': 'casual'}},
            {'type': 'rephrase', 'params': {'style': 'technical'}}
        ]
    
    def get_state_key(self, state: RLState) -> str:
        """Convert state to string key for Q-table."""
        # Discretize continuous features for Q-table lookup
        prompt_bucket = int(np.mean(state.prompt_features) * 10)
        context_bucket = int(np.mean(state.context_features) * 10)
        feedback_bucket = int(state.user_feedback * 10)
        
        return f"{prompt_bucket}_{context_bucket}_{feedback_bucket}"
    
    def select_action(self, state: RLState) -> int:
        """Select action using epsilon-greedy policy."""
        
        if random.random() < self.epsilon:
            # Exploration: random action
            return random.randint(0, len(self.actions) - 1)
        else:
            # Exploitation: best known action
            state_key = self.get_state_key(state)
            
            if state_key not in self.q_table:
                self.q_table[state_key] = [0.0] * len(self.actions)
            
            return np.argmax(self.q_table[state_key])
    
    def update_q_value(
        self, 
        state: RLState, 
        action_idx: int, 
        reward: float, 
        next_state: RLState
    ):
        """Update Q-value using Q-learning update rule."""
        
        state_key = self.get_state_key(state)
        next_state_key = self.get_state_key(next_state)
        
        # Initialize Q-values if not exists
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0] * len(self.actions)
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = [0.0] * len(self.actions)
        
        # Q-learning update
        current_q = self.q_table[state_key][action_idx]
        max_next_q = max(self.q_table[next_state_key])
        
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_table[state_key][action_idx] = new_q
    
    def remember(self, experience: RLExperience):
        """Store experience in replay memory."""
        self.memory.append(experience)
    
    def replay_experience(self):
        """Learn from batch of experiences."""
        
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        
        for experience in batch:
            action_idx = self._get_action_index(experience.action)
            self.update_q_value(
                experience.state,
                action_idx,
                experience.reward,
                experience.next_state
            )
        
        # Decay exploration rate
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def _get_action_index(self, action: RLAction) -> int:
        """Get action index from action object."""
        for i, act in enumerate(self.actions):
            if (act['type'] == action.action_type and 
                act['params'] == action.parameters):
                return i
        return 0  # Default action

class RLOptimizer:
    """Reinforcement Learning optimizer for prompt generation."""
    
    def __init__(self):
        self.agent = QLearningAgent()
        self.session_history = []
        self.performance_tracker = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize the RL optimizer."""
        
        if self.initialized:
            return
        
        try:
            # Load existing Q-table from Redis if available
            await self._load_q_table()
            
            self.initialized = True
            logger.info("RL optimizer initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize RL optimizer", error=str(e))
            raise ValidationError(f"RL optimizer initialization failed: {str(e)}")  
  
    async def optimize_prompt(
        self,
        initial_prompt: str,
        context: Dict[str, Any],
        feedback_function: callable,
        max_iterations: int = 20,
        target_reward: float = 0.9
    ) -> Dict[str, Any]:
        """Optimize prompt using reinforcement learning."""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            logger.info("Starting RL optimization", 
                       initial_prompt=initial_prompt[:100],
                       max_iterations=max_iterations)
            
            current_prompt = initial_prompt
            optimization_history = []
            total_reward = 0.0
            
            # Initial state
            current_state = await self._create_state(
                current_prompt, context, 0.0
            )
            
            for iteration in range(max_iterations):
                # Select action
                action_idx = self.agent.select_action(current_state)
                action_config = self.agent.actions[action_idx]
                
                action = RLAction(
                    action_type=action_config['type'],
                    parameters=action_config['params'],
                    confidence=1.0 - self.agent.epsilon
                )
                
                # Apply action to prompt
                new_prompt = await self._apply_action(current_prompt, action)
                
                # Get feedback/reward
                reward = await self._calculate_reward(
                    new_prompt, current_prompt, feedback_function
                )
                
                # Create next state
                next_state = await self._create_state(
                    new_prompt, context, reward
                )
                
                # Store experience
                experience = RLExperience(
                    state=current_state,
                    action=action,
                    reward=reward,
                    next_state=next_state,
                    done=(reward >= target_reward or iteration == max_iterations - 1)
                )
                
                self.agent.remember(experience)
                
                # Update Q-values
                self.agent.update_q_value(
                    current_state, action_idx, reward, next_state
                )
                
                # Track progress
                optimization_history.append({
                    "iteration": iteration,
                    "prompt": new_prompt,
                    "action": action_config,
                    "reward": reward,
                    "epsilon": self.agent.epsilon
                })
                
                total_reward += reward
                
                logger.debug("RL iteration completed", 
                           iteration=iteration,
                           reward=reward,
                           action_type=action.action_type)
                
                # Check termination condition
                if reward >= target_reward:
                    logger.info("Target reward reached", 
                               iteration=iteration, reward=reward)
                    break
                
                # Update for next iteration
                current_prompt = new_prompt
                current_state = next_state
            
            # Experience replay
            self.agent.replay_experience()
            
            # Save Q-table
            await self._save_q_table()
            
            # Calculate final metrics
            final_reward = optimization_history[-1]["reward"] if optimization_history else 0.0
            avg_reward = total_reward / len(optimization_history) if optimization_history else 0.0
            
            result = {
                "optimized_prompt": current_prompt,
                "final_reward": final_reward,
                "average_reward": avg_reward,
                "total_iterations": len(optimization_history),
                "optimization_history": optimization_history,
                "rl_metadata": {
                    "initial_prompt": initial_prompt,
                    "final_epsilon": self.agent.epsilon,
                    "q_table_size": len(self.agent.q_table),
                    "memory_size": len(self.agent.memory),
                    "learning_rate": self.agent.learning_rate,
                    "discount_factor": self.agent.discount_factor
                }
            }
            
            logger.info("RL optimization completed", 
                       final_reward=final_reward,
                       iterations=len(optimization_history))
            
            return result
            
        except Exception as e:
            logger.error("RL optimization failed", error=str(e))
            raise ValidationError(f"RL optimization failed: {str(e)}")
    
    async def _create_state(
        self, 
        prompt: str, 
        context: Dict[str, Any], 
        feedback: float
    ) -> RLState:
        """Create state representation from prompt and context."""
        
        # Extract prompt features
        prompt_features = self._extract_prompt_features(prompt)
        
        # Extract context features
        context_features = self._extract_context_features(context)
        
        # Performance metrics
        performance_metrics = {
            "length": len(prompt.split()),
            "complexity": self._calculate_complexity(prompt),
            "readability": self._calculate_readability(prompt)
        }
        
        return RLState(
            prompt_features=prompt_features,
            context_features=context_features,
            user_feedback=feedback,
            performance_metrics=performance_metrics,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def _extract_prompt_features(self, prompt: str) -> List[float]:
        """Extract numerical features from prompt text."""
        
        words = prompt.split()
        sentences = prompt.split('.')
        
        features = [
            len(words),  # Word count
            len(sentences),  # Sentence count
            np.mean([len(word) for word in words]) if words else 0,  # Avg word length
            len([w for w in words if w.isupper()]) / len(words) if words else 0,  # Uppercase ratio
            len([w for w in words if '?' in w]) / len(words) if words else 0,  # Question ratio
            len([w for w in words if '!' in w]) / len(words) if words else 0,  # Exclamation ratio
        ]
        
        # Normalize features to [0, 1] range
        normalized_features = []
        for feature in features:
            if isinstance(feature, (int, float)):
                normalized_features.append(min(feature / 100.0, 1.0))
            else:
                normalized_features.append(0.0)
        
        return normalized_features
    
    def _extract_context_features(self, context: Dict[str, Any]) -> List[float]:
        """Extract numerical features from context."""
        
        features = [
            context.get('complexity', 0.5),
            context.get('formality', 0.5),
            context.get('specificity', 0.5),
            len(context.get('requirements', '').split()) / 100.0,
            context.get('target_audience_expertise', 0.5)
        ]
        
        return [min(max(f, 0.0), 1.0) for f in features]
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score."""
        
        words = text.split()
        if not words:
            return 0.0
        
        # Simple complexity based on word length and sentence structure
        avg_word_length = np.mean([len(word) for word in words])
        sentence_count = len(text.split('.'))
        words_per_sentence = len(words) / sentence_count if sentence_count > 0 else len(words)
        
        complexity = (avg_word_length / 10.0 + words_per_sentence / 20.0) / 2.0
        return min(complexity, 1.0)
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate readability score (simplified)."""
        
        words = text.split()
        sentences = text.split('.')
        
        if not words or not sentences:
            return 0.0
        
        # Simplified readability score
        avg_sentence_length = len(words) / len(sentences)
        avg_word_length = np.mean([len(word) for word in words])
        
        # Lower values = more readable
        readability = 1.0 - min((avg_sentence_length / 30.0 + avg_word_length / 10.0) / 2.0, 1.0)
        return readability    

    async def _apply_action(self, prompt: str, action: RLAction) -> str:
        """Apply RL action to modify the prompt."""
        
        if action.action_type == 'modify':
            return await self._modify_prompt(prompt, action.parameters)
        elif action.action_type == 'expand':
            return await self._expand_prompt(prompt, action.parameters)
        elif action.action_type == 'simplify':
            return await self._simplify_prompt(prompt, action.parameters)
        elif action.action_type == 'rephrase':
            return await self._rephrase_prompt(prompt, action.parameters)
        else:
            return prompt
    
    async def _modify_prompt(self, prompt: str, params: Dict[str, Any]) -> str:
        """Modify prompt with given intensity."""
        
        intensity = params.get('intensity', 0.1)
        words = prompt.split()
        
        # Randomly modify some words based on intensity
        num_changes = int(len(words) * intensity)
        
        for _ in range(num_changes):
            if words:
                idx = random.randint(0, len(words) - 1)
                word = words[idx]
                
                # Simple modifications
                if word.endswith('ing'):
                    words[idx] = word[:-3] + 'ed'
                elif word.endswith('ed'):
                    words[idx] = word[:-2] + 'ing'
                elif len(word) > 4:
                    # Add emphasis
                    words[idx] = f"**{word}**"
        
        return ' '.join(words)
    
    async def _expand_prompt(self, prompt: str, params: Dict[str, Any]) -> str:
        """Expand prompt by adding content."""
        
        length_factor = params.get('length_factor', 1.2)
        
        expansions = [
            "Please provide detailed information.",
            "Consider all relevant aspects.",
            "Include specific examples.",
            "Ensure comprehensive coverage.",
            "Address potential edge cases."
        ]
        
        if length_factor > 1.0:
            expansion = random.choice(expansions)
            return f"{prompt} {expansion}"
        
        return prompt
    
    async def _simplify_prompt(self, prompt: str, params: Dict[str, Any]) -> str:
        """Simplify prompt by reducing complexity."""
        
        reduction_factor = params.get('reduction_factor', 0.8)
        words = prompt.split()
        
        if reduction_factor < 1.0:
            # Remove some words
            target_length = int(len(words) * reduction_factor)
            if target_length > 0 and target_length < len(words):
                # Keep most important words (simple heuristic)
                important_words = []
                for word in words:
                    if (len(word) > 3 and 
                        word.lower() not in ['the', 'and', 'or', 'but', 'in', 'on', 'at']):
                        important_words.append(word)
                
                if len(important_words) >= target_length:
                    return ' '.join(important_words[:target_length])
        
        return prompt
    
    async def _rephrase_prompt(self, prompt: str, params: Dict[str, Any]) -> str:
        """Rephrase prompt with different style."""
        
        style = params.get('style', 'formal')
        
        if style == 'formal':
            # Make more formal
            replacements = {
                "can't": "cannot",
                "won't": "will not",
                "don't": "do not",
                "it's": "it is",
                "you're": "you are"
            }
        elif style == 'casual':
            # Make more casual
            replacements = {
                "cannot": "can't",
                "will not": "won't",
                "do not": "don't",
                "it is": "it's",
                "you are": "you're"
            }
        elif style == 'technical':
            # Make more technical
            replacements = {
                "use": "utilize",
                "help": "facilitate",
                "show": "demonstrate",
                "find": "identify",
                "make": "generate"
            }
        else:
            return prompt
        
        modified_prompt = prompt
        for old, new in replacements.items():
            modified_prompt = modified_prompt.replace(old, new)
        
        return modified_prompt
    
    async def _calculate_reward(
        self,
        new_prompt: str,
        old_prompt: str,
        feedback_function: callable
    ) -> float:
        """Calculate reward for the new prompt."""
        
        try:
            # Get feedback score for new prompt
            new_score = await feedback_function(new_prompt)
            
            # Get baseline score for comparison
            old_score = await feedback_function(old_prompt)
            
            # Reward is improvement over baseline
            improvement = new_score - old_score
            
            # Normalize reward to [-1, 1] range
            reward = np.tanh(improvement * 5)  # Scale and bound
            
            return float(reward)
            
        except Exception as e:
            logger.error("Reward calculation failed", error=str(e))
            return -0.1  # Small negative reward for errors
    
    async def _load_q_table(self):
        """Load Q-table from Redis."""
        
        try:
            q_table_data = await redis_client.get_json("rl_optimizer:q_table")
            if q_table_data:
                self.agent.q_table = q_table_data
                logger.info("Q-table loaded from cache", size=len(self.agent.q_table))
        except Exception as e:
            logger.warning("Failed to load Q-table from cache", error=str(e))
    
    async def _save_q_table(self):
        """Save Q-table to Redis."""
        
        try:
            await redis_client.set_json(
                "rl_optimizer:q_table", 
                self.agent.q_table, 
                ttl=86400 * 7  # 7 days
            )
            logger.debug("Q-table saved to cache", size=len(self.agent.q_table))
        except Exception as e:
            logger.warning("Failed to save Q-table to cache", error=str(e))
    
    async def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        
        return {
            "q_table_size": len(self.agent.q_table),
            "memory_size": len(self.agent.memory),
            "current_epsilon": self.agent.epsilon,
            "learning_rate": self.agent.learning_rate,
            "discount_factor": self.agent.discount_factor,
            "action_space_size": len(self.agent.actions),
            "session_history_length": len(self.session_history)
        }

# Global RL optimizer instance
rl_optimizer = RLOptimizer()