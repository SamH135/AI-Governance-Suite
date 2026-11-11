#!/usr/bin/env python3
"""
Test the Google provider with proper API format
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

try:
    from unified_api.api import get_unified_api
    from unified_api.base import ModelConfig, ModelRequest
    from unified_api.providers.google import GoogleProvider
    
    def test_google_request_format():
        """Test Google API request payload format"""
        print("Testing Google API request format...")
        
        config = ModelConfig(
            provider="google",
            model_id="gemini-2.5-flash",
            api_key="test-key",
            temperature=0.7,
            max_tokens=100
        )
        
        provider = GoogleProvider(config)
        
        # Test simple request
        request = ModelRequest(prompt="Hello, how are you?")
        payload = provider._build_request_payload(request)
        
        print("Simple request payload:")
        print(json.dumps(payload, indent=2))
        
        # Test with system prompt
        request_with_system = ModelRequest(
            prompt="Hello, how are you?",
            system_prompt="You are a helpful assistant."
        )
        payload_with_system = provider._build_request_payload(request_with_system)
        
        print("\nRequest with system prompt payload:")
        print(json.dumps(payload_with_system, indent=2))
        
        # Verify payload structure
        assert "contents" in payload
        assert "generationConfig" in payload
        assert "safetySettings" in payload
        assert len(payload["contents"]) > 0
        assert "parts" in payload["contents"][0]
        assert "text" in payload["contents"][0]["parts"][0]
        
        print("✅ Google API request format is correct!")
        
        # Test model ID normalization
        test_ids = [
            "gemini-2.5-flash",
            "models/gemini-1.5-pro", 
            "gemini-1.0-pro"
        ]
        
        print("\nTesting model ID handling:")
        for model_id in test_ids:
            normalized = provider._normalize_model_id(model_id)
            print(f"  {model_id} -> {normalized}")
        
        return True
        
    if test_google_request_format():
        print("\n🎉 Google provider format test passed!")
        
except Exception as e:
    print(f"Test failed: {e}")
    import traceback
    traceback.print_exc()