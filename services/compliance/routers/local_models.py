"""Local model management endpoints."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
import structlog

from ...shared.auth import get_current_active_user, require_admin
from ...shared.schemas import UserResponse, ApiResponse
from ...shared.exceptions import ValidationError
from ...shared.local_models import local_model_manager

logger = structlog.get_logger()
router = APIRouter()

@router.get("/available", response_model=ApiResponse[Dict[str, Any]])
async def get_available_models(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get available local models and hardware information."""
    
    try:
        # Get hardware info
        if not local_model_manager.initialized:
            await local_model_manager.initialize()
        
        device_info = local_model_manager.device_info
        memory_info = await local_model_manager.get_memory_usage()
        
        # Get model recommendations based on available memory
        available_memory = memory_info["system_memory"]["available_gb"]
        recommendations = await local_model_manager.optimize_model_loading(available_memory)
        
        available_info = {
            "hardware": device_info,
            "memory": memory_info,
            "recommended_models": recommendations,
            "model_categories": local_model_manager.model_configs
        }
        
        return ApiResponse(
            success=True,
            data=available_info,
            message="Available models and hardware information retrieved"
        )
        
    except Exception as e:
        logger.error("Failed to get available models", error=str(e))
        raise ValidationError(f"Failed to get available models: {str(e)}")

@router.post("/load", response_model=ApiResponse[Dict[str, Any]])
async def load_model(
    model_name: str,
    background_tasks: BackgroundTasks,
    model_type: str = "causal_lm",
    quantization: Optional[str] = None,
    device: Optional[str] = None,
    current_user: UserResponse = Depends(require_admin)
):
    """Load a local model (admin only)."""
    
    try:
        # Start model loading in background
        background_tasks.add_task(
            load_model_background,
            model_name,
            model_type,
            quantization,
            device,
            current_user.user_id
        )
        
        return ApiResponse(
            success=True,
            data={
                "model_name": model_name,
                "model_type": model_type,
                "status": "loading_started"
            },
            message="Model loading started in background"
        )
        
    except Exception as e:
        logger.error("Failed to start model loading", 
                    model_name=model_name, error=str(e))
        raise ValidationError(f"Failed to start model loading: {str(e)}")

