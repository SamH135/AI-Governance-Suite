# Reinforcement Learning Optimizer for J1 Models

This document describes the Reinforcement Learning (RL) optimizer implementation for J1 prompt generation, providing automated prompt optimization through Q-learning.

## Overview

The RL optimizer uses Q-learning to iteratively improve prompts based on feedback, learning which modifications lead to better prompt quality over time. It integrates seamlessly with the J1 service to provide intelligent prompt optimization.

## Architecture

### Core Components

1. **QLearningAgent**: Implements the Q-learning algorithm
2. **RLOptimizer**: Main optimizer class that orchestrates the optimization process
3. **State Representation**: Numerical features extracted from prompts and context
4. **Action Space**: Predefined modifications (modify, expand, simplify, rephrase)
5. **Reward System**: Feedback-based scoring for prompt quality

### Key Classes

#### RLState
Represents the current state of a prompt optimization:
```python
@dataclass
class RLState:
    prompt_features: List[float]      # Numerical prompt characteristics
    context_features: List[float]     # Context-based features
    user_feedback: float              # Quality score (0-1)
    performance_metrics: Dict         # Length, complexity, readability
    timestamp: str                    # When state was created
```

#### RLAction
Represents an optimization action:
```python
@dataclass
class RLAction:
    action_type: str                  # 'modify', 'expand', 'simplify', 'rephrase'
    parameters: Dict[str, Any]        # Action-specific parameters
    confidence: float                 # Confidence in action selection
```

#### QLearningAgent
Implements the Q-learning algorithm:
- **Epsilon-greedy exploration**: Balances exploration vs exploitation
- **Q-table**: Stores learned action values for states
- **Experience replay**: Learns from past experiences
- **Action space**: 10 predefined optimization actions

## Features

### 1. Intelligent Action Selection
- **Exploration vs Exploitation**: Uses epsilon-greedy policy
- **Adaptive Learning**: Epsilon decay reduces exploration over time
- **State Discretization**: Converts continuous features to discrete states

### 2. Diverse Action Space
- **Modify**: Adjust prompt intensity (0.1, 0.3, 0.5)
- **Expand**: Add content with length factors (1.2, 1.5)
- **Simplify**: Reduce complexity (0.8, 0.6 reduction)
- **Rephrase**: Change style (formal, casual, technical)

### 3. Feature Engineering
- **Prompt Features**: Word count, sentence count, avg word length, ratios
- **Context Features**: Complexity, formality, specificity, requirements
- **Performance Metrics**: Length, complexity, readability scores

### 4. Persistent Learning
- **Redis Integration**: Q-table persistence across sessions
- **Experience Memory**: Replay buffer for batch learning
- **Statistics Tracking**: Comprehensive optimization metrics

## API Endpoints

### 1. RL Optimization
```http
POST /api/prompts/{prompt_id}/optimize-rl
```

**Parameters:**
- `context`: Optional context dictionary
- `max_iterations`: Maximum optimization iterations (default: 15)
- `target_reward`: Target reward threshold (default: 0.85)

**Response:**
```json
{
  "success": true,
  "data": {
    "optimized_prompt": {...},
    "rl_results": {
      "final_reward": 0.87,
      "average_reward": 0.72,
      "total_iterations": 12,
      "optimization_summary": "Improved clarity and specificity",
      "convergence_achieved": true
    }
  }
}
```

### 2. RL Statistics
```http
GET /api/prompts/rl/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "rl_stats": {
      "q_table_size": 45,
      "memory_size": 120,
      "current_epsilon": 0.08,
      "learning_rate": 0.1,
      "discount_factor": 0.95
    },
    "j1_integration": {
      "model_used": "gpt-4",
      "feedback_method": "j1_evaluation",
      "optimization_available": true
    }
  }
}
```

### 3. RL Analysis
```http
GET /api/prompts/{prompt_id}/rl-analysis
```

**Response:**
```json
{
  "success": true,
  "data": {
    "optimization_results": {
      "final_reward": 0.87,
      "total_iterations": 12,
      "convergence_achieved": true
    },
    "learning_progress": [...],
    "j1_analysis": {...},
    "rl_metadata": {...}
  }
}
```

## Usage Examples

