"""Core test execution service with orchestration capabilities."""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import structlog
import httpx

from services.shared.models import TestExecution, AISystem
from services.shared.schemas import TestStatus, TestProgressUpdate
from services.shared.exceptions import ValidationError, ExternalServiceError
from services.shared.redis_client import redis_client
from services.shared.websocket_manager import websocket_notifier

logger = structlog.get_logger()

class TestType(str, Enum):
    COMPLIANCE = "compliance"
    PROMPT_GENERATION = "prompt_generation"
    DOCUMENT_GENERATION = "document_generation"
    INTEGRATED = "integrated"

class TestExecutor:
    """Unified test execution service with orchestration capabilities."""
    
    def __init__(self):
        self.http_client = None
        self.service_urls = {}
        self.initialized = False
        self.running_executions = {}
        
    async def initialize(self):
        """Initialize the test executor."""
        
        if self.initialized:
            return
            
        try:
            # Initialize HTTP client
            self.http_client = httpx.AsyncClient(timeout=300.0)
            
            # Service URLs
            self.service_urls = {
                "compliance": "http://compliance-service:8000",
                "prompts": "http://prompt-service:8000", 
                "documents": "http://document-service:8000"
            }
            
            self.initialized = True
            logger.info("Test executor initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize test executor", error=str(e))
            raise ExternalServiceError("TestExecutor", f"Initialization failed: {str(e)}")
    
    async def close(self):
        """Close test executor connections."""
        if self.http_client:
            await self.http_client.aclose()
            logger.info("Test executor connections closed")
    
    async def execute_test_suite(
        self,
        execution: TestExecution,
        ai_system: AISystem,
        test_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a complete test suite with orchestration."""
        
        if not self.initialized:
            await self.initialize()
            
        execution_id = execution.execution_id
        
        try:
            logger.info("Starting test suite execution", 
                       execution_id=execution_id,
                       suite_name=execution.test_suite_name)
            
            # Store execution in running executions
            self.running_executions[execution_id] = {
                "status": TestStatus.RUNNING,
                "progress": 0,
                "started_at": datetime.utcnow(),
                "current_test": None,
                "results": []
            }
            
            # Determine test types to run
            test_types = self._determine_test_types(test_config)
            total_tests = len(test_types)
            
            # Update total tests
            await self._update_execution_progress(
                execution_id, 0, total_tests, "Initializing test suite"
            )
            
            # Execute tests based on type
            all_results = []
            
            for i, test_type in enumerate(test_types):
                try:
                    current_progress = int((i / total_tests) * 100)
                    await self._update_execution_progress(
                        execution_id, current_progress, total_tests, f"Running {test_type} tests"
                    )
                    
                    if test_type == TestType.COMPLIANCE:
                        results = await self._execute_compliance_tests(ai_system, test_config)
                    elif test_type == TestType.PROMPT_GENERATION:
                        results = await self._execute_prompt_tests(ai_system, test_config)
                    elif test_type == TestType.DOCUMENT_GENERATION:
                        results = await self._execute_document_tests(ai_system, test_config)
                    elif test_type == TestType.INTEGRATED:
                        results = await self._execute_integrated_tests(ai_system, test_config)
                    else:
                        results = []
                    
                    all_results.extend(results)
                    
                    # Update progress
                    self.running_executions[execution_id]["results"].extend(results)
                    
                except Exception as e:
                    logger.error("Test type execution failed", 
                               test_type=test_type, error=str(e))
                    # Continue with other tests
                    all_results.append({
                        "test_type": test_type,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            # Complete execution
            await self._update_execution_progress(
                execution_id, 100, total_tests, "Test suite completed"
            )
            
            # Calculate overall results
            execution_summary = self._calculate_execution_summary(all_results)
            
            # Clean up
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]
            
            logger.info("Test suite execution completed", 
                       execution_id=execution_id,
                       total_tests=len(all_results),
                       success_rate=execution_summary.get("success_rate", 0))
            
            return {
                "execution_id": execution_id,
                "status": "completed",
                "summary": execution_summary,
                "results": all_results,
                "completed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Test suite execution failed", 
                        execution_id=execution_id, error=str(e))
            
            # Update execution status
            await self._update_execution_progress(
                execution_id, 0, 0, f"Execution failed: {str(e)}", TestStatus.FAILED
            )
            
            # Clean up
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]
            
            raise ValidationError(f"Test suite execution failed: {str(e)}")
    
    def _determine_test_types(self, test_config: Dict[str, Any]) -> List[TestType]:
        """Determine which test types to run based on configuration."""
        
        test_types = []
        
        # Check configuration for enabled test types
        if test_config.get("compliance_tests", True):
            test_types.append(TestType.COMPLIANCE)
            
        if test_config.get("prompt_tests", False):
            test_types.append(TestType.PROMPT_GENERATION)
            
        if test_config.get("document_tests", False):
            test_types.append(TestType.DOCUMENT_GENERATION)
            
        if test_config.get("integrated_tests", False):
            test_types.append(TestType.INTEGRATED)
        
        # Default to compliance if nothing specified
        if not test_types:
            test_types.append(TestType.COMPLIANCE)
            
        return test_types
    
    async def _execute_compliance_tests(
        self, 
        ai_system: AISystem, 
        test_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute compliance tests via compliance service."""
        
        try:
            # Prepare compliance test request
            compliance_config = {
                "system_id": ai_system.system_id,
                "framework": test_config.get("framework", "GDPR"),
                "test_config": test_config.get("compliance_config", {})
            }
            
            # Call compliance service
            response = await self.http_client.post(
                f"{self.service_urls['compliance']}/compliance/evaluate",
                json=compliance_config
            )
            
            if response.status_code == 200:
                result = response.json()
                return [{
                    "test_type": "compliance",
                    "status": "completed",
                    "framework": compliance_config["framework"],
                    "overall_score": result.get("data", {}).get("overall_score", 0),
                    "risk_level": result.get("data", {}).get("risk_assessment", "unknown"),
                    "test_results": result.get("data", {}).get("test_results", []),
                    "timestamp": datetime.utcnow().isoformat()
                }]
            else:
                logger.error("Compliance service error", 
                           status_code=response.status_code,
                           response=response.text)
                return [{
                    "test_type": "compliance",
                    "status": "failed",
                    "error": f"Service error: {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }]
                
        except Exception as e:
            logger.error("Compliance test execution failed", error=str(e))
            return [{
                "test_type": "compliance",
                "status": "failed", 
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }]
    
    async def _execute_prompt_tests(
        self,
        ai_system: AISystem,
        test_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute prompt generation tests."""
        
        try:
            # Prepare prompt generation request
            prompt_config = {
                "requirements": test_config.get("prompt_requirements", "Generate test prompts"),
                "system_id": ai_system.system_id,
                "count": test_config.get("prompt_count", 3),
                "optimization_params": test_config.get("prompt_optimization", {})
            }
            
            # Call prompt service
            response = await self.http_client.post(
                f"{self.service_urls['prompts']}/prompts/generate",
                json=prompt_config
            )
            
            if response.status_code == 200:
                result = response.json()
                prompts = result.get("data", [])
                
                return [{
                    "test_type": "prompt_generation",
                    "status": "completed",
                    "prompts_generated": len(prompts),
                    "average_quality": sum(p.get("quality_score", 0) for p in prompts) / len(prompts) if prompts else 0,
                    "prompts": prompts,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            else:
                return [{
                    "test_type": "prompt_generation",
                    "status": "failed",
                    "error": f"Service error: {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }]
                
        except Exception as e:
            logger.error("Prompt test execution failed", error=str(e))
            return [{
                "test_type": "prompt_generation",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }]
    
    async def _execute_document_tests(
        self,
        ai_system: AISystem,
        test_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute document generation tests."""
        
        try:
            # Get available templates first
            templates_response = await self.http_client.get(
                f"{self.service_urls['documents']}/templates/"
            )
            
            if templates_response.status_code != 200:
                return [{
                    "test_type": "document_generation",
                    "status": "failed",
                    "error": "Could not fetch templates",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            
            templates = templates_response.json().get("data", [])
            if not templates:
                return [{
                    "test_type": "document_generation", 
                    "status": "skipped",
                    "reason": "No templates available",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            
            # Use first available template
            template = templates[0]
            
            # Prepare document generation request
            doc_config = {
                "template_id": template["template_id"],
                "system_id": ai_system.system_id,
                "title": f"Test Document for {ai_system.name}",
                "content": test_config.get("document_data", {}),
                "format": test_config.get("document_format", "html")
            }
            
            # Call document service
            response = await self.http_client.post(
                f"{self.service_urls['documents']}/documents/generate",
                json=doc_config
            )
            
            if response.status_code == 200:
                result = response.json()
                document = result.get("data", {})
                
                return [{
                    "test_type": "document_generation",
                    "status": "completed",
                    "document_id": document.get("document_id"),
                    "template_used": template["name"],
                    "format": doc_config["format"],
                    "timestamp": datetime.utcnow().isoformat()
                }]
            else:
                return [{
                    "test_type": "document_generation",
                    "status": "failed",
                    "error": f"Service error: {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }]
                
        except Exception as e:
            logger.error("Document test execution failed", error=str(e))
            return [{
                "test_type": "document_generation",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }]
    
    async def _execute_integrated_tests(
        self,
        ai_system: AISystem,
        test_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute integrated tests across multiple services."""
        
        try:
            # Integrated test: Generate prompts, test compliance, create documentation
            results = []
            
            # Step 1: Generate prompts
            prompt_results = await self._execute_prompt_tests(ai_system, test_config)
            results.extend(prompt_results)
            
            # Step 2: Test compliance with generated prompts
            if prompt_results and prompt_results[0].get("status") == "completed":
                compliance_results = await self._execute_compliance_tests(ai_system, test_config)
                results.extend(compliance_results)
                
                # Step 3: Generate documentation based on results
                doc_results = await self._execute_document_tests(ai_system, test_config)
                results.extend(doc_results)
            
            # Create integrated summary
            integrated_summary = {
                "test_type": "integrated",
                "status": "completed",
                "steps_completed": len(results),
                "overall_success": all(r.get("status") == "completed" for r in results),
                "sub_results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return [integrated_summary]
            
        except Exception as e:
            logger.error("Integrated test execution failed", error=str(e))
            return [{
                "test_type": "integrated",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }]
    
    async def _update_execution_progress(
        self,
        execution_id: int,
        progress: int,
        total_tests: int,
        current_test: str,
        status: TestStatus = TestStatus.RUNNING
    ):
        """Update execution progress and broadcast via WebSocket."""
        
        # Update local state
        if execution_id in self.running_executions:
            self.running_executions[execution_id].update({
                "progress": progress,
                "current_test": current_test,
                "status": status,
                "updated_at": datetime.utcnow()
            })
        
        # Create progress update
        progress_update = TestProgressUpdate(
            execution_id=execution_id,
            progress=progress,
            current_test=current_test,
            status=status,
            results=self.running_executions.get(execution_id, {}).get("results", [])
        )
        
        # Broadcast via Redis pub/sub for WebSocket
        try:
            await redis_client.publish(
                f"test_progress:{execution_id}",
                progress_update.model_dump_json()
            )
            
            # Also use WebSocket notifier for real-time updates
            await websocket_notifier.notify_test_progress(
                user_id=str(execution_id),  # In real implementation, get actual user_id
                test_id=str(execution_id),
                progress=float(progress),
                status=status.value,
                details={
                    "current_test": current_test,
                    "total_tests": total_tests,
                    "results_count": len(self.running_executions.get(execution_id, {}).get("results", []))
                }
            )
        except Exception as e:
            logger.warning("Failed to broadcast progress update", error=str(e))
    
    def _calculate_execution_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for test execution."""
        
        if not results:
            return {
                "total_tests": 0,
                "success_rate": 0,
                "failed_tests": 0,
                "completed_tests": 0
            }
        
        total_tests = len(results)
        completed_tests = len([r for r in results if r.get("status") == "completed"])
        failed_tests = len([r for r in results if r.get("status") == "failed"])
        success_rate = (completed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Calculate average scores where available
        scores = []
        for result in results:
            if result.get("overall_score"):
                scores.append(result["overall_score"])
            elif result.get("average_quality"):
                scores.append(result["average_quality"])
        
        average_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "total_tests": total_tests,
            "completed_tests": completed_tests,
            "failed_tests": failed_tests,
            "success_rate": round(success_rate, 2),
            "average_score": round(average_score, 2),
            "test_types": list(set(r.get("test_type") for r in results)),
            "execution_time": "calculated_separately"
        }
    
    async def get_execution_status(self, execution_id: int) -> Optional[Dict[str, Any]]:
        """Get current status of a running execution."""
        
        if execution_id in self.running_executions:
            return self.running_executions[execution_id]
        
        # Check Redis for cached status
        try:
            cached_status = await redis_client.get_json(f"execution_status:{execution_id}")
            return cached_status
        except Exception:
            return None
    
    async def cancel_execution(self, execution_id: int) -> bool:
        """Cancel a running test execution."""
        
        if execution_id in self.running_executions:
            self.running_executions[execution_id]["status"] = TestStatus.CANCELLED
            
            # Broadcast cancellation
            await self._update_execution_progress(
                execution_id, 0, 0, "Execution cancelled", TestStatus.CANCELLED
            )
            
            # Clean up
            del self.running_executions[execution_id]
            
            logger.info("Test execution cancelled", execution_id=execution_id)
            return True
        
        return False

# Global test executor instance
test_executor = TestExecutor()