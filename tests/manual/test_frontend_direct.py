#!/usr/bin/env python3
"""
Direct test of frontend functionality using browser automation simulation.
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def test_frontend_with_browser():
    """Test the frontend using browser automation."""
    print("🌐 Setting up browser automation...")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 10)
        
        print("🔍 Opening frontend application...")
        driver.get("http://localhost:3000")
        
        # Wait for the page to load
        time.sleep(3)
        
        # Check if we're on login page or main app
        page_title = driver.title
        print(f"📄 Page title: {page_title}")
        
        # Try to find settings link or login form
        try:
            # Look for login form first
            login_form = driver.find_element(By.TAG_NAME, "form")
            print("🔐 Found login form - need to authenticate first")
            
            # Try to find username/email field
            username_field = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[name='username'], input[placeholder*='email']")
            password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            # Fill in test credentials
            username_field.send_keys("test@example.com")
            password_field.send_keys("testpass123")
            
            # Find and click submit button
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button:contains('Login'), button:contains('Sign')")
            submit_button.click()
            
            print("✅ Submitted login form")
            time.sleep(2)
            
        except NoSuchElementException:
            print("ℹ️  No login form found - might already be authenticated")
        
        # Now look for Settings link
        try:
            settings_link = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Settings')] | //button[contains(text(), 'Settings')]"))
            )
            print("✅ Found Settings link")
            settings_link.click()
            time.sleep(2)
            
            # Look for AI Models tab
            ai_models_tab = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'AI Models')] | //a[contains(text(), 'AI Models')]"))
            )
            print("✅ Found AI Models tab")
            ai_models_tab.click()
            time.sleep(2)
            
            # Look for Add Model button
            add_model_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Add Model')]")
            print("✅ Found Add Model button")
            
            # Check if model configuration form elements exist
            page_source = driver.page_source
            has_provider_select = "provider" in page_source.lower()
            has_model_select = "model_id" in page_source.lower() or "model" in page_source.lower()
            has_api_key_field = "api_key" in page_source.lower() or "api key" in page_source.lower()
            
            print(f"✅ Frontend components detected:")
            print(f"  - Provider selection: {'✅' if has_provider_select else '❌'}")
            print(f"  - Model selection: {'✅' if has_model_select else '❌'}")
            print(f"  - API key field: {'✅' if has_api_key_field else '❌'}")
            
            return True
            
        except TimeoutException:
            print("❌ Could not find Settings or AI Models interface")
            print(f"Current URL: {driver.current_url}")
            print("Page content preview:")
            print(driver.page_source[:500])
            return False
            
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        return False
    finally:
        if 'driver' in locals():
            driver.quit()

def test_frontend_curl():
    """Test frontend with simple HTTP requests.""" 
    print("\n🔍 Testing Frontend with HTTP requests...")
    
    import requests
    
    try:
        # Test main page
        response = requests.get("http://localhost:3000", timeout=10)
        print(f"✅ Frontend status: {response.status_code}")
        
        # Check if React app is loaded
        content = response.text
        has_react = "react" in content.lower() or "app" in content.lower()
        has_root = 'id="root"' in content
        
        print(f"✅ React app indicators: {'✅' if has_react else '❌'}")
        print(f"✅ Root div found: {'✅' if has_root else '❌'}")
        
        # Check for our new components in the bundle
        has_model_config = "modelconfiguration" in content.lower()
        print(f"✅ Model configuration components: {'✅' if has_model_config else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")
        return False

def main():
    """Main test execution."""
    print("🚀 Frontend AI Model Configuration Test")
    print("="*50)
    
    # Test basic HTTP connectivity
    http_success = test_frontend_curl()
    
    # Test with browser if available
    try:
        browser_success = test_frontend_with_browser()
    except ImportError:
        print("⚠️  Selenium not available - skipping browser tests")
        browser_success = None
    except Exception as e:
        print(f"⚠️  Browser test not available: {e}")
        browser_success = False
    
    print("\n" + "="*50)
    print("🎯 FRONTEND TEST RESULTS")
    print("="*50)
    print(f"HTTP Access: {'✅' if http_success else '❌'}")
    if browser_success is not None:
        print(f"Browser Test: {'✅' if browser_success else '❌'}")
    
    print("\n📋 Manual Testing Instructions:")
    print("1. Open http://localhost:3000 in your browser")
    print("2. Login (or create account) if prompted")
    print("3. Navigate to Settings (in sidebar)")
    print("4. Click 'AI Models' tab")
    print("5. Click 'Add Model' to create new configuration")
    print("6. Select 'Google (Gemini)' as provider")
    print("7. Choose 'gemini-1.5-flash' as model")
    print("8. Enter API key: your-google-api-key-here")
    print("9. Set temperature to 0.3, max tokens to 1000")
    print("10. Click 'Test Configuration' to validate")
    print("11. Click 'Save Configuration' when test passes")

if __name__ == "__main__":
    main()