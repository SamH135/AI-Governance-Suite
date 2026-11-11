#!/usr/bin/env python3
"""
Direct LLM test for the Generic Compliance Evaluator.
This bypasses the unified API and tests LLM functionality directly.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services"))

def test_llm_direct():
    """Test LLM functionality by calling the evaluator's LLM methods directly."""
    print("🤖 Testing LLM Enhanced Compliance Evaluation")
    print("=" * 60)
    
    try:
        # Import the evaluator
        from services.compliance.framework.core.registry import Registry
        Registry.discover_evaluators()
        
        # Get the evaluator
        evaluator = Registry.get_evaluator("Generic Compliance Analysis")
        
        # Test text that should trigger compliance issues
        test_text = """
        Our AI system automatically processes loan applications using demographic data including race, gender, and zip code.
        We use machine learning to predict creditworthiness based on historical patterns.
        Personal information is collected and used for automated decision-making without explicit user consent.
        The system has been trained on data from the past 20 years of lending decisions.
        """
        
        print(f"📝 Test Text ({len(test_text)} chars):")
        print(test_text.strip())
        
        # Try to call the evaluator's LLM analysis methods directly
        print(f"\n🔍 Checking evaluator methods...")
        
        # Check if evaluator has LLM-related methods
        methods = [method for method in dir(evaluator) if 'llm' in method.lower()]
        print(f"LLM-related methods: {methods}")
        
        # Check if it has any analysis methods that might use LLM
        analysis_methods = [method for method in dir(evaluator) if 'analyz' in method.lower() or 'enhance' in method.lower()]
        print(f"Analysis methods: {analysis_methods}")
        
        # Try calling with a simple config object
        print(f"\n🧪 Testing with mock LLM config...")
        
        # Create a simple config-like object
        class MockLLMConfig:
            def __init__(self):
                self.provider = "google"
                self.model_id = "gemini-pro"
                self.api_key = os.getenv("GOOGLE_API_KEY", "")
                self.temperature = 0.3
                self.max_tokens = 1000
        
        mock_config = MockLLMConfig()
        
        # Try calling evaluate with the config
        result = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=mock_config
        )
        
        print(f"✅ LLM evaluation completed!")
        print(f"📊 Results:")
        print(json.dumps(result, indent=2))
        
        # Check if it actually used LLM
        method_used = result.get('method', 'unknown')
        print(f"\n🔧 Method used: {method_used}")
        
        if 'llm' in method_used.lower() or 'enhanced' in method_used.lower():
            print("✅ LLM was successfully used!")
            return True
        else:
            print("⚠️ Fell back to rule-based analysis (LLM not used)")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_direct_api_call():
    """Test by making a direct API call to Google's Gemini."""
    print(f"\n🌐 Testing Direct Google Gemini API Call")
    print("=" * 60)
    
    try:
        import requests
        
        api_key = os.getenv("GOOGLE_API_KEY", "")
        
        # Test with a simple compliance prompt
        prompt = """
        Analyze the following text for compliance issues related to GDPR, HIPAA, bias, and security:
        
        "Our AI system automatically processes loan applications using demographic data including race, gender, and zip code. We use machine learning to predict creditworthiness based on historical patterns."
        
        Provide a JSON response with:
        - compliance_score (0-100)
        - violations found
        - frameworks affected
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        }
        
        print(f"🔗 Making API call to Google Gemini...")
        print(f"URL: {url}")
        
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"📡 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if 'candidates' in result and len(result['candidates']) > 0:
                text_response = result['candidates'][0]['content']['parts'][0]['text']
                print(f"✅ LLM Response received!")
                print(f"📝 Response:")
                print(text_response)
                return True
            else:
                print(f"⚠️ Unexpected response format: {result}")
                return False
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Error making API call: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing LLM Enhanced Compliance Evaluation")
    print("=" * 60)
    
    # Test LLM functionality directly
    llm_success = test_llm_direct()
    
    # Test direct API call to verify the key works
    api_success = test_with_direct_api_call()
    
    print("\n" + "=" * 60)
    print("📈 LLM Test Summary:")
    print(f"  Evaluator LLM Test: {'✅ PASS' if llm_success else '❌ FAIL'}")
    print(f"  Direct API Test: {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if api_success:
        print("\n🎉 Your Google Gemini API key is working!")
        if not llm_success:
            print("⚠️  However, the evaluator couldn't use it due to missing unified API")
    else:
        print("\n💥 API key or connection issues detected.")