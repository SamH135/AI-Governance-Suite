#!/usr/bin/env python3
"""
Test script for the Generic Compliance Evaluator with Google API key.
"""

import sys
import os
sys.path.append('../../')

from services.compliance.framework.core.registry import Registry
from shared.unified_api.base import ModelConfig, ModelType

def test_compliance_evaluator():
    print("Testing Compliance Evaluator with Google API")
    print("=" * 60)
    
    try:
        # Discover evaluators
        print("1. Discovering evaluators...")
        Registry.discover_evaluators()
        evaluators = Registry.list_evaluators()
        print(f"   Found {len(evaluators)} evaluators: {evaluators}")
        
        # Get the Generic Compliance evaluator
        print("\n2. Loading Generic Compliance evaluator...")
        if "Generic Compliance Analysis" not in evaluators:
            print("   ERROR: Generic Compliance Analysis not found!")
            return False
            
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        metadata = evaluator.get_metadata()
        print(f"   Loaded: {metadata.name} v{metadata.version}")
        print(f"   Capabilities: {[cap.value for cap in metadata.capabilities]}")
        
        # Test rule-based analysis first (no API key needed)
        print("\n3. Testing rule-based analysis (no API key)...")
        test_text = "Please provide your email address john@example.com and social security number 123-45-6789 for verification."
        
        result_rule = evaluator.evaluate(test_text)
        print(f"   Rule-based analysis completed")
        print(f"   Compliance Score: {result_rule.get('compliance_score')}/100")
        print(f"   Status: {result_rule.get('compliance_status')}")
        print(f"   Violations: {result_rule.get('violations_count')}")
        print(f"   Method: {result_rule.get('method')}")
        
        # Test LLM-enhanced analysis with Google API
        print("\n4. Testing LLM-enhanced analysis with Google API...")
        # For alpha testing, use local provider with pre-determined responses
        # Replace with actual API key for production testing
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if api_key:
            google_config = ModelConfig(
                provider="google",
                model_id="gemini-pro",
                api_key=api_key,
                temperature=0.3,
                max_tokens=1000,
                usage_type=ModelType.EVALUATOR
            )
        else:
            print("   No GOOGLE_API_KEY found, using local provider for testing")
            google_config = ModelConfig(
                provider="local",
                model_id="local-mock",
                usage_type=ModelType.EVALUATOR
            )
        
        result_llm = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=google_config
        )
        
        print(f"   LLM-enhanced analysis completed")
        print(f"   Compliance Score: {result_llm.get('compliance_score')}/100")
        print(f"   Status: {result_llm.get('compliance_status')}")
        print(f"   Violations: {result_llm.get('violations_count')}")
        print(f"   Method: {result_llm.get('method')}")
        print(f"   LLM Model: {result_llm.get('llm_model', 'N/A')}")
        print(f"   Processing Time: {result_llm.get('processing_time', 0):.2f}s")
        
        # Show detailed analysis
        if result_llm.get('explanation'):
            print(f"\n   LLM Analysis Summary:")
            print(f"   {result_llm.get('explanation', 'No explanation provided')[:200]}...")
            
        if result_llm.get('violations'):
            print(f"\n   Violations Found:")
            for i, violation in enumerate(result_llm.get('violations', [])[:3]):
                print(f"      {i+1}. {violation.get('framework', 'Unknown')} - {violation.get('issue', 'Unknown issue')}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print(f"Rule-based score: {result_rule.get('compliance_score')}")  
        print(f"LLM-enhanced score: {result_llm.get('compliance_score')}")
        print(f"Improvement: {abs(result_llm.get('compliance_score', 0) - result_rule.get('compliance_score', 0)):.1f} points")
        
        return True
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_compliance_evaluator()