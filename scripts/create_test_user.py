#!/usr/bin/env python3
"""
DEVELOPMENT SCRIPT ONLY
This script creates/updates a test user in the database.
WARNING: Never use this in production environments.
"""

import os
import bcrypt
import subprocess
import json

# Generate hash for a proper password - use environment variable with safe default
password = os.getenv("TEST_USER_PASSWORD", "testpass123")
print(f"Using password from environment or default: {'***' if password else 'default'}")

hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
hash_str = hashed.decode('utf-8')
print(f"Password hash generated successfully")

# Escape the hash for SQL
escaped_hash = hash_str.replace('$', '\\$')

# Create/update the test user
sql_command = f"UPDATE users SET password_hash = '{escaped_hash}' WHERE username = 'testadmin';"
cmd = f'docker exec ai-governance-suite-postgres-1 psql -U postgres -d ai_compliance -c "{sql_command}"'

result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(f"Database update result: {result.stdout}")

# Test login
import requests

login_data = {
    "username": "testadmin",
    "password": password
}

try:
    response = requests.post("http://localhost:8000/api/auth/login", 
                           json=login_data, 
                           headers={"Content-Type": "application/json"})
    print(f"Login response status: {response.status_code}")
    print(f"Login response: {response.json()}")
    
    if response.status_code == 200:
        response_data = response.json()
        token = response_data.get("data", {}).get("token")
        if token:
            print(f"Authentication successful! Token: {token[:20]}...")
            
            # Test models API
            headers = {"Authorization": f"Bearer {token}"}
            
            # Test providers endpoint first
            providers_response = requests.get("http://localhost:8000/api/models/providers/", headers=headers)
            print(f"Providers API response status: {providers_response.status_code}")
            print(f"Providers API response: {providers_response.json()}")
            
            # Test models list
            models_response = requests.get("http://localhost:8000/api/models/", headers=headers)
            print(f"Models API response status: {models_response.status_code}")
            print(f"Models API response: {models_response.json()}")
        else:
            print("No token in response")
except Exception as e:
    print(f"Error testing login: {e}")