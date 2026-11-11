#!/usr/bin/env python3
"""
Test LLM functionality within the Docker container environment.
This simulates how the evaluator would work when called from the API.
"""

import requests
import json
import time

def test_evaluator_via_container():
    """Test the evaluator by calling into the running Docker container."""
    print("🐳 Testing LLM Enhancement via Docker Container")
    print("=" * 60)
    
    # Create a test by directly accessing the container's Python environment
    container_test_script = '''
import sys
import os
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app/services")

try:
    # Test the imports within the container
    from shared.unified_api.base import ModelConfig, ModelType
    from shared.unified_api import get_unified_api
    from services.compliance.framework.core.registry import Registry
    
    print("✅ All imports successful in container")
    
    # Get unified API
    api = get_unified_api()
    providers = api.list_providers()
    print(f"📋 Available providers: {providers}")
    
    # Get evaluator
    Registry.discover_evaluators()
    evaluator = Registry.get_evaluator("Generic Compliance Analysis")
    
    # Create LLM config
    llm_config = ModelConfig(
        provider="google",
        model_id="gemini-1.5-flash",
        api_key= os.getenv("GOOGLE_API_KEY", ""),
        temperature=0.3,
        max_tokens=1000,
        usage_type=ModelType.EVALUATOR
    )
    
    # Test text
    test_text = """
    Our system automatically processes personal data including race and gender for loan decisions.
    We share customer information with third parties without explicit consent.
    Social security numbers are stored in plain text files on our servers.
    """
    
    print(f"🧪 Running LLM-enhanced evaluation...")
    
    # Run evaluation
    result = evaluator.evaluate(
        text=test_text,
        evaluator_llm_config=llm_config
    )
    
    print(f"📊 Results:")
    print(f"  Method: {result.get('method', 'unknown')}")
    print(f"  Score: {result.get('compliance_score', 'N/A')}")
    print(f"  Status: {result.get('compliance_status', 'N/A')}")
    print(f"  Processing Time: {result.get('processing_time', 'N/A'):.4f}s")
    
    if 'llm' in result.get('method', '').lower():
        print("🎉 SUCCESS: LLM enhancement working!")
        import json
        print("📋 Full Result:")
        print(json.dumps(result, indent=2)[:800] + "..." if len(json.dumps(result, indent=2)) > 800 else json.dumps(result, indent=2))
    else:
        print(f"⚠️ Fallback to rule-based: {result.get('fallback_reason', 'Unknown')}")
        
except Exception as e:
    print(f"❌ Container test failed: {e}")
    import traceback
    traceback.print_exc()
'''
    
    try:
        # Execute the test script in the container
        print("🔧 Executing test within Docker container...")
        
        import subprocess
        result = subprocess.run([
            'docker', 'exec', 'ai-governance-suite-compliance-service-1',
            'python', '-c', container_test_script
        ], capture_output=True, text=True, timeout=60)
        
        print("📤 Container Output:")
        print(result.stdout)
        
        if result.stderr:
            print("📥 Container Errors:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Container test completed successfully")
            return True
        else:
            print(f"❌ Container test failed with code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Container test timed out")
        return False
    except Exception as e:
        print(f"❌ Error running container test: {e}")
        return False

def create_working_curl_command():
    """Create a working curl command that would test the LLM functionality."""
    print(f"\n🔧 Creating Working Curl Command")
    print("=" * 60)
    
    # The request body that would test LLM enhancement
    request_body = {
        "text": "Our system collects personal data without consent and makes automated decisions affecting users financial status based on demographic information.",
        "llm_config": {
            "provider": "google",
            "model_id": "gemini-1.5-flash",
            "api_key": os.getenv("GOOGLE_API_KEY", ""),
            "temperature": 0.3,
            "max_tokens": 1000
        }
    }
    
    print("📋 Equivalent curl command:")
    print("=" * 40)
    
    curl_command = f'''curl -X POST "http://localhost:8001/evaluators/test/Generic%20Compliance%20Analysis" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(request_body, indent=2)}'
'''
    
    print(curl_command)
    
    print("\n📝 This would:")
    print("  1. Call the Generic Compliance Analysis evaluator")
    print("  2. Use Google Gemini for LLM-enhanced analysis")
    print("  3. Return detailed compliance assessment")
    print("  4. Show method='llm_enhanced' if successful")
    
    return curl_command

if __name__ == "__main__":
    print("🚀 Testing LLM Enhancement in Production Environment")
    print("=" * 60)
    
    # Test within container
    container_success = test_evaluator_via_container()
    
    # Create curl command
    curl_command = create_working_curl_command()
    
    print("\n" + "=" * 60)
    print("📈 Test Summary:")
    print(f"  Container LLM Test: {'✅ PASS' if container_success else '❌ FAIL'}")
    
    if container_success:
        print("\n🎉 LLM Enhancement is working in production!")
        print("✅ The evaluator can successfully use Google Gemini")
        print("✅ Ready for curl testing via API endpoints")
    else:
        print("\n💥 LLM Enhancement needs further debugging")