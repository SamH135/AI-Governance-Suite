#!/usr/bin/env python3

import requests
import json
import os
from datetime import datetime

# Login to get token
def get_auth_token():
    login_data = {
        "username": "testadmin",
        "password": "testpass123"
    }
    
    response = requests.post("http://localhost:8000/api/auth/login", 
                           json=login_data, 
                           headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        response_data = response.json()
        token = response_data.get("data", {}).get("token")
        return token
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_systems_api():
    # Get auth token
    token = get_auth_token()
    if not token:
        print("Failed to get authentication token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Testing AI Systems API")
    print("=" * 50)
    
    # 1. Test getting systems (should be empty initially)
    print("1. Getting all AI systems...")
    response = requests.get("http://localhost:8000/api/systems/", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        systems = response.json()
        print(f"Response: {json.dumps(systems, indent=2)}")
        print(f"Found {len(systems)} systems")
    else:
        print(f"Error: {response.text}")
        return
    
    # 2. First, let's create a model configuration to link to
    print("\n2. Creating a model configuration...")
    # For alpha testing, use local provider with pre-determined responses
    # Replace with actual API key for production testing
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model_data = {
        "name": "Test Model",
        "description": "Test model for systems API",
        "provider": "local" if not api_key else "openai",
        "model_id": "local-mock" if not api_key else "gpt-4",
        "api_key": api_key if api_key else "",
        "temperature": 0.7,
        "max_tokens": 1000,
        "timeout": 30
    }
    
    model_response = requests.post("http://localhost:8000/api/models/", 
                                 json=model_data, 
                                 headers=headers)
    print(f"Model creation status: {model_response.status_code}")
    if model_response.status_code == 201:
        model_result = model_response.json()
        model_id = model_result.get("id")
        print(f"Created model with ID: {model_id}")
    else:
        print(f"Model creation error: {model_response.text}")
        model_id = None
    
    # 3. Test creating a new AI system
    print("\n3. Creating a new AI system...")
    system_data = {
        "name": "Healthcare AI Assistant",
        "description": "AI system for medical diagnosis support",
        "system_type": "llm",
        "compliance_frameworks": ["GDPR", "HIPAA"],
        "industry": "healthcare"
    }
    
    if model_id:
        system_data["model_config_id"] = model_id
    
    response = requests.post("http://localhost:8000/api/systems/", 
                           json=system_data, 
                           headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        created_system = response.json()
        print(f"Response: {json.dumps(created_system, indent=2)}")
        system_id = created_system.get("system_id")
        print(f"Created system with ID: {system_id}")
    else:
        print(f"Error: {response.text}")
        return
    
    # 4. Test getting the specific system
    print(f"\n4. Getting AI system {system_id}...")
    response = requests.get(f"http://localhost:8000/api/systems/{system_id}", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        system = response.json()
        print(f"Response: {json.dumps(system, indent=2)}")
    else:
        print(f"Error: {response.text}")
    
    # 5. Test updating the system
    print(f"\n5. Updating AI system {system_id}...")
    update_data = {
        "description": "Updated AI system for medical diagnosis support with enhanced features",
        "compliance_frameworks": ["GDPR", "HIPAA", "FDA"]
    }
    
    response = requests.put(f"http://localhost:8000/api/systems/{system_id}", 
                          json=update_data, 
                          headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        updated_system = response.json()
        print(f"Response: {json.dumps(updated_system, indent=2)}")
    else:
        print(f"Error: {response.text}")
    
    # 6. Test getting all systems again (should show our created system)
    print("\n6. Getting all AI systems again...")
    response = requests.get("http://localhost:8000/api/systems", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        systems = response.json()
        print(f"Response: {json.dumps(systems, indent=2)}")
        print(f"Found {len(systems)} systems")
    else:
        print(f"Error: {response.text}")
    
    # 7. Test deleting the system
    print(f"\n7. Deleting AI system {system_id}...")
    response = requests.delete(f"http://localhost:8000/api/systems/{system_id}", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 204:
        print("System deleted successfully")
    else:
        print(f"Error: {response.text}")
    
    # 8. Verify system was deleted
    print(f"\n8. Verifying system {system_id} was deleted...")
    response = requests.get(f"http://localhost:8000/api/systems/{system_id}", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 404:
        print("System successfully deleted (404 as expected)")
    else:
        print(f"Unexpected response: {response.text}")
    
    print("\nAI Systems API testing completed!")

if __name__ == "__main__":
    test_systems_api()