#!/usr/bin/env python3
"""Test script for the RL optimizer functionality."""

import asyncio
import json
from typing import Dict, Any
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

async def mock_feedback_function(prompt: str) -> float:
    """Mock feedback function that evaluates prompt quality."""
    
    # Simple heuristic-based scoring
    score = 0.5  # Base score
    
    # Length bonus
    words = prompt.split()
    if len(words) > 10:
        score += 0.1
    if len(words) > 20:
        score += 0.1
    
    # Structure bonus
    if ":" in prompt:
        score += 0.1
    if any(word in prompt.lower() for word in ["please", "ensure", "provide"]):
        score += 0.1
    
    # Specificity bonus
    if any(word in prompt.lower() for word in ["specific", "detailed", "clear"]):
        score += 0.1
    
    # Complexity penalty for overly long prompts
    if len(words) > 50:
        score -= 0.1
    
    # Add some randomness to simulate real feedback
    import random
    score += random.uniform(-0.05, 0.05)
    
    return max(0.0, min(1.0, score))

async def test_rl_optimizer():
    """Test the RL optimizer with a sample prompt."""
    
    try:
        # Import the RL optimizer
        from services.rl_optimizer import rl_optimizer
        
        logger.info("Starting RL optimizer test")
        
        # Initialize the optimizer
        await rl_optimizer.initialize()
        
        # Test prompt
        initial_prompt = "Write a response about machine learning."
        
        # Test context
        context = {
            "complexity": 0.6,
            "formality": 0.7,
            "specificity": 0.5,
            "requirements": "Create a comprehensive guide about machine learning concepts",
            "target_audience_expertise": 0.4
        }
        
        logger.info("Running RL optimization", 
                   initial_prompt=initial_prompt,
                   context=context)
        
        # Run optimization
        result = await rl_optimizer.optimize_prompt(
            initial_prompt=initial_prompt,
            context=context,
            feedback_function=mock_feedback_function,
            max_iterations=10,
            target_reward=0.8
        )
        
        # Display results
        print("\n" + "="*60)
        print("RL OPTIMIZATION RESULTS")
        print("="*60)
        
        print(f"\nInitial Prompt:")
        print(f"  {initial_prompt}")
        
        print(f"\nOptimized Prompt:")
        print(f"  {result['optimized_prompt']}")
        
        print(f"\nOptimization Metrics:")
        print(f"  Final Reward: {result['final_reward']:.3f}")
        print(f"  Average Reward: {result['average_reward']:.3f}")
        print(f"  Total Iterations: {result['total_iterations']}")
        print(f"  Target Achieved: {result['final_reward'] >= 0.8}")
        
        print(f"\nRL Metadata:")
        rl_meta = result['rl_metadata']
        print(f"  Final Epsilon: {rl_meta['final_epsilon']:.3f}")
        print(f"  Q-table Size: {rl_meta['q_table_size']}")
        print(f"  Memory Size: {rl_meta['memory_size']}")
        print(f"  Learning Rate: {rl_meta['learning_rate']}")
        
        print(f"\nOptimization History (last 5 iterations):")
        history = result['optimization_history'][-5:]
        for item in history:
            action_type = item['action']['type']
            reward = item['reward']
            epsilon = item['epsilon']
            print(f"  Iteration {item['iteration']}: {action_type} -> reward: {reward:.3f}, ε: {epsilon:.3f}")
        
        # Test statistics
        print(f"\nOptimizer Statistics:")
        stats = await rl_optimizer.get_optimization_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n" + "="*60)
        print("TEST COMPLETED SUCCESSFULLY")
        print("="*60)
        
        return result
        
    except Exception as e:
        logger.error("RL optimizer test failed", error=str(e))
        print(f"\nERROR: {str(e)}")
        raise

async def test_individual_components():
    """Test individual components of the RL optimizer."""
    
    try:
        from services.rl_optimizer import QLearningAgent, RLState, RLAction
        
        print("\n" + "="*60)
        print("TESTING INDIVIDUAL COMPONENTS")
        print("="*60)
        
        # Test Q-Learning Agent
        agent = QLearningAgent()
        
        # Create test state
        test_state = RLState(
            prompt_features=[0.5, 0.3, 0.7, 0.2, 0.1, 0.0],
            context_features=[0.6, 0.7, 0.5, 0.4, 0.4],
            user_feedback=0.6,
            performance_metrics={"length": 15, "complexity": 0.5, "readability": 0.7},
            timestamp="2024-01-01T00:00:00Z"
        )
        
        print(f"\nTest State:")
        print(f"  Prompt Features: {test_state.prompt_features}")
        print(f"  Context Features: {test_state.context_features}")
        print(f"  User Feedback: {test_state.user_feedback}")
        
        # Test action selection
        action_idx = agent.select_action(test_state)
        selected_action = agent.actions[action_idx]
        
        print(f"\nSelected Action:")
        print(f"  Index: {action_idx}")
        print(f"  Type: {selected_action['type']}")
        print(f"  Parameters: {selected_action['params']}")
        print(f"  Current Epsilon: {agent.epsilon}")
        
        # Test state key generation
        state_key = agent.get_state_key(test_state)
        print(f"\nState Key: {state_key}")
        
        # Test Q-value update
        next_state = RLState(
            prompt_features=[0.6, 0.4, 0.8, 0.3, 0.1, 0.0],
            context_features=[0.6, 0.7, 0.5, 0.4, 0.4],
            user_feedback=0.7,
            performance_metrics={"length": 18, "complexity": 0.6, "readability": 0.8},
            timestamp="2024-01-01T00:01:00Z"
        )
        
        reward = 0.1  # Positive reward for improvement
        agent.update_q_value(test_state, action_idx, reward, next_state)
        
        print(f"\nQ-value Updated:")
        print(f"  Reward: {reward}")
        print(f"  Q-table size: {len(agent.q_table)}")
        
        if state_key in agent.q_table:
            print(f"  Q-values for state: {agent.q_table[state_key]}")
        
        print("\n" + "="*60)
        print("COMPONENT TESTS COMPLETED")
        print("="*60)
        
    except Exception as e:
        logger.error("Component test failed", error=str(e))
        print(f"\nERROR: {str(e)}")
        raise

async def main():
    """Main test function."""
    
    print("RL Optimizer Test Suite")
    print("=" * 60)
    
    try:
        # Test individual components first
        await test_individual_components()
        
        # Test full RL optimization
        await test_rl_optimizer()
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest suite failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)