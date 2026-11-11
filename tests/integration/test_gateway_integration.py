#!/usr/bin/env python3
"""
Test gateway integration with Unified AI API
Tests the actual gateway service endpoints for model configuration
"""

import asyncio
import asyncpg
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GatewayTester:
    """Test gateway integration with Unified AI API"""
    
    def __init__(self):
        self.db_pool = None
        
    async def setup_database_connection(self):
        """Setup database connection"""
        try:
            database_url = "postgresql://postgres:password@localhost:5432/ai_compliance"
            self.db_pool = await asyncpg.create_pool(database_url)
            logger.info("✓ Database connection established")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            return False
    
    async def test_models_service_import(self):
        """Test that ModelsService can be imported and initialized"""
        print("\n=== Testing ModelsService Import ===")
        
        try:
            # Import the models service from gateway
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gateway', 'src', 'shared'))
            
            from models_service import ModelsService
            
            # Try to initialize with database pool
            if not self.db_pool:
                await self.setup_database_connection()
            
            if self.db_pool:
                models_service = ModelsService(self.db_pool)
                logger.info("✓ ModelsService imported and initialized successfully")
                return models_service
            else:
                logger.error("✗ Cannot test ModelsService without database connection")
                return None
                
        except Exception as e:
            logger.error(f"✗ Failed to import/initialize ModelsService: {e}")
            return None
    
    async def test_provider_listing(self, models_service):
        """Test provider listing through ModelsService"""
        print("\n=== Testing Provider Listing ===")
        
        try:
            providers = await models_service.get_providers()
            logger.info(f"✓ Retrieved {len(providers)} providers:")
            for provider in providers:
                logger.info(f"  - {provider['name']}: {provider['description']}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to get providers: {e}")
            return False
    
    async def test_model_configuration_crud(self, models_service):
        """Test CRUD operations for model configurations"""
        print("\n=== Testing Model Configuration CRUD ===")
        
        try:
            # Create a test user first
            async with self.db_pool.acquire() as conn:
                # Check if test user exists
                test_user = await conn.fetchrow(
                    "SELECT user_id FROM users WHERE email = $1", 
                    "test@example.com"
                )
                
                if not test_user:
                    # Create test user
                    test_user = await conn.fetchrow("""
                        INSERT INTO users (username, email, password_hash, full_name, role)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING user_id
                    """, "testuser", "test@example.com", "dummy_hash", "Test User", "user")
                
                user_id = test_user['user_id']
                logger.info(f"✓ Using test user ID: {user_id}")
            
            # Import request model
            from models_service import AIModelConfigRequest, ProviderType, UsageType
            
            # Test creating a model configuration
            test_config = AIModelConfigRequest(
                name="Test OpenAI Config",
                description="Test configuration for testing",
                provider=ProviderType.OPENAI,
                model_id="gpt-3.5-turbo",
                api_key="test-key-12345",
                temperature=0.7,
                max_tokens=1000,
                usage_type=UsageType.TEST_SUBJECT
            )
            
            # Create the configuration
            created_config = await models_service.create_model(test_config, user_id)
            logger.info(f"✓ Created model configuration: {created_config.name} (ID: {created_config.id})")
            
            # Test retrieving the configuration
            retrieved_config = await models_service.get_model(created_config.id, user_id)
            if retrieved_config:
                logger.info(f"✓ Retrieved model configuration: {retrieved_config.name}")
            else:
                logger.error("✗ Failed to retrieve created configuration")
                return False
            
            # Test listing all configurations
            all_configs = await models_service.get_models(user_id)
            logger.info(f"✓ Listed {len(all_configs)} model configurations")
            
            # Test updating the configuration
            test_config.name = "Updated Test OpenAI Config"
            test_config.temperature = 0.8
            updated_config = await models_service.update_model(created_config.id, test_config, user_id)
            if updated_config and updated_config.name == "Updated Test OpenAI Config":
                logger.info(f"✓ Updated model configuration: {updated_config.name}")
            else:
                logger.error("✗ Failed to update configuration")
                return False
            
            # Test deleting the configuration
            deleted = await models_service.delete_model(created_config.id, user_id)
            if deleted:
                logger.info("✓ Deleted model configuration")
            else:
                logger.error("✗ Failed to delete configuration")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"✗ CRUD test failed: {e}")
            return False
    
    async def test_model_testing_functionality(self, models_service):
        """Test model testing functionality"""
        print("\n=== Testing Model Testing Functionality ===")
        
        try:
            # Test with mock configuration data (no actual API call)
            test_config_data = {
                "provider": "openai",
                "model_id": "gpt-3.5-turbo",
                "api_key": "invalid-test-key",  # Invalid key to test error handling
                "temperature": 0.7,
                "max_tokens": 100,
                "timeout": 30
            }
            
            # Test the model (should fail gracefully due to invalid API key)
            test_result = await models_service.test_model(test_config_data, 1)
            
            # Check that we get a proper response structure
            if hasattr(test_result, 'success') and hasattr(test_result, 'error_message'):
                if not test_result.success and test_result.error_message:
                    logger.info(f"✓ Model test correctly failed with invalid credentials: {test_result.error_message[:100]}...")
                else:
                    logger.info(f"✓ Model test completed: success={test_result.success}")
            else:
                logger.error("✗ Model test returned unexpected response structure")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Model testing functionality failed: {e}")
            return False
    
    async def cleanup_database(self):
        """Clean up test data"""
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    # Clean up test user and related data
                    await conn.execute("DELETE FROM ai_model_configs WHERE created_by IN (SELECT user_id FROM users WHERE email = 'test@example.com')")
                    await conn.execute("DELETE FROM users WHERE email = 'test@example.com'")
                await self.db_pool.close()
                logger.info("✓ Database cleanup completed")
        except Exception as e:
            logger.error(f"⚠ Database cleanup failed: {e}")
    
    async def run_all_tests(self):
        """Run all gateway integration tests"""
        print("🚀 Starting Gateway Integration Tests")
        print("=" * 60)
        
        results = {
            "database_connection": False,
            "models_service_import": False,
            "provider_listing": False,
            "crud_operations": False,
            "model_testing": False
        }
        
        try:
            # Test database connection
            results["database_connection"] = await self.setup_database_connection()
            
            if results["database_connection"]:
                # Test ModelsService import
                models_service = await self.test_models_service_import()
                results["models_service_import"] = models_service is not None
                
                if models_service:
                    # Test provider listing
                    results["provider_listing"] = await self.test_provider_listing(models_service)
                    
                    # Test CRUD operations
                    results["crud_operations"] = await self.test_model_configuration_crud(models_service)
                    
                    # Test model testing functionality
                    results["model_testing"] = await self.test_model_testing_functionality(models_service)
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
        
        finally:
            await self.cleanup_database()
        
        return results
    
    def generate_report(self, results: Dict[str, bool]) -> str:
        """Generate test report"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("GATEWAY INTEGRATION TEST REPORT")
        report.append("=" * 60)
        report.append(f"Test run at: {datetime.now().isoformat()}")
        report.append("")
        
        total_tests = len(results)
        passed_tests = sum(1 for success in results.values() if success)
        
        for test_name, success in results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            report.append(f"  {status} {test_name.replace('_', ' ').title()}")
        
        report.append("\n" + "=" * 60)
        report.append("SUMMARY")
        report.append("=" * 60)
        report.append(f"Total tests: {total_tests}")
        report.append(f"Passed: {passed_tests}")
        report.append(f"Failed: {total_tests - passed_tests}")
        report.append(f"Success rate: {(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%")
        
        if passed_tests == total_tests:
            report.append("\n🎉 ALL GATEWAY TESTS PASSED! System is ready for use.")
        else:
            report.append(f"\n⚠️  {total_tests - passed_tests} tests failed. Please check the implementation.")
        
        return "\n".join(report)

async def main():
    """Main test execution function"""
    tester = GatewayTester()
    
    # Run all tests
    results = await tester.run_all_tests()
    
    # Generate and print report
    report = tester.generate_report(results)
    print(report)
    
    # Save results
    with open("gateway_integration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    with open("gateway_integration_test_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n📄 Results saved to: gateway_integration_test_results.json")
    print(f"📄 Report saved to: gateway_integration_test_report.txt")

if __name__ == "__main__":
    asyncio.run(main())