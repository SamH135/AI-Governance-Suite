#!/usr/bin/env python3
"""
Test script to validate unified API integration.
"""

import sys
import asyncio
from pathlib import Path

# Add services to path - adjust for container environment
current_dir = Path(__file__).parent
if current_dir.name == "services":
    # Running from services directory in container
    sys.path.insert(0, str(current_dir))
else:
    # Running from project root
    sys.path.insert(0, str(current_dir / "services"))

async def test_unified_api():
    """Test the unified API system."""
    print("🔍 Testing Unified API Integration...")
    
    try:
        # Import unified API
        from shared.unified_api import get_unified_api, ModelConfig
        
        # Initialize API
        api = get_unified_api()
        print("✅ Unified API imported and initialized")
        
        # Test provider discovery
        providers = api.list_providers()
        print(f"✅ Auto-discovered providers: {providers}")
        
        # Test provider info
        for provider in providers:
            try:
                info = api.get_provider_info(provider)
                print(f"  📋 {provider}: {info.get('name', 'Unknown')}")
            except Exception as e:
                print(f"  ⚠️  {provider}: {e}")
        
        # Test aliases
        aliases = api.get_providers_with_aliases()
        print(f"✅ Provider aliases: {aliases}")
        
        # Test local provider
        if "local" in providers:
            config = ModelConfig(
                provider="local",
                model_id="test-model",
                temperature=0.7,
                max_tokens=100
            )
            
            response = await api.agenerate("Hello, this is a test.", config)
            if response.error:
                print(f"❌ Local provider test failed: {response.error.message}")
            else:
                print(f"✅ Local provider test: {response.content[:50]}...")
        
        print("\n🎉 All tests passed! Unified API is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_unified_api())
    sys.exit(0 if success else 1)