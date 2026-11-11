#!/usr/bin/env python3
"""
Direct test script for the Generic Compliance Evaluator.
This script tests the evaluator functionality without going through the API.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services"))
sys.path.insert(0, str(project_root / "shared"))

def test_evaluator_basic():
    """Test the evaluator with basic text (no LLM required)."""
    print("=== Testing Generic Compliance Evaluator (Basic) ===")
    
    try:
        # Import the evaluator
        from services.compliance.framework.core.registry import Registry
        
        # Discover evaluators
        Registry.discover_evaluators()
        
        # List available evaluators
        evaluators = Registry.list_evaluators()
        print(f"Available evaluators: {evaluators}")
        
        if "Generic Compliance Analysis" not in evaluators:
            print("ERROR: Generic Compliance Analysis evaluator not found!")
            return False
        
        # Get the evaluator
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        print(f"Successfully loaded evaluator: {evaluator.__class__.__name__}")
        
        # Test text that should trigger some compliance issues
        test_text = """
        This AI system makes decisions based on user demographics. 
        We collect personal information including race, gender, and financial status.
        The system automatically rejects applications from certain zip codes.
        User data is shared with third parties without explicit consent.
        """
        
        print(f"\nTesting with text ({len(test_text)} chars):")
        print(test_text[:100] + "..." if len(test_text) > 100 else test_text)
        
        # Run evaluation
        result = evaluator.evaluate(test_text)
        
        print(f"\nEvaluation completed!")
        print(f"Results:")
        print(json.dumps(result, indent=2))
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_evaluator_with_llm():
    """Test the evaluator with LLM configuration."""
    print("\n=== Testing Generic Compliance Evaluator (With LLM) ===")
    
    try:
        # Import necessary modules
        from services.compliance.framework.core.registry import Registry
        from shared.unified_api.base import ModelConfig, ModelType
        
        # Get the evaluator
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        
        # Create LLM configuration
        # For alpha testing, use local provider with pre-determined responses
        # Replace with actual API key for production testing
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if api_key:
            llm_config = ModelConfig(
                provider="google",
                model_id="gemini-pro", 
                api_key=api_key,
                temperature=0.3,
                max_tokens=1000,
                usage_type=ModelType.EVALUATOR
            )
        else:
            print("WARNING: No GOOGLE_API_KEY found, using local provider for testing")
            llm_config = ModelConfig(
                provider="local",
                model_id="local-mock",
                usage_type=ModelType.EVALUATOR
            )
        
        # Test text
        test_text = """
        Our AI hiring system uses machine learning to screen candidates.
        It automatically filters resumes based on university rankings and previous company prestige.
        The system has been trained on historical hiring data from the past 20 years.
        """
        
        print(f"Testing with LLM-enhanced analysis:")
        print(test_text)
        
        # Run evaluation with LLM
        result = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=llm_config
        )
        
        print(f"\nLLM-enhanced evaluation completed!")
        print(f"Results:")
        print(json.dumps(result, indent=2))
        
        return True
        
    except Exception as e:
        print(f"Error with LLM test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_evaluator_metadata():
    """Test evaluator metadata and capabilities."""
    print("\n=== Testing Evaluator Metadata ===")
    
    try:
        from services.compliance.framework.evaluators.generic_compliance.evaluator import GenericComplianceEvaluator
        
        # Get metadata
        metadata = GenericComplianceEvaluator.get_metadata()
        
        print(f"Evaluator Metadata:")
        print(f"  Name: {metadata.name}")
        print(f"  Description: {metadata.description}")
        print(f"  Version: {metadata.version}")
        print(f"  Category: {metadata.category}")
        print(f"  Tags: {metadata.tags}")
        print(f"  Capabilities: {[cap.value for cap in metadata.capabilities]}")
        print(f"  LLM Requirements: {metadata.llm_requirements.requirement_level.value}")
        print(f"  RAG Requirements: {metadata.rag_requirements.requirement_level.value}")
        print(f"  Fallback Mode: {metadata.fallback_mode}")
        print(f"  Runtime: {metadata.estimated_runtime}")
        
        return True
        
    except Exception as e:
        print(f"Error getting metadata: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting Generic Compliance Evaluator Tests")
    print("=" * 60)
    
    # Test metadata first
    metadata_success = test_evaluator_metadata()
    
    # Test basic functionality
    basic_success = test_evaluator_basic()
    
    # Test with LLM (this might fail if API key is invalid, but that's OK)
    llm_success = test_evaluator_with_llm()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"  Metadata Test: {'PASS' if metadata_success else 'FAIL'}")
    print(f"  Basic Test: {'PASS' if basic_success else 'FAIL'}")
    print(f"  LLM Test: {'PASS' if llm_success else 'FAIL'}")
    
    if basic_success:
        print("\nGeneric Compliance Evaluator is working!")
    else:
        print("\n💥 Generic Compliance Evaluator has issues.")
        sys.exit(1)