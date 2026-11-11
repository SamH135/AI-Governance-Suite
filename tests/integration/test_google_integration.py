#!/usr/bin/env python3
"""
Test script to validate Unified API integration with Google API.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
import requests
import time

# Google API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Service URLs
GATEWAY_URL = "http://localhost:8000"
COMPLIANCE_URL = "http://localhost:8001"
PROMPTS_URL = "http://localhost:8002"
DOCUMENTS_URL = "http://localhost:8003"

def wait_for_service(url, service_name, max_retries=30):
    """Wait for a service to become healthy."""
    print(f"🔍 Waiting for {service_name} to be ready...")
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ {service_name} is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"  ⏳ Attempt {attempt + 1}/{max_retries} - {service_name} not ready yet...")
        time.sleep(2)
    
    print(f"❌ {service_name} failed to become ready after {max_retries} attempts")
    return False

def test_compliance_service():
    """Test compliance service with Google API."""
    print("\n🧪 Testing Compliance Service with Google API...")
    
    # Test data for generic compliance evaluator
    test_data = {
        "text": "This AI system processes user data including names, emails, and location information for personalized recommendations.",
        "test_subject_config": {
            "provider": "google",
            "model_id": "gemini-1.5-flash",
            "api_key": GOOGLE_API_KEY,
            "temperature": 0.3,
            "max_tokens": 500
        },
        "evaluator_llm_config": {
            "provider": "google", 
            "model_id": "gemini-1.5-flash",
            "api_key": GOOGLE_API_KEY,
            "temperature": 0.1,
            "max_tokens": 1000
        },
        "evaluation_context": {
            "compliance_framework": "GDPR",
            "evaluation_criteria": ["data_minimization", "consent", "transparency", "purpose_limitation"]
        }
    }
    
    try:
        response = requests.post(
            f"{COMPLIANCE_URL}/compliance/evaluate/generic_compliance",
            json=test_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Compliance service test passed!")
            print(f"  Score: {result.get('score', 'N/A')}")
            print(f"  Status: {result.get('status', 'N/A')}")
            return True
        else:
            print(f"❌ Compliance service test failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Compliance service test failed with exception: {e}")
        return False

def test_prompts_service():
    """Test prompts service with Google API.""" 
    print("\n🧪 Testing Prompts Service with Google API...")
    
    test_data = {
        "prompt": "You are a helpful AI assistant. Please explain the concept of machine learning in simple terms.",
        "requirements": "The explanation should be accessible to beginners and include practical examples.",
        "llm_config": {
            "provider": "google",
            "model_id": "gemini-1.5-flash", 
            "api_key": GOOGLE_API_KEY,
            "temperature": 0.7,
            "max_tokens": 500
        }
    }
    
    try:
        response = requests.post(
            f"{PROMPTS_URL}/prompts/j1/optimize",
            json=test_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Prompts service test passed!")
            print(f"  Original prompt length: {len(test_data['prompt'])}")
            print(f"  Optimization status: {result.get('status', 'N/A')}")
            return True
        else:
            print(f"❌ Prompts service test failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Prompts service test failed with exception: {e}")
        return False

def test_documents_service():
    """Test documents service with Google API."""
    print("\n🧪 Testing Documents Service with Google API...")
    
    test_data = {
        "template_id": "regulatory_gdpr_compliance_report",
        "title": "GDPR Compliance Assessment Report",
        "variables": {
            "company_name": "Test Company Inc.",
            "assessment_date": "2024-01-15",
            "data_categories": ["Personal identifiers", "Contact information", "Usage data"],
            "compliance_score": "85%"
        },
        "llm_config": {
            "provider": "google",
            "model_id": "gemini-1.5-flash",
            "api_key": GOOGLE_API_KEY,
            "temperature": 0.3,
            "max_tokens": 2000
        }
    }
    
    try:
        response = requests.post(
            f"{DOCUMENTS_URL}/documents/generate",
            json=test_data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Documents service test passed!")
            print(f"  Document ID: {result.get('id', 'N/A')}")
            print(f"  Title: {result.get('title', 'N/A')}")
            return True
        else:
            print(f"❌ Documents service test failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Documents service test failed with exception: {e}")
        return False

def test_gateway_routing():
    """Test API gateway routing to services."""
    print("\n🧪 Testing API Gateway Routing...")
    
    test_endpoints = [
        ("/compliance/health", "Compliance routing"),
        ("/prompts/health", "Prompts routing"), 
        ("/documents/health", "Documents routing"),
        ("/tests/health", "Tests routing")
    ]
    
    success_count = 0
    for endpoint, description in test_endpoints:
        try:
            response = requests.get(f"{GATEWAY_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {description} working")
                success_count += 1
            else:
                print(f"❌ {description} failed: {response.status_code}")
        except Exception as e:
            print(f"❌ {description} failed with exception: {e}")
    
    return success_count == len(test_endpoints)

def main():
    """Main test execution."""
    print("🚀 Starting Unified AI API Integration Tests with Google API")
    print(f"🔑 Using Google API Key: {GOOGLE_API_KEY[:20]}...")
    print("="*60)
    
    # Wait for services to be ready
    services = [
        (GATEWAY_URL, "API Gateway"),
        (COMPLIANCE_URL, "Compliance Service"),
        (PROMPTS_URL, "Prompts Service"), 
        (DOCUMENTS_URL, "Documents Service")
    ]
    
    for url, name in services:
        if not wait_for_service(url, name):
            print(f"❌ {name} is not ready. Exiting...")
            return False
    
    print("\n" + "="*60)
    
    # Run tests
    test_results = []
    
    # Test gateway routing
    test_results.append(("Gateway Routing", test_gateway_routing()))
    
    # Test individual services
    test_results.append(("Compliance Service", test_compliance_service()))
    test_results.append(("Prompts Service", test_prompts_service()))
    test_results.append(("Documents Service", test_documents_service()))
    
    # Print summary
    print("\n" + "="*60)
    print("🎯 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    total = len(test_results)
    print("="*60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Unified API integration is working correctly with Google API.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the logs above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)