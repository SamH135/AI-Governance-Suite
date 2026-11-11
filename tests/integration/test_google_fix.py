#!/usr/bin/env python3
"""
Test the Google provider fix with model ID normalization
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

try:
    from unified_api.api import get_unified_api
    from unified_api.base import ModelConfig, ModelRequest
    
    def test_google_model_normalization():
        """Test Google model ID normalization"""
        print("Testing Google model ID normalization...")
        
        # Test model ID mappings
        test_configs = [
            ("gemini-2.5-flash", "gemini-1.5-flash"),
            ("gemini-1.5-flash", "gemini-1.5-flash"),
            ("models/gemini-1.5-pro", "gemini-1.5-pro"),
            ("gemini-pro", "gemini-1.5-pro")
        ]
        
        unified_api = get_unified_api()
        
        for original_id, expected_id in test_configs:
            config = ModelConfig(
                provider="google",
                model_id=original_id,
                api_key="test-key",
                temperature=0.7,
                max_tokens=100
            )
            
            # Import provider directly to test normalization
            from unified_api.providers.google import GoogleProvider
            provider = GoogleProvider(config)
            normalized_id = provider._normalize_model_id(original_id)
            
            print(f"✓ {original_id} -> {normalized_id} (expected: {expected_id})")
            assert normalized_id == expected_id, f"Expected {expected_id}, got {normalized_id}"
        
        print("✅ All model ID normalizations work correctly!")
        
        # Test with actual API call (will fail due to no API key, but should show better error)
        print("\nTesting error handling with invalid model ID...")
        
        config = ModelConfig(
            provider="google", 
            model_id="gemini-2.5-flash",  # This should get normalized to gemini-1.5-flash
            api_key="invalid-key",
            temperature=0.7,
            max_tokens=50
        )
        
        request = ModelRequest(prompt="Test")
        response = unified_api.generate(prompt=request.prompt, config=config)
        
        if response.error:
            print(f"✓ Error handled correctly: {response.error.message[:100]}...")
            if "gemini-1.5-flash" in response.error.message:
                print("✅ Model ID was correctly normalized in the request!")
        else:
            print("❌ Expected error but got success")
            
    test_google_model_normalization()
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Test failed: {e}")