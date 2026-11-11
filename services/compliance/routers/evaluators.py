# services/compliance/routers/evaluators.py
"""Evaluator management endpoints with framework integration and saved API key support."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Request
import structlog

from ...shared.auth import get_current_active_user, require_admin
from ...shared.schemas import UserResponse, ApiResponse
from ...shared.unified_api_auth import setup_unified_api_auth_dependency
from ..framework.core.registry import Registry

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_available_evaluators(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of available compliance evaluators."""
    
    try:
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        frameworks = Registry.list_evaluators()
        
        evaluators = []
        for framework in frameworks:
            try:
                # Get evaluator class and metadata
                evaluator_class = Registry._evaluators.get(framework)
                if evaluator_class:
                    metadata = evaluator_class.get_metadata()
                    evaluator_info = {
                        "framework": framework,
                        "name": metadata.name,
                        "description": metadata.description,
                        "category": metadata.category,
                        "version": metadata.version,
                        "tags": metadata.tags,
                        "capabilities": [cap.value for cap in metadata.capabilities],
                        "llm_requirements": {
                            "requirement_level": metadata.llm_requirements.requirement_level.value,
                            "suggested_providers": metadata.llm_requirements.suggested_providers,
                            "suggested_models": metadata.llm_requirements.suggested_models,
                            "expected_response_format": metadata.llm_requirements.expected_response_format
                        },
                        "rag_requirements": {
                            "requirement_level": metadata.rag_requirements.requirement_level.value,
                            "vector_store_required": metadata.rag_requirements.vector_store_required,
                            "context_types": metadata.rag_requirements.context_types
                        },
                        "requires_test_subject_config": metadata.requires_test_subject_config,
                        "fallback_mode": metadata.fallback_mode,
                        "estimated_runtime": metadata.estimated_runtime,
                        "parallel_safe": metadata.parallel_safe
                    }
                    evaluators.append(evaluator_info)
                else:
                    # Fallback info for evaluators without detailed metadata
                    evaluators.append({
                        "framework": framework,
                        "name": framework,
                        "description": f"Evaluator for {framework} framework",
                        "category": "unknown",
                        "version": "1.0.0"
                    })
                    
            except Exception as e:
                logger.error("Failed to get evaluator info", framework=framework, error=str(e))
                evaluators.append({
                    "framework": framework,
                    "name": framework,
                    "description": f"Evaluator for {framework} (error loading details)",
                    "category": "unknown",
                    "error": str(e)
                })
        
        return ApiResponse(
            success=True,
            data=evaluators,
            message=f"Found {len(evaluators)} available evaluators"
        )
        
    except Exception as e:
        logger.error("Failed to get available evaluators", error=str(e))
        return ApiResponse(
            success=False,
            data=[],
            error=f"Failed to retrieve evaluators: {str(e)}"
        )


