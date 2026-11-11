#!/usr/bin/env python3
"""
Test script for AI Systems API through the gateway
"""

import requests
import json

def test_systems_api():
    """Test the systems API endpoints"""
    print("🔍 Testing AI Systems API through Gateway...")
    
    base_url = "http://localhost:8000/api"
    
    # Test auth first (using provided credentials)
    print("\n🔐 Testing Authentication...")
    auth_response = requests.post(f"{base_url}/auth/login", json={
        "username": "000",
        "password": "00000000"
    })
    
    if auth_response.status_code == 200:
        print("✅ Authentication successful")
        auth_data = auth_response.json()
        print(f"   Response structure: {list(auth_data.keys())}")
        
        # Handle different possible response structures
        if "data" in auth_data and "token" in auth_data["data"]:
            token = auth_data["data"]["token"]
        elif "data" in auth_data and "access_token" in auth_data["data"]:
            token = auth_data["data"]["access_token"]
        elif "access_token" in auth_data:
            token = auth_data["access_token"]
        elif "token" in auth_data:
            token = auth_data["token"]
        else:
            print(f"   Full response: {auth_data}")
            print("❌ Could not find access token in response")
            return False
            
        headers = {"Authorization": f"Bearer {token}"}
    else:
        print(f"❌ Authentication failed: {auth_response.status_code}")
        print(f"   Response: {auth_response.text}")
        return False
    
    # Test systems endpoint
    print("\n📋 Testing Systems Endpoint...")
    systems_response = requests.get(f"{base_url}/systems", headers=headers)
    
    if systems_response.status_code == 200:
        systems = systems_response.json()
        print(f"✅ Systems endpoint working - found {len(systems)} systems")
        
        for system in systems:
            print(f"   - {system['name']}: {len(system['models'])} models")
            print(f"     Frameworks: {system['compliance_frameworks']}")
            print(f"     Model: {system['model_name']}")
    else:
        print(f"❌ Systems endpoint failed: {systems_response.status_code}")
        print(f"   Response: {systems_response.text}")
        return False
    
    # Test creating a new system
    print("\n➕ Testing System Creation...")
    new_system_data = {
        "name": "API Test System",
        "description": "System created via API test",
        "model_config_id": 11,  # Using the test model we created
        "compliance_frameworks": ["GDPR", "CCPA"],
        "industry": "technology"
    }
    
    create_response = requests.post(f"{base_url}/systems", 
                                   json=new_system_data, 
                                   headers=headers)
    
    if create_response.status_code == 201:
        new_system = create_response.json()
        print(f"✅ System creation successful - ID: {new_system['system_id']}")
        print(f"   Name: {new_system['name']}")
        print(f"   Model: {new_system['model_name']}")
        system_id = new_system['system_id']
    else:
        print(f"❌ System creation failed: {create_response.status_code}")
        print(f"   Response: {create_response.text}")
        return False
    
    # Test getting specific system
    print(f"\n🔍 Testing Get Specific System (ID: {system_id})...")
    get_response = requests.get(f"{base_url}/systems/{system_id}", headers=headers)
    
    if get_response.status_code == 200:
        system_detail = get_response.json()
        print(f"✅ Get system successful")
        print(f"   Name: {system_detail['name']}")
        print(f"   Models: {len(system_detail['models'])}")
    else:
        print(f"❌ Get system failed: {get_response.status_code}")
        print(f"   Response: {get_response.text}")
        return False
    
    print("\n🎉 All API tests passed!")
    print("\n📝 Summary:")
    print("   ✅ Authentication works")
    print("   ✅ Systems listing works")
    print("   ✅ System creation works")
    print("   ✅ System retrieval works")
    print("   ✅ Data structure matches frontend expectations")
    
    return True

if __name__ == "__main__":
    success = test_systems_api()
    
    if success:
        print("\n✅ API TESTING COMPLETE - All endpoints working correctly!")
        print("\n🎯 Ready for frontend testing:")
        print("   1. Navigate to http://localhost:3000")
        print("   2. Login with username: '000', password: '00000000'")
        print("   3. Go to Compliance → Systems")
        print("   4. Create, view, and test AI systems")
    else:
        print("\n❌ API TESTING FAILED - Issues found that need to be resolved")