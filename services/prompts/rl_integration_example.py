#!/usr/bin/env python3
"""
Integration example showing how to use the RL optimizer with the J1 service.
This demonstrates the complete workflow from prompt generation to RL optimization.
"""

import asyncio
import json
import os
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

class RLIntegrationDemo:
    """Demonstration of RL optimizer integration with J1 service."""
    
    def __init__(self):
        self.j1_service = None
        self.rl_optimizer = None
    
    async def initialize(self):
        """Initialize services."""
        try:
            # Import services
            from services.j1_service import j1_service
            from services.rl_optimizer import rl_optimizer
            
            self.j1_service = j1_service
            self.rl_optimizer = rl_optimizer
            
            # Initialize services
            await self.j1_service.initialize()
            await self.rl_optimizer.initialize()
            
            logger.info("Services initialized successfully")
            
        except Exception as e:
            logger.error("Service initialization failed", error=str(e))
            raise
    
    async def demonstrate_workflow(self):
        """Demonstrate the complete RL optimization workflow."""
        
        print("\n" + "="*80)
        print("RL OPTIMIZER INTEGRATION DEMONSTRATION")
        print("="*80)
        
        # Step 1: Generate initial prompt using J1
        print("\n1. GENERATING INITIAL PROMPT WITH J1")
        print("-" * 40)
        
        requirements = """
        Create a prompt that helps users write effective technical documentation.
        The prompt should guide them through structure, clarity, and completeness.
        Target audience: Software developers and technical writers.
        """
        
        initial_prompts = await self.j1_service.generate_prompts(
            requirements=requirements,
            category="technical_writing",
            count=1,
            system_context="Documentation assistant system"
        )
        
        initial_prompt = initial_prompts[0]["text"]
        print(f"Generated prompt: {initial_prompt[:200]}...")
        print(f"Initial quality score: {initial_prompts[0]['quality_score']:.3f}")
        
        # Step 2: Prepare context for RL optimization
        print("\n2. PREPARING RL OPTIMIZATION CONTEXT")
        print("-" * 40)
        
        rl_context = {
            "complexity": 0.7,  # Technical content
            "formality": 0.8,   # Professional tone
            "specificity": 0.9, # Very specific requirements
            "requirements": requirements,
            "target_audience_expertise": 0.7,  # Experienced developers
            "domain": "technical_writing",
            "optimization_goals": [
                "improve_clarity",
                "enhance_structure", 
                "increase_actionability"
            ]
        }
        
        print(f"Context prepared with {len(rl_context)} parameters")
        
        # Step 3: Run RL optimization
        print("\n3. RUNNING RL OPTIMIZATION")
        print("-" * 40)
        
        optimization_result = await self.j1_service.optimize_prompt_with_rl(
            initial_prompt=initial_prompt,
            context=rl_context,
            max_iterations=12,
            target_reward=0.85
        )
        
        # Display results
        print(f"\nOptimization completed!")
        print(f"Final reward: {optimization_result['final_reward']:.3f}")
        print(f"Average reward: {optimization_result['average_reward']:.3f}")
        print(f"Total iterations: {optimization_result['total_iterations']}")
        print(f"Target achieved: {optimization_result['final_reward'] >= 0.85}")
        
        # Step 4: Analyze optimization process
        print("\n4. OPTIMIZATION ANALYSIS")
        print("-" * 40)
        
        j1_analysis = optimization_result.get("j1_analysis", {})
        if j1_analysis:
            print(f"\nImprovement Summary:")
            print(f"  {j1_analysis.get('improvement_summary', 'No summary available')}")
            
            quality_comparison = j1_analysis.get("quality_comparison", {})
            if quality_comparison:
                print(f"\nQuality Comparison:")
                print(f"  Initial: {quality_comparison.get('initial_quality', 'N/A')}")
                print(f"  Final: {quality_comparison.get('final_quality', 'N/A')}")
                
                improvements = quality_comparison.get("improvement_areas", [])
                if improvements:
                    print(f"  Improvements: {', '.join(improvements)}")
            
            rl_effectiveness = j1_analysis.get("rl_effectiveness", {})
            if rl_effectiveness:
                print(f"\nRL Process Analysis:")
                print(f"  Convergence: {rl_effectiveness.get('convergence_analysis', 'N/A')}")
                print(f"  Best actions: {rl_effectiveness.get('action_effectiveness', 'N/A')}")
        
        # Step 5: Show learning progress
        print("\n5. LEARNING PROGRESS")
        print("-" * 40)
        
        history = optimization_result.get("optimization_history", [])
        if history:
            print(f"\nOptimization trajectory (last 5 iterations):")
            for item in history[-5:]:
                iteration = item.get("iteration", 0)
                reward = item.get("reward", 0)
                action = item.get("action", {})
                action_type = action.get("type", "unknown")
                epsilon = item.get("epsilon", 0)
                
                print(f"  Iter {iteration:2d}: {action_type:10s} -> "
                      f"reward: {reward:6.3f}, ε: {epsilon:.3f}")
        
        # Step 6: Compare prompts
        print("\n6. PROMPT COMPARISON")
        print("-" * 40)
        
        optimized_prompt = optimization_result["optimized_prompt"]
        
        print(f"\nORIGINAL PROMPT:")
        print(f"  Length: {len(initial_prompt.split())} words")
        print(f"  Text: {initial_prompt}")
        
        print(f"\nOPTIMIZED PROMPT:")
        print(f"  Length: {len(optimized_prompt.split())} words")
        print(f"  Text: {optimized_prompt}")
        
        # Step 7: Get RL statistics
        print("\n7. RL OPTIMIZER STATISTICS")
        print("-" * 40)
        
        stats = await self.j1_service.get_rl_optimization_stats()
        rl_stats = stats.get("rl_stats", {})
        
        print(f"\nCurrent RL State:")
        print(f"  Q-table size: {rl_stats.get('q_table_size', 0)}")
        print(f"  Memory size: {rl_stats.get('memory_size', 0)}")
        print(f"  Current epsilon: {rl_stats.get('current_epsilon', 0):.3f}")
        print(f"  Learning rate: {rl_stats.get('learning_rate', 0)}")
        print(f"  Action space size: {rl_stats.get('action_space_size', 0)}")
        
        return optimization_result
    
    async def demonstrate_batch_optimization(self):
        """Demonstrate optimizing multiple prompts to show learning."""
        
        print("\n" + "="*80)
        print("BATCH OPTIMIZATION DEMONSTRATION")
        print("="*80)
        
        test_prompts = [
            "Write a guide about Python programming.",
            "Explain machine learning concepts.",
            "Create documentation for an API.",
            "Describe software testing best practices."
        ]
        
        results = []
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\n{i}. OPTIMIZING PROMPT: {prompt}")
            print("-" * 60)
            
            context = {
                "complexity": 0.6 + (i * 0.1),  # Increasing complexity
                "formality": 0.7,
                "specificity": 0.8,
                "requirements": f"Create comprehensive content about: {prompt}",
                "target_audience_expertise": 0.5
            }
            
            result = await self.j1_service.optimize_prompt_with_rl(
                initial_prompt=prompt,
                context=context,
                max_iterations=8,  # Fewer iterations for batch demo
                target_reward=0.8
            )
            
            results.append(result)
            
            print(f"  Final reward: {result['final_reward']:.3f}")
            print(f"  Iterations: {result['total_iterations']}")
            print(f"  Optimized: {result['optimized_prompt'][:100]}...")
        
        # Show learning progression
        print(f"\nLEARNING PROGRESSION:")
        print("-" * 40)
        
        for i, result in enumerate(results, 1):
            final_reward = result['final_reward']
            iterations = result['total_iterations']
            print(f"  Prompt {i}: {final_reward:.3f} reward in {iterations} iterations")
        
        # Final statistics
        final_stats = await self.j1_service.get_rl_optimization_stats()
        rl_stats = final_stats.get("rl_stats", {})
        
        print(f"\nFINAL RL STATE:")
        print(f"  Q-table size: {rl_stats.get('q_table_size', 0)} (learned states)")
        print(f"  Memory size: {rl_stats.get('memory_size', 0)} (experiences)")
        print(f"  Final epsilon: {rl_stats.get('current_epsilon', 0):.3f} (exploration rate)")
        
        return results
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.j1_service:
                await self.j1_service.close()
            logger.info("Services cleaned up")
        except Exception as e:
            logger.error("Cleanup failed", error=str(e))

async def main():
    """Main demonstration function."""
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable is required")
        print("Please set your OpenAI API key to run this demonstration")
        return 1
    
    demo = RLIntegrationDemo()
    
    try:
        # Initialize services
        await demo.initialize()
        
        # Run single optimization demonstration
        await demo.demonstrate_workflow()
        
        # Run batch optimization demonstration
        await demo.demonstrate_batch_optimization()
        
        print("\n" + "="*80)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nKey takeaways:")
        print("1. RL optimizer learns from feedback to improve prompts")
        print("2. Q-learning adapts action selection based on experience")
        print("3. J1 service provides intelligent evaluation and analysis")
        print("4. System maintains learning state across optimizations")
        print("5. Integration provides comprehensive optimization workflow")
        
        return 0
        
    except Exception as e:
        logger.error("Demonstration failed", error=str(e))
        print(f"\nDEMONSTRATION FAILED: {str(e)}")
        return 1
        
    finally:
        await demo.cleanup()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)