### Basic RL Optimization
```python
from services.prompts.services.rl_optimizer import rl_optimizer

# Initialize
await rl_optimizer.initialize()

# Define feedback function
async def feedback_function(prompt: str) -> float:
    # Your evaluation logic here
    return quality_score  # 0.0 to 1.0

# Optimize prompt
result = await rl_optimizer.optimize_prompt(
    initial_prompt="Write about AI",
    context={"complexity": 0.6, "formality": 0.7},
    feedback_function=feedback_function,
    max_iterations=20,
    target_reward=0.9
)

print(f"Optimized: {result['optimized_prompt']}")
print(f"Final reward: {result['final_reward']}")
```

### J1 Service Integration
```python
from services.prompts.services.j1_service import j1_service

# RL optimization with J1 evaluation
result = await j1_service.optimize_prompt_with_rl(
    initial_prompt="Explain machine learning",
    context={"target_audience": "beginners"},
    max_iterations=15,
    target_reward=0.85
)

# Access J1 analysis
j1_analysis = result["j1_analysis"]
print(f"Improvement summary: {j1_analysis['improvement_summary']}")
```

## Configuration

### RL Parameters
```python
class QLearningAgent:
    def __init__(self):
        self.learning_rate = 0.1        # Learning rate (α)
        self.discount_factor = 0.95     # Discount factor (γ)
        self.epsilon = 0.1              # Exploration rate
        self.epsilon_decay = 0.995      # Epsilon decay rate
        self.epsilon_min = 0.01         # Minimum epsilon
        self.batch_size = 32            # Experience replay batch size
```

### Action Space Configuration
The action space includes 10 predefined actions:
- 3 modify actions (different intensities)
- 2 expand actions (different length factors)
- 2 simplify actions (different reduction factors)
- 3 rephrase actions (different styles)

## Performance Considerations

### Optimization Speed
- **Typical convergence**: 10-20 iterations
- **Target reward**: 0.85 (85% quality score)
- **Feedback evaluation**: ~1-2 seconds per iteration
- **Total optimization time**: 15-40 seconds

### Memory Usage
- **Q-table**: Grows with unique states encountered
- **Experience replay**: Limited to 10,000 experiences
- **Redis caching**: 7-day TTL for Q-table persistence

### Scalability
- **Concurrent optimizations**: Supported via separate agent instances
- **State space**: Automatically managed through discretization
- **Action space**: Fixed size (10 actions) for consistent performance

## Testing

### Run Tests
```bash
# Run the test suite
python services/prompts/test_rl_optimizer.py
```

### Test Components
1. **Individual Components**: Tests Q-learning agent, states, actions
2. **Full Optimization**: End-to-end optimization test
3. **Mock Feedback**: Heuristic-based quality evaluation
4. **Statistics**: Optimizer performance metrics

### Expected Output
```
RL OPTIMIZATION RESULTS
========================================
Initial Prompt: Write a response about machine learning.
Optimized Prompt: Write a detailed response about machine learning concepts...

Optimization Metrics:
  Final Reward: 0.823
  Average Reward: 0.687
  Total Iterations: 8
  Target Achieved: False

RL Metadata:
  Final Epsilon: 0.092
  Q-table Size: 12
  Memory Size: 8
```

## Troubleshooting

### Common Issues

1. **Low Convergence Rate**
   - Increase `max_iterations`
   - Lower `target_reward`
   - Check feedback function quality

2. **Poor Optimization Results**
   - Verify feedback function logic
   - Adjust learning parameters
   - Review action space effectiveness

3. **Memory Issues**
   - Monitor Q-table growth
   - Implement state space pruning
   - Adjust experience replay buffer size

### Debug Mode
Enable detailed logging:
```python
import structlog
logger = structlog.get_logger()
logger.setLevel("DEBUG")
```

## Future Enhancements

### Planned Features
1. **Neural Network Q-function**: Replace tabular Q-learning
2. **Multi-objective Optimization**: Optimize for multiple criteria
3. **Transfer Learning**: Share knowledge across prompt types
4. **Advanced Action Space**: Dynamic action generation
5. **Distributed Training**: Multi-agent optimization

### Research Directions
1. **Deep Q-Networks (DQN)**: For continuous state spaces
2. **Policy Gradient Methods**: Direct policy optimization
3. **Meta-learning**: Learn to optimize faster
4. **Human-in-the-loop**: Interactive optimization

## Contributing

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all functions
- Add comprehensive docstrings
- Include error handling

### Testing Requirements
- Unit tests for all components
- Integration tests for full workflows
- Performance benchmarks
- Mock external dependencies

### Documentation
- Update this README for new features
- Add inline code documentation
- Provide usage examples
- Document configuration options

## License

This RL optimizer is part of the AI Compliance system and follows the same licensing terms as the main project.