@router.get("/loaded", response_model=ApiResponse[Dict[str, Any]])
async def get_loaded_models(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of currently loaded models."""
    
    try:
        loaded_models = await local_model_manager.list_loaded_models()
        
        return ApiResponse(
            success=True,
            data=loaded_models,
            message=f"Found {loaded_models['total_models']} loaded models"
        )
        
    except Exception as e:
        logger.error("Failed to get loaded models", error=str(e))
        raise ValidationError(f"Failed to get loaded models: {str(e)}")

@router.get("/info/{model_key}", response_model=ApiResponse[Dict[str, Any]])
async def get_model_info(
    model_key: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get information about a specific loaded model."""
    
    try:
        model_info = await local_model_manager.get_model_info(model_key)
        
        return ApiResponse(
            success=True,
            data=model_info,
            message="Model information retrieved"
        )
        
    except Exception as e:
        logger.error("Failed to get model info", 
                    model_key=model_key, error=str(e))
        raise ValidationError(f"Failed to get model info: {str(e)}")

@router.post("/generate", response_model=ApiResponse[Dict[str, Any]])
async def generate_text(
    model_key: str,
    prompt: str,
    max_length: int = 100,
    temperature: float = 0.7,
    do_sample: bool = True,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Generate text using a loaded local model."""
    
    try:
        result = await local_model_manager.generate_text(
            model_key=model_key,
            prompt=prompt,
            max_length=max_length,
            temperature=temperature,
            do_sample=do_sample
        )
        
        logger.info("Text generated successfully", 
                   model_key=model_key,
                   user_id=current_user.user_id,
                   input_length=result["input_length"])
        
        return ApiResponse(
            success=True,
            data=result,
            message="Text generated successfully"
        )
        
    except Exception as e:
        logger.error("Text generation failed", 
                    model_key=model_key, error=str(e))
        raise ValidationError(f"Text generation failed: {str(e)}")

@router.post("/embeddings", response_model=ApiResponse[Dict[str, Any]])
async def generate_embeddings(
    model_key: str,
    texts: List[str],
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Generate embeddings using a loaded embedding model."""
    
    try:
        result = await local_model_manager.generate_embeddings(
            model_key=model_key,
            texts=texts
        )
        
        logger.info("Embeddings generated successfully", 
                   model_key=model_key,
                   user_id=current_user.user_id,
                   text_count=result["count"])
        
        return ApiResponse(
            success=True,
            data=result,
            message="Embeddings generated successfully"
        )
        
    except Exception as e:
        logger.error("Embedding generation failed", 
                    model_key=model_key, error=str(e))
        raise ValidationError(f"Embedding generation failed: {str(e)}")

@router.post("/pipeline", response_model=ApiResponse[Dict[str, Any]])
async def create_pipeline(
    model_key: str,
    task: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Create a pipeline for a loaded model (admin only)."""
    
    try:
        pipeline_key = await local_model_manager.create_pipeline(
            model_key=model_key,
            task=task
        )
        
        return ApiResponse(
            success=True,
            data={
                "pipeline_key": pipeline_key,
                "model_key": model_key,
                "task": task
            },
            message="Pipeline created successfully"
        )
        
    except Exception as e:
        logger.error("Pipeline creation failed", 
                    model_key=model_key, task=task, error=str(e))
        raise ValidationError(f"Pipeline creation failed: {str(e)}")

@router.post("/pipeline/{pipeline_key}/run", response_model=ApiResponse[Dict[str, Any]])
async def run_pipeline(
    pipeline_key: str,
    inputs: Dict[str, Any],
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Run a pipeline with given inputs."""
    
    try:
        result = await local_model_manager.run_pipeline(
            pipeline_key=pipeline_key,
            inputs=inputs.get("inputs"),
            **inputs.get("kwargs", {})
        )
        
        logger.info("Pipeline executed successfully", 
                   pipeline_key=pipeline_key,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=result,
            message="Pipeline executed successfully"
        )
        
    except Exception as e:
        logger.error("Pipeline execution failed", 
                    pipeline_key=pipeline_key, error=str(e))
        raise ValidationError(f"Pipeline execution failed: {str(e)}")

@router.delete("/unload/{model_key}", response_model=ApiResponse[str])
async def unload_model(
    model_key: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Unload a model to free memory (admin only)."""
    
    try:
        success = await local_model_manager.unload_model(model_key)
        
        if success:
            logger.info("Model unloaded successfully", 
                       model_key=model_key,
                       user_id=current_user.user_id)
            
            return ApiResponse(
                success=True,
                data="Model unloaded successfully",
                message=f"Model {model_key} has been unloaded"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to unload model {model_key}"
            )
        
    except Exception as e:
        logger.error("Model unloading failed", 
                    model_key=model_key, error=str(e))
        raise ValidationError(f"Model unloading failed: {str(e)}")

@router.get("/memory", response_model=ApiResponse[Dict[str, Any]])
async def get_memory_usage(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get current memory usage information."""
    
    try:
        memory_info = await local_model_manager.get_memory_usage()
        
        return ApiResponse(
            success=True,
            data=memory_info,
            message="Memory usage information retrieved"
        )
        
    except Exception as e:
        logger.error("Failed to get memory usage", error=str(e))
        raise ValidationError(f"Failed to get memory usage: {str(e)}")

async def load_model_background(
    model_name: str,
    model_type: str,
    quantization: Optional[str],
    device: Optional[str],
    user_id: int
):
    """Background task to load a model."""
    
    try:
        logger.info("Starting background model loading", 
                   model_name=model_name,
                   model_type=model_type,
                   user_id=user_id)
        
        model_key = await local_model_manager.load_model(
            model_name=model_name,
            model_type=model_type,
            quantization=quantization,
            device=device
        )
        
        logger.info("Background model loading completed", 
                   model_name=model_name,
                   model_key=model_key,
                   user_id=user_id)
        
    except Exception as e:
        logger.error("Background model loading failed", 
                    model_name=model_name,
                    user_id=user_id,
                    error=str(e))