@router.get("/{framework}", response_model=ApiResponse[Dict[str, Any]])
async def get_evaluator_details(
    framework: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get detailed information about a specific evaluator."""
    
    try:
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        
        # Check if evaluator exists
        if framework not in Registry._evaluators:
            return ApiResponse(
                success=False,
                data={},
                error=f"Evaluator not found: {framework}"
            )
        
        # Get evaluator class and metadata
        evaluator_class = Registry._evaluators[framework]
        metadata = evaluator_class.get_metadata()
        
        evaluator_info = {
            "framework": framework,
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category,
            "version": metadata.version,
            "tags": metadata.tags,
            "output_format": metadata.output_format,
            "primary_output_key": metadata.primary_output_key,
            "display_fields": metadata.display_fields,
            "risk_thresholds": metadata.risk_thresholds,
            "capabilities": [cap.value for cap in metadata.capabilities],
            "llm_requirements": {
                "requirement_level": metadata.llm_requirements.requirement_level.value,
                "suggested_providers": metadata.llm_requirements.suggested_providers,
                "suggested_models": metadata.llm_requirements.suggested_models,
                "min_context_window": metadata.llm_requirements.min_context_window,
                "expected_response_format": metadata.llm_requirements.expected_response_format,
                "notes": metadata.llm_requirements.notes
            },
            "rag_requirements": {
                "requirement_level": metadata.rag_requirements.requirement_level.value,
                "vector_store_required": metadata.rag_requirements.vector_store_required,
                "min_context_chunks": metadata.rag_requirements.min_context_chunks,
                "max_context_chunks": metadata.rag_requirements.max_context_chunks,
                "context_types": metadata.rag_requirements.context_types,
                "suggested_providers": metadata.rag_requirements.suggested_providers,
                "notes": metadata.rag_requirements.notes
            },
            "requires_test_subject_config": metadata.requires_test_subject_config,
            "fallback_mode": metadata.fallback_mode,
            "estimated_runtime": metadata.estimated_runtime,
            "parallel_safe": metadata.parallel_safe
        }
        
        # Try to get additional details by instantiating the evaluator
        try:
            evaluator = Registry.get_evaluator(framework)
            
            # Add sample test cases if available
            if hasattr(evaluator, 'get_test_cases'):
                try:
                    test_cases = evaluator.get_test_cases()
                    evaluator_info["test_count"] = len(test_cases) if test_cases else 0
                    evaluator_info["sample_tests"] = [tc.get("name") for tc in test_cases[:3]] if test_cases else []
                except:
                    pass
            
        except Exception as e:
            logger.warning("Could not instantiate evaluator for details", 
                         framework=framework, error=str(e))
        
        return ApiResponse(
            success=True,
            data=evaluator_info,
            message=f"Retrieved details for {framework} evaluator"
        )
        
    except Exception as e:
        logger.error("Failed to get evaluator details", framework=framework, error=str(e))
        return ApiResponse(
            success=False,
            data={},
            error=f"Failed to get evaluator details: {str(e)}"
        )


@router.get("/category/{category}", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_evaluators_by_category(
    category: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get evaluators filtered by category."""
    
    try:
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        
        evaluators = []
        for framework_name in Registry.list_evaluators():
            try:
                evaluator_class = Registry._evaluators.get(framework_name)
                if evaluator_class:
                    metadata = evaluator_class.get_metadata()
                    if metadata.category.lower() == category.lower():
                        evaluator_info = {
                            "framework": framework_name,
                            "name": metadata.name,
                            "description": metadata.description,
                            "category": metadata.category,
                            "version": metadata.version,
                            "tags": metadata.tags,
                            "capabilities": [cap.value for cap in metadata.capabilities]
                        }
                        evaluators.append(evaluator_info)
            except Exception as e:
                logger.warning("Failed to process evaluator for category filter", 
                             framework=framework_name, error=str(e))
        
        return ApiResponse(
            success=True,
            data=evaluators,
            message=f"Found {len(evaluators)} evaluators in category: {category}"
        )
        
    except Exception as e:
        logger.error("Failed to get evaluators by category", category=category, error=str(e))
        return ApiResponse(
            success=False,
            data=[],
            error=f"Failed to get evaluators by category: {str(e)}"
        )


@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
async def get_evaluator_health(
    current_user: UserResponse = Depends(require_admin)  # Admin only
):
    """Get health status of evaluator system."""
    
    try:
        # Perform health check by discovering and testing evaluators
        Registry.discover_evaluators()
        evaluator_names = Registry.list_evaluators()
        
        health_status = {
            "status": "healthy",
            "evaluators_discovered": len(evaluator_names),
            "evaluator_list": evaluator_names,
            "registry_health": "ok",
            "errors": []
        }
        
        # Test instantiation of each evaluator
        for name in evaluator_names:
            try:
                evaluator = Registry.get_evaluator(name)
                metadata = evaluator.get_metadata()
                logger.info(f"Health check: {name} instantiated successfully")
            except Exception as e:
                error_msg = f"Failed to instantiate {name}: {str(e)}"
                health_status["errors"].append(error_msg)
                logger.warning(error_msg)
        
        # Update overall status if there are errors
        if health_status["errors"]:
            health_status["status"] = "degraded"
        
        return ApiResponse(
            success=True,
            data=health_status,
            message="Evaluator system health check completed"
        )
        
    except Exception as e:
        logger.error("Failed to perform health check", error=str(e))
        return ApiResponse(
            success=False,
            data={"status": "error", "error": str(e)},
            error=f"Health check failed: {str(e)}"
        )


@router.post("/test/{framework}", response_model=ApiResponse[Dict[str, Any]])
async def test_evaluator_directly(
    framework: str,
    request_data: Dict[str, Any]
):
    """Test an evaluator directly without authentication (for development)."""
    
    try:
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        
        # Check if evaluator exists
        if framework not in Registry._evaluators:
            return ApiResponse(
                success=False,
                data={},
                error=f"Evaluator not found: {framework}"
            )
        
        # Get evaluator
        evaluator = Registry.get_evaluator(framework)

        # Extract test parameters - support multiple input formats
        test_text = request_data.get("text")

        # If no text field, check for test_subject structure
        if not test_text and "test_subject" in request_data:
            test_subject = request_data["test_subject"]
            if isinstance(test_subject, dict):
                # Prioritize response content for evaluation
                test_text = test_subject.get("response") or test_subject.get("prompt")
            else:
                test_text = str(test_subject)

        # Require text to be provided
        if not test_text:
            return ApiResponse(
                success=False,
                data={},
                error="No test text provided. Include 'text' field or 'test_subject' object with 'response' or 'prompt'"
            )

        llm_config_data = request_data.get("llm_config")
        
        # Create LLM config if provided
        llm_config = None
        if llm_config_data:
            from shared.unified_api.base import ModelConfig, ModelType
            llm_config = ModelConfig(
                provider=llm_config_data.get("provider", "google"),
                model_id=llm_config_data.get("model_id", "gemini-pro"),
                api_key=llm_config_data.get("api_key"),
                temperature=llm_config_data.get("temperature", 0.3),
                max_tokens=llm_config_data.get("max_tokens", 1000),
                usage_type=ModelType.EVALUATOR
            )
        
        # Run evaluation
        logger.info(f"Testing evaluator {framework} with text length: {len(test_text)}")
        result = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=llm_config
        )
        
        # Add test metadata
        result["test_metadata"] = {
            "framework": framework,
            "text_length": len(test_text),
            "llm_used": llm_config is not None,
            "llm_provider": llm_config.provider if llm_config else None,
            "llm_model": llm_config.model_id if llm_config else None
        }
        
        logger.info(f"Evaluator test completed: {framework}, score: {result.get('compliance_score', 'N/A')}")
        
        return ApiResponse(
            success=True,
            data=result,
            message=f"Evaluator {framework} test completed successfully"
        )
        
    except Exception as e:
        logger.error(f"Evaluator test failed: {framework}, error: {str(e)}")
        return ApiResponse(
            success=False,
            data={"error_details": str(e)},
            error=f"Evaluator test failed: {str(e)}"
        )


