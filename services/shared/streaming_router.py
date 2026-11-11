"""
Streaming Service Router
Provides REST API endpoints for real-time streaming capabilities
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from .auth import get_current_active_user
from .schemas import UserResponse, ApiResponse
from .exceptions import ValidationError, ExternalServiceError
from .streaming_service import streaming_service, StreamType, StreamFormat

logger = structlog.get_logger()
router = APIRouter()

# Pydantic schemas for streaming
class LLMStreamRequest(BaseModel):
    model: str = Field(..., description="LLM model to use")
    prompt: str = Field(..., description="Prompt text")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Model parameters")
    format: StreamFormat = Field(default=StreamFormat.SSE, description="Stream format")

class ProgressStreamRequest(BaseModel):
    operation_type: StreamType = Field(..., description="Type of operation")
    operation_id: str = Field(..., description="Unique operation identifier")
    total_steps: Optional[int] = Field(default=None, description="Total number of steps")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

class ProgressUpdateRequest(BaseModel):
    step: Optional[int] = Field(default=None, description="Current step number")
    message: Optional[str] = Field(default=None, description="Progress message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")
    increment: bool = Field(default=True, description="Whether to increment step counter")

@router.post("/llm/stream", response_model=ApiResponse[str])
async def create_llm_stream(
    stream_request: LLMStreamRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Create a new LLM streaming response."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        stream_id = await streaming_service.create_llm_stream(
            model=stream_request.model,
            prompt=stream_request.prompt,
            parameters=stream_request.parameters,
            format=stream_request.format
        )
        
        logger.info("LLM stream created", 
                   stream_id=stream_id,
                   model=stream_request.model,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=stream_id,
            message="LLM stream created successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Failed to create LLM stream", 
                    model=stream_request.model, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/llm/stream/{stream_id}")
async def get_llm_stream(
    stream_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get LLM stream as Server-Sent Events."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        # Verify stream exists
        stream_status = await streaming_service.get_stream_status(stream_id)
        if not stream_status:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Return SSE stream
        return StreamingResponse(
            streaming_service.get_stream_sse(stream_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get LLM stream", 
                    stream_id=stream_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/progress/stream", response_model=ApiResponse[str])
async def create_progress_stream(
    stream_request: ProgressStreamRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Create a new progress stream for long-running operations."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        stream_id = await streaming_service.create_progress_stream(
            operation_type=stream_request.operation_type,
            operation_id=stream_request.operation_id,
            total_steps=stream_request.total_steps,
            metadata=stream_request.metadata
        )
        
        logger.info("Progress stream created", 
                   stream_id=stream_id,
                   operation_type=stream_request.operation_type,
                   operation_id=stream_request.operation_id,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=stream_id,
            message="Progress stream created successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create progress stream", 
                    operation_type=stream_request.operation_type, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/progress/stream/{stream_id}", response_model=ApiResponse[bool])
async def update_progress_stream(
    stream_id: str,
    update_request: ProgressUpdateRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Update progress for a stream."""
    
    try:
        success = await streaming_service.update_progress_stream(
            stream_id=stream_id,
            step=update_request.step,
            message=update_request.message,
            data=update_request.data,
            increment=update_request.increment
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        return ApiResponse(
            success=True,
            data=success,
            message="Progress updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update progress stream", 
                    stream_id=stream_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/progress/stream/{stream_id}/complete", response_model=ApiResponse[bool])
async def complete_progress_stream(
    stream_id: str,
    final_result: Optional[Dict[str, Any]] = None,
    success: bool = True,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Mark a progress stream as completed."""
    
    try:
        completed = await streaming_service.complete_stream(
            stream_id=stream_id,
            final_result=final_result,
            success=success
        )
        
        if not completed:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        logger.info("Progress stream completed", 
                   stream_id=stream_id,
                   success=success,
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=completed,
            message="Stream completed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to complete progress stream", 
                    stream_id=stream_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/progress/stream/{stream_id}")
async def get_progress_stream(
    stream_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get progress stream as Server-Sent Events."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        # Verify stream exists
        stream_status = await streaming_service.get_stream_status(stream_id)
        if not stream_status:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Return SSE stream
        return StreamingResponse(
            streaming_service.get_stream_sse(stream_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get progress stream", 
                    stream_id=stream_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stream/{stream_id}/status", response_model=ApiResponse[Dict[str, Any]])
async def get_stream_status(
    stream_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get the current status of a stream."""
    
    try:
        status = await streaming_service.get_stream_status(stream_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        return ApiResponse(
            success=True,
            data=status,
            message="Stream status retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get stream status", 
                    stream_id=stream_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/streams/active", response_model=ApiResponse[list])
async def get_active_streams(
    stream_type: Optional[StreamType] = None,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of active streams."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        streams = await streaming_service.get_active_streams(stream_type)
        
        return ApiResponse(
            success=True,
            data=streams,
            message=f"Found {len(streams)} active streams"
        )
        
    except Exception as e:
        logger.error("Failed to get active streams", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.websocket("/ws/{stream_id}")
async def websocket_stream_endpoint(websocket: WebSocket, stream_id: str):
    """WebSocket endpoint for real-time stream updates."""
    
    try:
        if not streaming_service.initialized:
            await streaming_service.initialize()
        
        # Subscribe to stream
        success = await streaming_service.subscribe_websocket(stream_id, websocket)
        
        if not success:
            await websocket.close(code=1008, reason="Stream not found")
            return
        
        # Keep connection alive and handle disconnection
        try:
            while True:
                # Wait for any message (keep-alive)
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await streaming_service.unsubscribe_websocket(stream_id, websocket)
            
    except Exception as e:
        logger.error("WebSocket stream error", 
                    stream_id=stream_id, error=str(e))
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.close(code=1011, reason="Internal server error")

@router.post("/cleanup", response_model=ApiResponse[str])
async def cleanup_completed_streams(
    max_age_hours: int = 24,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Clean up completed streams (admin only)."""
    
    try:
        # This would typically require admin permissions
        # For now, allow any authenticated user
        
        await streaming_service.cleanup_completed_streams(max_age_hours)
        
        return ApiResponse(
            success=True,
            data="Cleanup completed",
            message=f"Cleaned up streams older than {max_age_hours} hours"
        )
        
    except Exception as e:
        logger.error("Failed to cleanup streams", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")