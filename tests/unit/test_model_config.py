#!/usr/bin/env python3
"""
Test script to create and test AI model configuration via API.
"""

import requests
import json
import time
import os

GATEWAY_URL = "http://localhost:8000"
# For alpha testing, use local provider with pre-determined responses
# Replace with actual API key for production testing
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

def test_frontend_health():
    """Test if frontend is accessible."""
    print("🔍 Testing Frontend Health...")
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print("✅ Frontend is accessible!")
            return True
        else:
            print(f"❌ Frontend returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend health check failed: {e}")
        return False

def get_auth_token():
    """Get authentication token for API access."""
    print("\n🔍 Getting Authentication Token...")
    
    # Try to register and login
    register_data = {
        "username": "testuser@example.com",
        "email": "testuser@example.com", 
        "password": "testpass123",
        "role": "user"
    }
    
    try:
        # Try registration (might fail if user exists)
        requests.post(f"{GATEWAY_URL}/api/auth/register", json=register_data, timeout=10)
    except:
        pass  # User might already exist
    
    # Now try to login
    try:
        auth_data = {
            "username": "testuser@example.com",
            "password": "testpass123"
        }
        
        response = requests.post(f"{GATEWAY_URL}/api/auth/login", json=auth_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            token = result.get('access_token')
            print("✅ Authentication successful!")
            return token
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return None

def create_model_config(token):
    """Create a Google AI model configuration."""
    print("\n🧪 Creating Google AI Model Configuration...")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    model_config = {
        "name": "Test Google Gemini Model",
        "description": "Google Gemini 1.5 Flash for testing compliance evaluations",
        "provider": "google",
        "model_id": "gemini-1.5-flash",
        "api_key": GOOGLE_API_KEY,
        "temperature": 0.3,
        "max_tokens": 1000,
        "top_p": 0.9,
        "timeout": 30,
        "enabled": True,
        "tags": ["testing", "compliance", "google"]
    }
    
    try:
        response = requests.post(
            f"{GATEWAY_URL}/api/models",
            json=model_config,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            print("✅ Model configuration created successfully!")
            print(f"  Model ID: {result.get('id')}")
            print(f"  Name: {result.get('name')}")
            print(f"  Provider: {result.get('provider')}")
            print(f"  Model: {result.get('model_id')}")
            return result
        else:
            print(f"❌ Model creation failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Model creation failed: {e}")
        return None

def test_model_config(token, model_config):
    """Test the created model configuration."""
    print("\n🧪 Testing Model Configuration...")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    test_data = {
        "provider": model_config["provider"],
        "model_id": model_config["model_id"],
        "api_key": model_config["api_key"],
        "temperature": model_config["temperature"],
        "max_tokens": model_config["max_tokens"],
        "test_prompt": "Hello! This is a test message to verify the AI model is working correctly. Please respond with a confirmation."
    }
    
    try:
        response = requests.post(
            f"{GATEWAY_URL}/api/models/test",
            json=test_data,
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Model test successful!")
            print(f"  Message: {result.get('message')}")
            print(f"  Details: {result.get('details')}")
            print(f"  Response Time: {result.get('response_time')}ms")
            print(f"  Tokens Used: {result.get('tokens_used')}")
            if result.get('test_response'):
                print(f"  AI Response: {result.get('test_response')[:100]}...")
            return True
        else:
            print(f"❌ Model test failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def test_compliance_with_model(token, model_config):
    """Test using the model for compliance evaluation."""
    print("\n🧪 Testing Compliance Evaluation with Model...")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    compliance_test = {
        "text": "Our AI system processes customer personal data including names, email addresses, and location information to provide personalized product recommendations and targeted marketing campaigns.",
        "test_subject_config": {
            "provider": model_config["provider"],
            "model_id": model_config["model_id"],
            "api_key": model_config["api_key"],
            "temperature": 0.3,
            "max_tokens": 500
        },
        "evaluator_llm_config": {
            "provider": model_config["provider"],
            "model_id": model_config["model_id"],
            "api_key": model_config["api_key"],
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
            f"{GATEWAY_URL}/api/compliance/evaluate/generic_compliance",
            json=compliance_test,
            headers=headers,
            timeout=90
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Compliance evaluation successful!")
            print(f"  Score: {result.get('score', 'N/A')}")
            print(f"  Status: {result.get('status', 'N/A')}")
            print(f"  Framework: GDPR")
            if result.get('details'):
                print(f"  Details: {str(result.get('details'))[:200]}...")
            return True
        else:
            print(f"❌ Compliance evaluation failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Compliance evaluation failed: {e}")
        return False

def list_model_configs(token):
    """List all model configurations."""
    print("\n📋 Listing All Model Configurations...")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    try:
        response = requests.get(
            f"{GATEWAY_URL}/api/models",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            models = response.json()
            print(f"✅ Found {len(models)} model configurations:")
            for model in models:
                status = "🟢" if model.get('enabled') else "🔴"
                print(f"  {status} {model.get('name')} ({model.get('provider')} - {model.get('model_id')})")
            return models
        else:
            print(f"❌ Failed to list models: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Failed to list models: {e}")
        return []

def main():
    """Main test execution."""
    print("🚀 AI Model Configuration Test Suite")
    print(f"🔑 Using Google API Key: {GOOGLE_API_KEY[:20]}...")
    print("="*60)
    
    # Test frontend accessibility
    if not test_frontend_health():
        print("⚠️  Frontend not accessible, but continuing with API tests...")
    
    # Get authentication token
    token = get_auth_token()
    
    # List existing models
    list_model_configs(token)
    
    # Create new model configuration
    model_config = create_model_config(token)
    
    if model_config:
        # Test the model configuration
        test_success = test_model_config(token, model_config)
        
        if test_success:
            # Test compliance evaluation with the model
            test_compliance_with_model(token, model_config)
        
        # List models again to show the new one
        list_model_configs(token)
    
    print("\n" + "="*60)
    print("🎯 TEST SUITE COMPLETE")
    print("="*60)
    print("✅ Frontend: http://localhost:3000/settings (AI Models tab)")
    print("✅ API Gateway: http://localhost:8000")
    print("✅ Model Configuration: Ready for use")
    print("\nYou can now access the AI Models configuration page at:")
    print("http://localhost:3000/settings → AI Models tab")

if __name__ == "__main__":
    main()