@router.post("/test-with-saved-keys/{framework}", response_model=ApiResponse[Dict[str, Any]])
async def test_evaluator_with_saved_keys(
    framework: str,
    request_data: Dict[str, Any],
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
    auth_manager = Depends(setup_unified_api_auth_dependency)
):
    """Test an evaluator using saved API keys from the gateway."""
    
    try:
        # Ensure evaluators are discovered
        Registry.discover_evaluators()
        
        # Check if evaluator exists
        if framework not in Registry._evaluators:
            return ApiResponse(
                success=False,
                data={},
                error=f"Evaluator not found: {framework}"
            )
        
        # Get evaluator
        evaluator = Registry.get_evaluator(framework)

        # Extract test parameters - support multiple input formats
        test_text = request_data.get("text")

        # If no text field, check for test_subject structure
        if not test_text and "test_subject" in request_data:
            test_subject = request_data["test_subject"]
            if isinstance(test_subject, dict):
                # Prioritize response content for evaluation
                test_text = test_subject.get("response") or test_subject.get("prompt")
            else:
                test_text = str(test_subject)

        # Require text to be provided
        if not test_text:
            return ApiResponse(
                success=False,
                data={},
                error="No test text provided. Include 'text' field or 'test_subject' object with 'response' or 'prompt'"
            )

        llm_config_data = request_data.get("llm_config", {})
        
        # Create LLM config - the unified API will automatically use saved keys
        # if provider and model are specified but no API key is provided
        llm_config = None
        provider = llm_config_data.get("provider")
        model_id = llm_config_data.get("model_id")
        
        if provider and model_id:
            from shared.unified_api.base import ModelConfig, ModelType
            llm_config = ModelConfig(
                provider=provider,
                model_id=model_id,
                # Don't specify API key - it will be retrieved from saved keys
                temperature=llm_config_data.get("temperature", 0.3),
                max_tokens=llm_config_data.get("max_tokens", 1000),
                usage_type=ModelType.EVALUATOR
            )
            
            logger.info(f"Using saved API keys for provider: {provider}")
        
        # Run evaluation
        logger.info(f"Testing evaluator {framework} with saved keys, text length: {len(test_text)}")
        result = evaluator.evaluate(
            text=test_text,
            evaluator_llm_config=llm_config
        )
        
        # Add test metadata
        result["test_metadata"] = {
            "framework": framework,
            "text_length": len(test_text),
            "llm_used": llm_config is not None,
            "llm_provider": llm_config.provider if llm_config else None,
            "llm_model": llm_config.model_id if llm_config else None,
            "using_saved_keys": True,
            "user_id": current_user.id
        }
        
        logger.info(f"Evaluator test with saved keys completed: {framework}, score: {result.get('compliance_score', 'N/A')}")
        
        return ApiResponse(
            success=True,
            data=result,
            message=f"Evaluator {framework} test completed successfully with saved API keys"
        )
        
    except Exception as e:
        logger.error(f"Evaluator test with saved keys failed: {framework}, error: {str(e)}")
        return ApiResponse(
            success=False,
            data={"error_details": str(e)},
            error=f"Evaluator test with saved keys failed: {str(e)}"
        )
