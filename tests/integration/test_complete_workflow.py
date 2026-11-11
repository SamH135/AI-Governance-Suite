#!/usr/bin/env python3

import requests
import json
import time
from datetime import datetime

def get_auth_token():
    """Get authentication token"""
    login_data = {
        "username": "testadmin", 
        "password": "testpass123"
    }
    
    response = requests.post("http://localhost:8000/api/auth/login", 
                           json=login_data, 
                           headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        response_data = response.json()
        return response_data.get("data", {}).get("token")
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_complete_workflow():
    """Test the complete AI Governance Suite workflow"""
    print("🚀 Testing Complete AI Governance Suite Workflow")
    print("=" * 80)
    
    # Get auth token
    token = get_auth_token()
    if not token:
        print("❌ Failed to get authentication token")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # STEP 1: Create AI Model Configuration
        print("\n📊 STEP 1: Creating AI Model Configuration...")
        model_data = {
            "name": f"Healthcare GPT-4 Model {int(time.time())}",  # Make name unique
            "description": "GPT-4 model optimized for healthcare compliance testing",
            "provider": "openai",
            "model_id": "gpt-4",
            "api_key": "sk-test-healthcare-key-12345", 
            "temperature": 0.3,
            "max_tokens": 2000,
            "timeout": 45,
            "tags": ["healthcare", "compliance", "production"]
        }
        
        model_response = requests.post("http://localhost:8000/api/models/", 
                                     json=model_data, 
                                     headers=headers)
        
        if model_response.status_code != 201:
            print(f"❌ Model creation failed: {model_response.text}")
            return
        
        model_result = model_response.json()
        model_id = model_result.get("id")
        print(f"✅ Created model configuration: ID {model_id}, Name: {model_result.get('name')}")
        
        # STEP 2: Create AI System linked to Model
        print("\n🤖 STEP 2: Creating AI System...")
        system_data = {
            "name": f"MedAssist Pro {int(time.time())}",  # Make name unique
            "description": "AI-powered medical diagnosis assistance system with HIPAA compliance",
            "version": "2.1.0",
            "system_type": "llm",
            "compliance_frameworks": ["HIPAA", "FDA", "GDPR"],
            "model_config_id": model_id,
            "industry": "healthcare"
        }
        
        system_response = requests.post("http://localhost:8000/api/systems/", 
                                      json=system_data, 
                                      headers=headers)
        
        if system_response.status_code != 201:
            print(f"❌ AI System creation failed: {system_response.text}")
            return
        
        system_result = system_response.json()
        system_id = system_result.get("system_id")
        print(f"✅ Created AI System: ID {system_id}, Name: {system_result.get('name')}")
        print(f"   🔗 Linked to model: {system_result.get('model_name')}")
        print(f"   📋 Compliance frameworks: {system_result.get('compliance_frameworks')}")
        
        # STEP 3: Run HIPAA Compliance Test
        print("\n🔒 STEP 3: Running HIPAA Compliance Test...")
        test_request = {
            "framework": "HIPAA",
            "test_config": {
                "test_mode": "comprehensive",
                "include_phi_tests": True,
                "security_level": "high"
            }
        }
        
        test_response = requests.post(f"http://localhost:8000/api/systems/{system_id}/test", 
                                    json=test_request, 
                                    headers=headers)
        
        if test_response.status_code != 201:
            print(f"❌ HIPAA test execution failed: {test_response.text}")
            return
        
        test_result = test_response.json()
        hipaa_test_id = test_result.get("test_id")
        print(f"✅ Started HIPAA compliance test: ID {hipaa_test_id}")
        print(f"   📊 Status: {test_result.get('status')}")
        print(f"   💬 Message: {test_result.get('message')}")
        
        # STEP 4: Run FDA Compliance Test  
        print("\n🏥 STEP 4: Running FDA Compliance Test...")
        fda_test_request = {
            "framework": "FDA",
            "test_config": {
                "test_mode": "clinical_validation",
                "device_class": "II",
                "risk_category": "moderate"
            }
        }
        
        fda_test_response = requests.post(f"http://localhost:8000/api/systems/{system_id}/test", 
                                        json=fda_test_request, 
                                        headers=headers)
        
        if fda_test_response.status_code != 201:
            print(f"❌ FDA test execution failed: {fda_test_response.text}")
            return
        
        fda_result = fda_test_response.json()
        fda_test_id = fda_result.get("test_id")
        print(f"✅ Started FDA compliance test: ID {fda_test_id}")
        print(f"   📊 Status: {fda_result.get('status')}")
        
        # STEP 5: Run GDPR Compliance Test
        print("\n🛡️ STEP 5: Running GDPR Compliance Test...")
        gdpr_test_request = {
            "framework": "GDPR",
            "test_config": {
                "test_mode": "data_privacy",
                "include_consent_tests": True,
                "data_retention_check": True
            }
        }
        
        gdpr_test_response = requests.post(f"http://localhost:8000/api/systems/{system_id}/test", 
                                         json=gdpr_test_request, 
                                         headers=headers)
        
        if gdpr_test_response.status_code != 201:
            print(f"❌ GDPR test execution failed: {gdpr_test_response.text}")
            return
        
        gdpr_result = gdpr_test_response.json()
        gdpr_test_id = gdpr_result.get("test_id")
        print(f"✅ Started GDPR compliance test: ID {gdpr_test_id}")
        
        # STEP 6: Wait for tests to complete
        print(f"\n⏳ STEP 6: Waiting for test completion (5 seconds)...")
        time.sleep(5)
        
        # STEP 7: Retrieve Test Results
        print("\n📈 STEP 7: Retrieving Test Results...")
        results_response = requests.get(f"http://localhost:8000/api/systems/{system_id}/tests", 
                                      headers=headers)
        
        if results_response.status_code != 200:
            print(f"❌ Failed to retrieve test results: {results_response.text}")
            return
        
        test_results = results_response.json()
        print(f"✅ Retrieved {len(test_results)} test results")
        
        # Display results summary
        print(f"\n📊 TEST RESULTS SUMMARY:")
        print("-" * 60)
        
        for result in test_results:
            framework = result.get("framework")
            score = result.get("score")
            passed = result.get("passed")
            status = result.get("status")
            
            status_emoji = "✅" if passed else "❌" if status == "completed" else "⏳"
            
            print(f"{status_emoji} {framework} Framework:")
            print(f"   Score: {score}%" if score else f"   Status: {status}")
            print(f"   Result: {'PASSED' if passed else 'FAILED' if status == 'completed' else 'RUNNING'}")
            
            details = result.get("details", {})
            if details:
                risk_level = details.get("risk_level", "Unknown")
                tests_run = details.get("tests_run", 0)
                tests_passed = details.get("tests_passed", 0)
                print(f"   Risk Level: {risk_level}")
                print(f"   Tests: {tests_passed}/{tests_run} passed")
            
            recommendations = result.get("recommendations", [])
            if recommendations:
                print(f"   Recommendations: {len(recommendations)} items")
                for i, rec in enumerate(recommendations[:2], 1):  # Show first 2
                    print(f"     {i}. {rec}")
            print()
        
        # STEP 8: Test another system type
        print("🔬 STEP 8: Testing Different System Type...")
        
        # Create a different system for comparison
        fintech_data = {
            "name": f"CreditScore AI {int(time.time())}",  # Make name unique
            "description": "AI system for credit scoring and risk assessment",
            "version": "1.5.0", 
            "system_type": "ml",
            "compliance_frameworks": ["GDPR", "CCPA", "SOC2"],
            "model_config_id": model_id,  # Reuse same model
            "industry": "fintech"
        }
        
        fintech_response = requests.post("http://localhost:8000/api/systems/", 
                                       json=fintech_data, 
                                       headers=headers)
        
        if fintech_response.status_code == 201:
            fintech_result = fintech_response.json()
            fintech_system_id = fintech_result.get("system_id")
            print(f"✅ Created FinTech AI System: {fintech_result.get('name')}")
            
            # Run GDPR test on fintech system
            fintech_test_response = requests.post(
                f"http://localhost:8000/api/systems/{fintech_system_id}/test", 
                json={"framework": "GDPR"}, 
                headers=headers
            )
            
            if fintech_test_response.status_code == 201:
                print("✅ Started GDPR test on FinTech system")
        
        # STEP 9: Verify Model-System Integration
        print("\n🔗 STEP 9: Verifying Model-System Integration...")
        
        # Get system details to confirm model linkage
        system_details = requests.get(f"http://localhost:8000/api/systems/{system_id}", 
                                    headers=headers)
        
        if system_details.status_code == 200:
            details = system_details.json()
            print(f"✅ System Integration Verified:")
            print(f"   System: {details.get('name')}")
            print(f"   Model: {details.get('model_name')}")
            print(f"   Model ID: {details.get('model_config_id')}")
            print(f"   Industry: {details.get('industry')}")
            print(f"   Frameworks: {details.get('compliance_frameworks')}")
        
        print(f"\n🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("✅ Model Configuration API - WORKING")
        print("✅ AI Systems CRUD API - WORKING") 
        print("✅ Test Execution Integration - WORKING")
        print("✅ Model-System Linking - WORKING")
        print("✅ Multi-Framework Testing - WORKING")
        print("✅ Results Storage & Retrieval - WORKING")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Workflow failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_workflow()