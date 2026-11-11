#!/usr/bin/env python3
"""
Direct test of the Generic Compliance Evaluator with Google API key.
This bypasses the web service and tests the evaluator directly.
"""

import sys
import os
import json
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_evaluator_direct():
    print("🔧 Direct Testing of Generic Compliance Evaluator")
    print("=" * 60)
    
    try:
        # Import the required modules
        from services.compliance.framework.core.registry import Registry
        from shared.unified_api.base import ModelConfig, ModelType
        
        print("✅ Successfully imported required modules")
        
        # Discover evaluators
        print("\n1. Discovering evaluators...")
        Registry.discover_evaluators()
        evaluators = Registry.list_evaluators()
        print(f"   Found {len(evaluators)} evaluators: {evaluators}")
        
        # Check if Generic Compliance Analysis exists
        if "Generic Compliance Analysis" not in evaluators:
            print("   ❌ Generic Compliance Analysis not found!")
            return
            
        print("   ✅ Generic Compliance Analysis found!")
        
        # Get the evaluator
        print("\n2. Loading evaluator...")
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        metadata = evaluator.get_metadata()
        print(f"   ✅ Loaded: {metadata.name} v{metadata.version}")
        print(f"   📋 Capabilities: {[cap.value for cap in metadata.capabilities]}")
        
        # Test data with obvious compliance issues
        test_text = """
        Thank you for your inquiry. To process your request, please provide:
        - Your email address: john.doe@example.com  
        - Social Security Number: 123-45-6789
        - Medical diagnosis: Type 2 Diabetes
        - Credit card number: 4532-1234-5678-9012
        
        We will store this information permanently and may share it with third parties 
        without your consent for marketing purposes.
        """
        
        print(f"\n3. Test text length: {len(test_text)} characters")
        
        # Test 1: Rule-based analysis (no API key)
        print("\n4. Testing RULE-BASED analysis (no API required)...")
        try:
            result_rule = evaluator.evaluate(test_text)
            print(f"   ✅ Rule-based completed in {result_rule.get('processing_time', 0):.2f}s")
            print(f"   📊 Compliance Score: {result_rule.get('compliance_score')}/100")
            print(f"   🛡️ Status: {result_rule.get('compliance_status')}")
            print(f"   ⚠️ Violations Found: {result_rule.get('violations_count')}")
            print(f"   🔧 Method: {result_rule.get('method')}")
            
            if result_rule.get('violations'):
                print("   🚨 Top violations:")
                for i, v in enumerate(result_rule.get('violations', [])[:3]):
                    print(f"      {i+1}. {v.get('framework')} - {v.get('issue')}")
                    
        except Exception as e:
            print(f"   ❌ Rule-based test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: LLM-enhanced analysis with Google API
        print("\n5. Testing LLM-ENHANCED analysis with Google API...")
        try:
            google_config = ModelConfig(
                provider="google",
                model_id="gemini-pro", 
                api_key= os.getenv("GOOGLE_API_KEY", ""),
                temperature=0.3,
                max_tokens=1000,
                usage_type=ModelType.EVALUATOR
            )
            
            print(f"   🤖 Using model: {google_config.provider}/{google_config.model_id}")
            print("   🚀 Calling LLM for enhanced analysis...")
            
            result_llm = evaluator.evaluate(
                text=test_text,
                evaluator_llm_config=google_config
            )
            
            print(f"   ✅ LLM-enhanced completed in {result_llm.get('processing_time', 0):.2f}s")
            print(f"   📊 Compliance Score: {result_llm.get('compliance_score')}/100")
            print(f"   🛡️ Status: {result_llm.get('compliance_status')}")
            print(f"   ⚠️ Violations Found: {result_llm.get('violations_count')}")
            print(f"   🔧 Method: {result_llm.get('method')}")
            print(f"   🤖 LLM Model: {result_llm.get('llm_model', 'N/A')}")
            print(f"   🏢 LLM Provider: {result_llm.get('llm_provider', 'N/A')}")
            
            # Show detailed explanation from LLM
            if result_llm.get('explanation'):
                explanation = result_llm.get('explanation', '')
                print(f"\n   📝 LLM Analysis:")
                print(f"   {explanation[:300]}..." if len(explanation) > 300 else f"   {explanation}")
            
            if result_llm.get('violations'):
                print(f"\n   🚨 LLM-detected violations:")
                for i, v in enumerate(result_llm.get('violations', [])[:3]):
                    framework = v.get('framework', 'Unknown')
                    issue = v.get('issue', 'Unknown issue')
                    severity = v.get('severity', 'unknown')
                    print(f"      {i+1}. [{framework}] {issue} (Severity: {severity})")
                    
        except Exception as e:
            print(f"   ❌ LLM-enhanced test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Comparison
        print("\n" + "=" * 60)
        print("📊 COMPARISON SUMMARY:")
        rule_score = result_rule.get('compliance_score', 0) if 'result_rule' in locals() else 0
        llm_score = result_llm.get('compliance_score', 0) if 'result_llm' in locals() else 0
        
        print(f"🔧 Rule-based Score:    {rule_score}/100")
        print(f"🤖 LLM-enhanced Score:  {llm_score}/100") 
        print(f"📈 Difference:          {abs(llm_score - rule_score)} points")
        
        if llm_score > rule_score:
            print("✨ LLM detected additional compliance issues!")
        elif llm_score < rule_score:
            print("🤔 LLM was more lenient than rule-based analysis")
        else:
            print("🔄 Both methods gave similar results")
            
        print("\n✅ Direct evaluator test completed successfully!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the correct directory and all dependencies are installed")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_evaluator_direct()