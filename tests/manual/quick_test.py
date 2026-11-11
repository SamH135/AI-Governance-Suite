#!/usr/bin/env python3

import requests
import time

# Quick test with authentication and execution
token_response = requests.post("http://localhost:8000/api/auth/login", 
                             json={"username": "testadmin", "password": "testpass123"})
token = token_response.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

# Run a simple test
test_response = requests.post("http://localhost:8000/api/systems/2/test", 
                            json={"framework": "GDPR"}, headers=headers)
print(f"Test creation: {test_response.status_code}")
if test_response.status_code == 201:
    result = test_response.json()
    print(f"Test ID: {result['test_id']}")
else:
    print(f"Error: {test_response.text}")

print("Waiting 8 seconds for completion...")
time.sleep(8)

# Check logs for any error details