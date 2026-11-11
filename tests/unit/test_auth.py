#!/usr/bin/env python3

import bcrypt
import requests
import json

# Test password verification
stored_hash = "$2b$12$0Zxzfi1BXiS4kq6MMSwwZe3.qmWwtt30S4tBAAZzPHu4qXJHG73J."
test_password = "secret"

# Verify the hash
result = bcrypt.checkpw(test_password.encode('utf-8'), stored_hash.encode('utf-8'))
print(f"Password verification result: {result}")

if result:
    print("Password hash is correct, testing login...")
    
    # Test login
    login_data = {
        "username": "testadmin",
        "password": "secret"
    }
    
    try:
        response = requests.post("http://localhost:8000/api/auth/login", 
                               json=login_data, 
                               headers={"Content-Type": "application/json"})
        print(f"Login response status: {response.status_code}")
        print(f"Login response: {response.json()}")
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                print(f"Authentication successful! Token: {token[:20]}...")
                
                # Test models API
                headers = {"Authorization": f"Bearer {token}"}
                models_response = requests.get("http://localhost:8000/api/models/", headers=headers)
                print(f"Models API response status: {models_response.status_code}")
                print(f"Models API response: {models_response.text}")
            else:
                print("No token in response")
    except Exception as e:
        print(f"Error testing login: {e}")
else:
    print("Password hash verification failed!")