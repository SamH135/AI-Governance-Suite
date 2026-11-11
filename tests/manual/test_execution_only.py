#!/usr/bin/env python3

import requests
import json
import time

def get_auth_token():
    """Get authentication token"""
    login_data = {"username": "testadmin", "password": "testpass123"}
    response = requests.post("http://localhost:8000/api/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json().get("data", {}).get("token")
    return None

def test_execution():
    token = get_auth_token()
    if not token:
        print("❌ Failed to get token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    print("🧪 Testing Test Execution on Existing System...")
    
    # First, get existing systems
    systems_response = requests.get("http://localhost:8000/api/systems/", headers=headers)
    if systems_response.status_code != 200:
        print(f"❌ Failed to get systems: {systems_response.text}")
        return
    
    systems = systems_response.json()
    if not systems:
        print("❌ No systems found")
        return
    
    system = systems[0]  # Use the first available system
    system_id = system["system_id"]
    
    print(f"✅ Using system: {system['name']} (ID: {system_id})")
    print(f"   Model: {system['model_name']}")
    
    # Run a test
    test_request = {
        "framework": "GDPR",
        "test_config": {"test_mode": "quick"}
    }
    
    test_response = requests.post(f"http://localhost:8000/api/systems/{system_id}/test", 
                                json=test_request, headers=headers)
    
    if test_response.status_code != 201:
        print(f"❌ Test execution failed: {test_response.text}")
        return
    
    test_result = test_response.json()
    test_id = test_result["test_id"]
    print(f"✅ Started test: ID {test_id}")
    
    # Wait and check results
    print("⏳ Waiting for test completion...")
    time.sleep(8)
    
    results_response = requests.get(f"http://localhost:8000/api/systems/{system_id}/tests", 
                                  headers=headers)
    
    if results_response.status_code == 200:
        results = results_response.json()
        print(f"✅ Retrieved {len(results)} results:")
        
        for result in results:
            print(f"   Test {result['test_id']}: {result['framework']} - {result['status']}")
            if result['score']:
                print(f"     Score: {result['score']}%, Passed: {result['passed']}")
            if result.get('error_message'):
                print(f"     Error: {result['error_message']}")
    else:
        print(f"❌ Failed to get results: {results_response.text}")

if __name__ == "__main__":
    test_execution()