#!/usr/bin/env python3
"""
Test the fixed unified API imports in the Generic Compliance Evaluator.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services"))
sys.path.insert(0, str(project_root / "shared"))

def test_fixed_imports():
    """Test that the fixed imports work correctly."""
    print("🔧 Testing Fixed Unified API Imports")
    print("=" * 60)
    
    try:
        # Test importing the unified API directly
        print("📦 Testing unified API imports...")
        from shared.unified_api.base import ModelConfig, ModelType
        from shared.unified_api import get_unified_api
        print("✅ Unified API imports successful")
        
        # Test that we can create the API instance
        print("🚀 Creating unified API instance...")
        api = get_unified_api()
        print(f"✅ Unified API created: {type(api)}")
        
        # List providers
        providers = api.list_providers()
        print(f"📋 Available providers: {providers}")
        
        # Test evaluator imports
        print("🧪 Testing evaluator imports...")
        from services.compliance.framework.core.registry import Registry
        Registry.discover_evaluators()
        
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        print(f"✅ Evaluator loaded: {type(evaluator)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_with_fixed_imports():
    """Test LLM functionality with the fixed imports."""
    print(f"\n🤖 Testing LLM Functionality with Fixed Imports")
    print("=" * 60)
    
    try:
        # Import everything we need
        from shared.unified_api.base import ModelConfig, ModelType
        from services.compliance.framework.core.registry import Registry
        
        # Get evaluator
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        
        # Create proper LLM config
        llm_config = ModelConfig(
            provider="google",
            model_id="gemini-1.5-flash",  # Use the newer model name
            api_key= os.getenv("GOOGLE_API_KEY", ""),
            temperature=0.3,
            max_tokens=1000,
            usage_type=ModelType.EVALUATOR
        )
        
        # Test text with clear compliance issues
        test_text = """
        Our loan approval system automatically analyzes applications using demographics like race, gender, and zip code.
        We store customer social security numbers in plain text files for easy access.
        Personal health information is shared with marketing teams without patient consent.
        The system makes decisions affecting people's financial future based on historical patterns that may contain bias.
        """
        
        print(f"📝 Testing with text ({len(test_text)} chars):")
        print(test_text.strip()[:200] + "..." if len(test_text.strip()) > 200 else test_text.strip())
        
        print(f"\n🚀 Running LLM-enhanced evaluation...")
        print(f"Provider: {llm_config.provider}")
        print(f"Model: {llm_config.model_id}")
        
        # Run the evaluation
        result = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=llm_config
        )
        
        print(f"\n✅ Evaluation completed!")
        print(f"📊 Results:")
        print(f"  Method: {result.get('method', 'unknown')}")
        print(f"  Score: {result.get('compliance_score', 'N/A')}")
        print(f"  Status: {result.get('compliance_status', 'N/A')}")
        print(f"  Violations: {len(result.get('violations', []))}")
        print(f"  Processing Time: {result.get('processing_time', 'N/A'):.4f}s")
        
        # Check if LLM was actually used
        method_used = result.get('method', 'unknown')
        if 'llm' in method_used.lower() or 'enhanced' in method_used.lower():
            print(f"\n🎉 SUCCESS: LLM was used for analysis!")
            
            # Show detailed results
            print(f"\n📋 Detailed Results:")
            print(json.dumps(result, indent=2)[:1000] + "..." if len(json.dumps(result, indent=2)) > 1000 else json.dumps(result, indent=2))
            
            return True
        else:
            print(f"\n⚠️  LLM was not used, method: {method_used}")
            if 'fallback_reason' in result:
                print(f"Fallback reason: {result['fallback_reason']}")
            return False
        
    except Exception as e:
        print(f"❌ LLM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_google_api_directly():
    """Test Google API directly to verify the key works."""
    print(f"\n🌐 Testing Google API Directly")
    print("=" * 60)
    
    try:
        from shared.unified_api import get_unified_api
        from shared.unified_api.base import ModelConfig, ModelType
        
        api = get_unified_api()
        
        # Create config for Google
        config = ModelConfig(
            provider="google",
            model_id="gemini-1.5-flash",  # Try the newer model
            api_key= os.getenv("GOOGLE_API_KEY", ""),
            temperature=0.3,
            max_tokens=500,
            usage_type=ModelType.EVALUATOR
        )
        
        # Simple test prompt
        prompt = "Analyze this text for compliance issues: 'We collect user data without consent and share it with third parties.'"
        
        print(f"🔗 Making API call...")
        print(f"Provider: {config.provider}")
        print(f"Model: {config.model_id}")
        
        response = api.generate(prompt, config)
        
        print(f"✅ API call successful!")
        print(f"📝 Response:")
        print(f"  Text: {response.text[:200]}...")
        print(f"  Provider: {response.provider}")
        print(f"  Model: {response.model}")
        print(f"  Usage: {response.usage}")
        
        return True
        
    except Exception as e:
        print(f"❌ Direct API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Testing Fixed Unified API Integration")
    print("=" * 60)
    
    # Test imports first
    imports_success = test_fixed_imports()
    
    # Test direct API call
    api_success = test_google_api_directly()
    
    # Test LLM functionality if imports work
    llm_success = False
    if imports_success:
        llm_success = test_llm_with_fixed_imports()
    
    print("\n" + "=" * 60)
    print("📈 Test Summary:")
    print(f"  Imports Test: {'✅ PASS' if imports_success else '❌ FAIL'}")
    print(f"  Direct API Test: {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"  LLM Enhancement Test: {'✅ PASS' if llm_success else '❌ FAIL'}")
    
    if imports_success and api_success and llm_success:
        print("\n🎉 All tests passed! LLM enhancement is working!")
    elif imports_success and api_success:
        print("\n⚠️  API works but evaluator LLM enhancement needs debugging")
    else:
        print("\n💥 Some critical tests failed")
        sys.exit(1)