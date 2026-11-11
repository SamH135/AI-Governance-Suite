#!/usr/bin/env python3
"""
Test script to verify API key handling fix for model configurations.
This script tests that:
1. Model configurations can be tested with actual API keys (not masked ones)
2. API keys are properly retrieved from the database or API key manager
3. The masking only happens in responses, not in actual testing
"""

import asyncio
import json
import aiohttp
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
GATEWAY_URL = "http://localhost:8000"
TEST_CONFIG = {
    "name": "Test Google Gemini 2.5 flash",
    "description": "Test configuration for API key fix verification",
    "provider": "google",
    "model_id": "gemini-2.5-flash",
    "api_key": "AIzaSyC123456789_YOUR_ACTUAL_API_KEY_HERE",  # Replace with actual key
    "temperature": 0.3,
    "max_tokens": 1000,
    "timeout": 45,
    "enabled": True,
    "tags": ["testing", "api-key-fix"]
}

async def test_api_key_handling():
    """Test the API key handling fix."""
    
    if TEST_CONFIG["api_key"] == "AIzaSyC123456789_YOUR_ACTUAL_API_KEY_HERE":
        logger.error("Please replace the API key in TEST_CONFIG with your actual Google API key")
        return False
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Try to create a new model configuration
            logger.info("Step 1: Creating model configuration...")
            
            # Note: In a real environment, you'd need proper authentication headers
            headers = {
                "Content-Type": "application/json",
                # "Authorization": "Bearer YOUR_TOKEN_HERE"  # Add if auth is enabled
            }
            
            async with session.post(
                f"{GATEWAY_URL}/models/",
                json=TEST_CONFIG,
                headers=headers
            ) as response:
                if response.status == 201:
                    config_data = await response.json()
                    config_id = config_data["id"]
                    logger.info(f"✓ Model configuration created with ID: {config_id}")
                    
                    # Verify the API key is masked in the response
                    if config_data.get("api_key") == "***masked***":
                        logger.info("✓ API key is properly masked in response")
                    else:
                        logger.warning(f"⚠ API key masking issue: got '{config_data.get('api_key')}'")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create model configuration: {response.status} - {error_text}")
                    return False
            
            # Step 2: Test the model configuration
            logger.info("Step 2: Testing model configuration...")
            
            test_payload = {
                "id": config_id,
                "prompt": "Hello, please respond with 'Test successful' to confirm the model is working."
            }
            
            async with session.post(
                f"{GATEWAY_URL}/models/test",
                json=test_payload,
                headers=headers
            ) as response:
                test_result = await response.json()
                
                if response.status == 200:
                    if test_result.get("success"):
                        logger.info("✓ Model test completed successfully!")
                        logger.info(f"Response: {test_result.get('response_content', 'No content')}")
                        return True
                    else:
                        error_msg = test_result.get("error_message", "Unknown error")
                        if "***masked***" in error_msg:
                            logger.error("✗ API key masking issue detected in test - the fix is needed!")
                            logger.error(f"Error message: {error_msg}")
                        else:
                            logger.error(f"✗ Model test failed: {error_msg}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"Test request failed: {response.status} - {error_text}")
                    return False
                    
        except aiohttp.ClientConnectorError:
            logger.error("Could not connect to the gateway. Make sure it's running on http://localhost:8000")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

async def main():
    """Main test function."""
    logger.info("Testing API key handling fix...")
    logger.info("=" * 50)
    
    success = await test_api_key_handling()
    
    logger.info("=" * 50)
    if success:
        logger.info("✓ All tests passed! API key handling is working correctly.")
    else:
        logger.info("✗ Tests failed. The API key handling fix may not be working properly.")
        logger.info("Common issues:")
        logger.info("  1. Gateway service not running")
        logger.info("  2. Database schema not updated with api_key_id column")
        logger.info("  3. API key masking still affecting test functionality")
        logger.info("  4. Invalid API key provided")

if __name__ == "__main__":
    asyncio.run(main())