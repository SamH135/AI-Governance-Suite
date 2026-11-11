#!/usr/bin/env python3  
"""
Final test script to verify LLM functionality is now working.
This creates a comprehensive test inside the container.
"""

def create_final_test():
    """Create the final comprehensive test script."""
    test_script = '''
import os
import sys
import json
import time

# Set up paths for container environment
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app/services")

def main():
    print("🚀 Final LLM Enhancement Test")
    print("=" * 60)
    
    try:
        # Import everything we need
        from shared.unified_api.base import ModelConfig, ModelType
        from shared.unified_api import get_unified_api
        from services.compliance.framework.core.registry import Registry
        
        print("✅ All imports successful")
        
        # Test unified API
        api = get_unified_api()
        providers = api.list_providers()
        print(f"📋 Available providers: {providers}")
        
        # Discover evaluators
        print("🔍 Discovering evaluators...")
        Registry.discover_evaluators()
        evaluators = Registry.list_evaluators()
        print(f"📊 Found evaluators: {evaluators}")
        
        # Get Generic Compliance evaluator
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        print(f"✅ Loaded evaluator: {type(evaluator).__name__}")
        
        # Test 1: Rule-based analysis (baseline)
        print("\\n📝 Test 1: Rule-based Analysis")
        print("-" * 40)
        
        test_text = """
        Our AI system processes loan applications using personal data including race, gender, and zip code.
        We share customer social security numbers with third parties without explicit consent.
        The system makes automated decisions that affect people's financial status.
        """
        
        result_rule = evaluator.evaluate(text=test_text)
        print(f"Method: {result_rule.get('method', 'unknown')}")
        print(f"Score: {result_rule.get('compliance_score', 'N/A')}")
        print(f"Violations: {len(result_rule.get('violations', []))}")
        
        # Test 2: LLM-enhanced analysis
        print("\\n🤖 Test 2: LLM-Enhanced Analysis")
        print("-" * 40)
        
        # Create LLM config
        llm_config = ModelConfig(
            provider="google",
            model_id="gemini-1.5-flash",
            api_key= os.getenv("GOOGLE_API_KEY", ""),
            temperature=0.3,
            max_tokens=1000,
            usage_type=ModelType.EVALUATOR
        )
        
        print(f"Provider: {llm_config.provider}")
        print(f"Model: {llm_config.model_id}")
        print("Running LLM-enhanced evaluation...")
        
        start_time = time.time()
        result_llm = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=llm_config
        )
        duration = time.time() - start_time
        
        print(f"Duration: {duration:.2f}s")
        print(f"Method: {result_llm.get('method', 'unknown')}")
        print(f"Score: {result_llm.get('compliance_score', 'N/A')}")
        print(f"Violations: {len(result_llm.get('violations', []))}")
        
        # Check if LLM was actually used
        if 'llm' in result_llm.get('method', '').lower():
            print("🎉 SUCCESS: LLM enhancement is working!")
            
            # Show comparison
            print("\\n📊 Comparison:")
            print(f"Rule-based score: {result_rule.get('compliance_score', 'N/A')}")
            print(f"LLM-enhanced score: {result_llm.get('compliance_score', 'N/A')}")
            
            # Show detailed LLM result
            print("\\n📋 LLM Analysis Details:")
            explanation = result_llm.get('explanation', 'No explanation')
            print(f"Explanation: {explanation[:200]}...")
            
            return True
        else:
            print(f"⚠️ LLM not used, fallback: {result_llm.get('fallback_reason', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\\n🎉 LLM Enhancement is fully working!")
        exit(0)
    else:
        print("\\n💥 LLM Enhancement needs debugging")
        exit(1)
'''
    return test_script

def run_final_test():
    """Run the final test in the container."""
    print("🐳 Running Final LLM Test in Container")
    print("=" * 60)
    
    try:
        import subprocess
        
        test_script = create_final_test()
        
        # Write test script to a file in the container
        with open("/tmp/container_test.py", "w") as f:
            f.write(test_script)
        
        # Copy to container and run
        subprocess.run([
            'docker', 'cp', '/tmp/container_test.py', 
            'ai-governance-suite-compliance-service-1:/app/final_test.py'
        ], check=True)
        
        # Run the test
        result = subprocess.run([
            'docker', 'exec', 'ai-governance-suite-compliance-service-1',
            'python', '/app/final_test.py'
        ], capture_output=True, text=True, timeout=120)
        
        print("📤 Container Test Output:")
        print(result.stdout)
        
        if result.stderr:
            print("📥 Container Errors:")
            print(result.stderr)
        
        success = result.returncode == 0
        return success
        
    except Exception as e:
        print(f"❌ Error running final test: {e}")
        return False

def create_final_curl_command():
    """Create the final working curl command."""
    print("\\n🔧 Final Working Curl Command")
    print("=" * 60)
    
    request_body = {
        "text": "Our system automatically processes loan applications using demographic data including race, gender, and zip code. We share customer personal information with third parties without explicit consent. Social security numbers are stored in plain text files for easy access.",
        "llm_config": {
            "provider": "google",
            "model_id": "gemini-1.5-flash",
            "api_key": os.getenv("GOOGLE_API_KEY", ""),
            "temperature": 0.3,
            "max_tokens": 1000
        }
    }
    
    import json
    body_json = json.dumps(request_body)
    
    curl_command = f'''curl -X POST "http://localhost:8001/evaluators/test/Generic%20Compliance%20Analysis" \\
  -H "Content-Type: application/json" \\
  -d '{body_json}'
'''
    
    print("📋 Copy and paste this command:")
    print("=" * 40)
    print(curl_command)
    
    print("\\n📝 Expected Response:")
    print("- success: true")
    print("- method: 'llm_enhanced' (if working)")
    print("- compliance_score: numerical score")
    print("- violations: array of compliance issues")
    print("- explanation: LLM-generated analysis")
    
    return curl_command

if __name__ == "__main__":
    print("🚀 Final LLM Enhancement Verification")
    print("=" * 60)
    
    # Run comprehensive test
    success = run_final_test()
    
    # Generate curl command  
    curl_cmd = create_final_curl_command()
    
    print("\\n" + "=" * 60)
    print("📈 Final Test Results:")
    print(f"  LLM Enhancement: {'✅ WORKING' if success else '❌ NEEDS DEBUG'}")
    
    if success:
        print("\\n🎉 SUCCESS! Generic Compliance Evaluator with LLM Enhancement is fully functional!")
        print("✅ The evaluator can use Google Gemini for enhanced analysis")
        print("✅ Ready for production use via API endpoints")
        print("✅ Can be used as the template for all other evaluators")
    else:
        print("\\n💥 LLM Enhancement still needs debugging")