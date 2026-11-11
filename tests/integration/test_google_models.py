#!/usr/bin/env python3
"""
Test Google Gemini API to verify available model IDs
"""

import os
import httpx
import json

def test_google_models():
    """Test which Google model IDs work"""
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("⚠ GOOGLE_API_KEY not set")
        return
    
    # Common Google model IDs to test
    model_ids = [
        "gemini-1.5-flash",
        "gemini-1.5-pro", 
        "gemini-1.0-pro",
        "gemini-2.5-flash",  # The one causing error
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-1.0-pro"
    ]
    
    test_payload = {
        "contents": [{"parts": [{"text": "Say 'test successful'"}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 50,
        }
    }
    
    print("Testing Google Gemini model IDs:")
    print("=" * 50)
    
    for model_id in model_ids:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
            
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=test_payload)
                
                if response.status_code == 200:
                    result = response.json()
                    if "candidates" in result:
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        print(f"✅ {model_id}: SUCCESS - {content.strip()}")
                    else:
                        print(f"✅ {model_id}: SUCCESS (no content)")
                else:
                    print(f"❌ {model_id}: HTTP {response.status_code}")
                    if response.status_code == 400:
                        try:
                            error_detail = response.json()
                            print(f"   Error: {error_detail}")
                        except:
                            print(f"   Error: {response.text}")
                            
        except Exception as e:
            print(f"❌ {model_id}: {str(e)}")
    
    # Also test listing available models
    print(f"\n🔍 Attempting to list available models:")
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        with httpx.Client(timeout=30) as client:
            response = client.get(list_url)
            if response.status_code == 200:
                models = response.json()
                print("Available models:")
                for model in models.get("models", []):
                    name = model.get("name", "Unknown")
                    description = model.get("description", "No description")
                    print(f"  - {name}: {description}")
            else:
                print(f"Failed to list models: HTTP {response.status_code}")
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    test_google_models()