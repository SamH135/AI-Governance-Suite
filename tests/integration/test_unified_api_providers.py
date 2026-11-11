#!/usr/bin/env python3
"""
Comprehensive test suite for Unified AI API providers
Tests each provider (OpenAI, Google, Anthropic, local) through the shared/unified_api system
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Add workspace root to sys.path for imports
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

try:
    from shared.unified_api.api import get_unified_api
    from shared.unified_api.base import ModelConfig, ModelRequest, ModelType
    from shared.unified_api.providers.openai import OpenAIProvider
    from shared.unified_api.providers.google import GoogleProvider
    from shared.unified_api.providers.anthropic import AnthropicProvider
    print("✓ Successfully imported Unified API components")
except ImportError as e:
    print(f"✗ Failed to import Unified API components: {e}")
    # Do not call sys.exit at module level so pytest collection doesn't crash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UnifiedAPITester:
    """Test suite for Unified AI API providers"""
    
    def __init__(self):
        self.unified_api = get_unified_api()
        self.test_results = {}
        
    def test_provider_initialization(self) -> Dict[str, bool]:
        """Test that all providers can be initialized"""
        print("\n=== Testing Provider Initialization ===")
        results = {}
        
        providers = self.unified_api.list_providers()
        print(f"Available providers: {providers}")
        
        for provider_name in providers:
            try:
                info = self.unified_api.get_provider_info(provider_name)
                print(f"✓ {provider_name}: {info.get('description', 'No description')}")
                results[provider_name] = True
            except Exception as e:
                print(f"✗ {provider_name}: {e}")
                results[provider_name] = False
                
        return results
    
    def test_openai_provider(self) -> Dict[str, Any]:
        """Test OpenAI provider with actual API call"""
        print("\n=== Testing OpenAI Provider ===")
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("⚠ OPENAI_API_KEY not set, skipping OpenAI test")
            return {"skipped": True, "reason": "No API key"}
            
        try:
            config = ModelConfig(
                provider="openai",
                model_id="gpt-3.5-turbo",
                api_key=api_key,
                temperature=0.7,
                max_tokens=100,
                timeout=30
            )
            
            request = ModelRequest(
                prompt="Say 'OpenAI test successful' to confirm the integration is working."
            )
            
            # Test synchronous call
            response = self.unified_api.generate(
                prompt=request.prompt,
                config=config
            )
            
            success = response.error is None and "successful" in response.content.lower()
            
            result = {
                "success": success,
                "response": response.content[:200],
                "model_id": response.model_id,
                "provider": response.provider,
                "error": response.error.message if response.error else None
            }
            
            print(f"✓ OpenAI test: {'PASSED' if success else 'FAILED'}")
            if response.content:
                print(f"  Response: {response.content[:100]}...")
                
            return result
            
        except Exception as e:
            print(f"✗ OpenAI test failed: {e}")
            return {"success": False, "error": str(e)}
    
    def test_google_provider(self) -> Dict[str, Any]:
        """Test Google provider with actual API call"""
        print("\n=== Testing Google Provider ===")
        
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print("⚠ GOOGLE_API_KEY not set, skipping Google test")
            return {"skipped": True, "reason": "No API key"}
            
        try:
            config = ModelConfig(
                provider="google",
                model_id="gemini-1.5-flash",
                api_key=api_key,
                temperature=0.7,
                max_tokens=100,
                timeout=30
            )
            
            request = ModelRequest(
                prompt="Say 'Google test successful' to confirm the integration is working."
            )
            
            response = self.unified_api.generate(
                prompt=request.prompt,
                config=config
            )
            
            success = response.error is None and "successful" in response.content.lower()
            
            result = {
                "success": success,
                "response": response.content[:200],
                "model_id": response.model_id,
                "provider": response.provider,
                "error": response.error.message if response.error else None
            }
            
            print(f"✓ Google test: {'PASSED' if success else 'FAILED'}")
            if response.content:
                print(f"  Response: {response.content[:100]}...")
                
            return result
            
        except Exception as e:
            print(f"✗ Google test failed: {e}")
            return {"success": False, "error": str(e)}
    
    def test_anthropic_provider(self) -> Dict[str, Any]:
        """Test Anthropic provider with actual API call"""
        print("\n=== Testing Anthropic Provider ===")
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("⚠ ANTHROPIC_API_KEY not set, skipping Anthropic test")
            return {"skipped": True, "reason": "No API key"}
            
        try:
            config = ModelConfig(
                provider="anthropic",
                model_id="claude-3-haiku-20240307",
                api_key=api_key,
                temperature=0.7,
                max_tokens=100,
                timeout=30
            )
            
            request = ModelRequest(
                prompt="Say 'Anthropic test successful' to confirm the integration is working."
            )
            
            response = self.unified_api.generate(
                prompt=request.prompt,
                config=config
            )
            
            success = response.error is None and "successful" in response.content.lower()
            
            result = {
                "success": success,
                "response": response.content[:200],
                "model_id": response.model_id,
                "provider": response.provider,
                "error": response.error.message if response.error else None
            }
            
            print(f"✓ Anthropic test: {'PASSED' if success else 'FAILED'}")
            if response.content:
                print(f"  Response: {response.content[:100]}...")
                
            return result
            
        except Exception as e:
            print(f"✗ Anthropic test failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_async_providers(self) -> Dict[str, Any]:
        """Test async functionality of providers"""
        print("\n=== Testing Async Provider Functionality ===")
        
        results = {}
        
        # Test OpenAI async
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                config = ModelConfig(
                    provider="openai",
                    model_id="gpt-3.5-turbo",
                    api_key=api_key,
                    temperature=0.7,
                    max_tokens=50,
                    timeout=30
                )
                
                response = await self.unified_api.agenerate(
                    prompt="Respond 'Async test successful'",
                    config=config
                )
                
                results["openai_async"] = {
                    "success": response.error is None,
                    "response": response.content[:100] if response.content else None,
                    "error": response.error.message if response.error else None
                }
                print(f"✓ OpenAI async: {'PASSED' if response.error is None else 'FAILED'}")
                
            except Exception as e:
                results["openai_async"] = {"success": False, "error": str(e)}
                print(f"✗ OpenAI async failed: {e}")
        
        return results
    
    def test_provider_validation(self) -> Dict[str, Any]:
        """Test provider configuration validation"""
        print("\n=== Testing Provider Validation ===")
        
        results = {}
        
        # Test invalid configurations
        invalid_configs = [
            {
                "name": "missing_api_key",
                "config": ModelConfig(
                    provider="openai",
                    model_id="gpt-3.5-turbo",
                    api_key=None
                )
            },
            {
                "name": "invalid_provider",
                "config": ModelConfig(
                    provider="invalid_provider",
                    model_id="test-model",
                    api_key="test-key"
                )
            }
        ]
        
        for test_case in invalid_configs:
            try:
                self.unified_api.generate(
                    prompt="Test",
                    config=test_case["config"]
                )
                results[test_case["name"]] = {
                    "success": False,
                    "error": "Should have failed but didn't"
                }
                print(f"✗ {test_case['name']}: Should have failed validation")
            except Exception as e:
                results[test_case["name"]] = {
                    "success": True,
                    "error": str(e)
                }
                print(f"✓ {test_case['name']}: Correctly failed with {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites"""
        print("🚀 Starting Unified AI API Provider Tests")
        print("=" * 60)
        
        # Test initialization
        self.test_results["initialization"] = self.test_provider_initialization()
        
        # Test individual providers
        self.test_results["openai"] = self.test_openai_provider()
        self.test_results["google"] = self.test_google_provider()
        self.test_results["anthropic"] = self.test_anthropic_provider()
        
        # Test validation
        self.test_results["validation"] = self.test_provider_validation()
        
        # Test async functionality
        async def run_async_tests():
            return await self.test_async_providers()
        
        self.test_results["async"] = asyncio.run(run_async_tests())
        
        return self.test_results
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("UNIFIED AI API PROVIDER TEST REPORT")
        report.append("=" * 60)
        report.append(f"Test run at: {datetime.now().isoformat()}")
        report.append("")
        
        total_tests = 0
        passed_tests = 0
        
        for category, results in self.test_results.items():
            report.append(f"\n📊 {category.upper()} TESTS:")
            report.append("-" * 40)
            
            if isinstance(results, dict):
                for test_name, result in results.items():
                    total_tests += 1
                    if isinstance(result, dict):
                        success = result.get("success", False)
                        if success:
                            passed_tests += 1
                            report.append(f"  ✅ {test_name}: PASSED")
                        elif result.get("skipped"):
                            report.append(f"  ⏭️  {test_name}: SKIPPED - {result.get('reason')}")
                        else:
                            report.append(f"  ❌ {test_name}: FAILED")
                            if result.get("error"):
                                report.append(f"     Error: {result['error']}")
                    elif result:
                        passed_tests += 1
                        report.append(f"  ✅ {test_name}: PASSED")
                    else:
                        report.append(f"  ❌ {test_name}: FAILED")
        
        # Summary
        report.append("\n" + "=" * 60)
        report.append("SUMMARY")
        report.append("=" * 60)
        report.append(f"Total tests: {total_tests}")
        report.append(f"Passed: {passed_tests}")
        report.append(f"Failed: {total_tests - passed_tests}")
        report.append(f"Success rate: {(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%")
        
        if passed_tests == total_tests:
            report.append("\n🎉 ALL TESTS PASSED! Unified AI API is working correctly.")
        else:
            report.append(f"\n⚠️  {total_tests - passed_tests} tests failed. Please check the errors above.")
        
        report.append("\n💡 Next steps:")
        report.append("  1. Set missing API keys in environment variables")
        report.append("  2. Test model configurations in the frontend")
        report.append("  3. Verify end-to-end functionality through the gateway")
        
        return "\n".join(report)

def main():
    """Main test execution function"""
    tester = UnifiedAPITester()
    
    # Run all tests
    results = tester.run_all_tests()
    
    # Generate and print report
    report = tester.generate_report()
    print(report)
    
    # Save results to file
    with open("unified_api_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # Save report to file
    with open("unified_api_test_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n📄 Results saved to: unified_api_test_results.json")
    print(f"📄 Report saved to: unified_api_test_report.txt")

if __name__ == "__main__":
    main()