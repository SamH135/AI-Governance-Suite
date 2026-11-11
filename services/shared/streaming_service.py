"""
Streaming Response Service
Provides real-time streaming for LLM responses and long-running operations
"""

import asyncio
import json
import os
import uuid
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from datetime import datetime
from enum import Enum
import structlog
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
import aiofiles

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from .exceptions import ValidationError, ExternalServiceError

logger = structlog.get_logger()

class StreamType(str, Enum):
    """Types of streams supported."""
    LLM_RESPONSE = "llm_response"
    EVALUATION_PROGRESS = "evaluation_progress"
    DOCUMENT_GENERATION = "document_generation"
    TEST_EXECUTION = "test_execution"
    DATA_PROCESSING = "data_processing"

class StreamFormat(str, Enum):
    """Stream output formats."""
    JSON = "json"
    TEXT = "text"
    SSE = "server_sent_events"
    WEBSOCKET = "websocket"

class StreamingService:
    """Service for managing streaming responses and real-time communication."""
    
    def __init__(self):
        self.initialized = False
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.llm_clients: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize the streaming service."""
        if self.initialized:
            return
        
        try:
            # Initialize LLM clients for streaming
            await self._initialize_llm_clients()
            
            self.initialized = True
            logger.info("Streaming service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize streaming service", error=str(e))
            raise ExternalServiceError("StreamingService", f"Initialization failed: {str(e)}")
    
    async def create_llm_stream(
        self,
        model: str,
        prompt: str,
        stream_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        format: StreamFormat = StreamFormat.SSE
    ) -> Union[AsyncGenerator[str, None], str]:
        """Create a streaming LLM response."""
        if not self.initialized:
            await self.initialize()
        
        if not stream_id:
            stream_id = str(uuid.uuid4())
        
        try:
            # Store stream metadata
            self.active_streams[stream_id] = {
                "type": StreamType.LLM_RESPONSE,
                "model": model,
                "prompt": prompt,
                "parameters": parameters or {},
                "format": format,
                "started_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
            
            # Determine which LLM client to use
            if model.startswith("claude"):
                if not ANTHROPIC_AVAILABLE or "anthropic" not in self.llm_clients:
                    raise ExternalServiceError("Anthropic", "Anthropic client not available")
                return await self._stream_anthropic_response(stream_id, model, prompt, parameters)
            
            elif model.startswith("gpt") or model.startswith("text-davinci"):
                if not OPENAI_AVAILABLE or "openai" not in self.llm_clients:
                    raise ExternalServiceError("OpenAI", "OpenAI client not available")
                return await self._stream_openai_response(stream_id, model, prompt, parameters)
            
            else:
                # Use custom streaming for other models
                return await self._stream_custom_response(stream_id, model, prompt, parameters)
            
        except Exception as e:
            logger.error("Failed to create LLM stream", 
                        stream_id=stream_id, model=model, error=str(e))
            
            # Update stream status
            if stream_id in self.active_streams:
                self.active_streams[stream_id]["status"] = "error"
                self.active_streams[stream_id]["error"] = str(e)
            
            raise ValidationError(f"Failed to create LLM stream: {str(e)}")
    
    async def create_progress_stream(
        self,
        operation_type: StreamType,
        operation_id: str,
        total_steps: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a progress stream for long-running operations."""
        if not self.initialized:
            await self.initialize()
        
        stream_id = str(uuid.uuid4())
        
        try:
            self.active_streams[stream_id] = {
                "type": operation_type,
                "operation_id": operation_id,
                "total_steps": total_steps,
                "current_step": 0,
                "progress_percentage": 0.0,
                "status": "active",
                "metadata": metadata or {},
                "started_at": datetime.utcnow().isoformat(),
                "updates": []
            }
            
            logger.info("Progress stream created", 
                       stream_id=stream_id,
                       operation_type=operation_type,
                       operation_id=operation_id)
            
            return stream_id
            
        except Exception as e:
            logger.error("Failed to create progress stream", 
                        operation_type=operation_type, error=str(e))
            raise ValidationError(f"Failed to create progress stream: {str(e)}")
    
    async def update_progress_stream(
        self,
        stream_id: str,
        step: Optional[int] = None,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        increment: bool = True
    ) -> bool:
        """Update a progress stream."""
        if stream_id not in self.active_streams:
            return False
        
        try:
            stream_info = self.active_streams[stream_id]
            
            # Update step
            if step is not None:
                stream_info["current_step"] = step
            elif increment:
                stream_info["current_step"] += 1
            
            # Calculate progress percentage
            if stream_info.get("total_steps"):
                progress = (stream_info["current_step"] / stream_info["total_steps"]) * 100
                stream_info["progress_percentage"] = min(progress, 100.0)
            
            # Add update entry
            update_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "step": stream_info["current_step"],
                "progress": stream_info["progress_percentage"],
                "message": message,
                "data": data
            }
            
            stream_info["updates"].append(update_entry)
            stream_info["last_updated"] = datetime.utcnow().isoformat()
            
            # Notify WebSocket connections if any
            await self._notify_websocket_subscribers(stream_id, update_entry)
            
            logger.debug("Progress stream updated", 
                        stream_id=stream_id,
                        step=stream_info["current_step"],
                        progress=stream_info["progress_percentage"])
            
            return True
            
        except Exception as e:
            logger.error("Failed to update progress stream", 
                        stream_id=stream_id, error=str(e))
            return False
    
    async def complete_stream(
        self,
        stream_id: str,
        final_result: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> bool:
        """Mark a stream as completed."""
        if stream_id not in self.active_streams:
            return False
        
        try:
            stream_info = self.active_streams[stream_id]
            stream_info["status"] = "completed" if success else "failed"
            stream_info["completed_at"] = datetime.utcnow().isoformat()
            
            if final_result:
                stream_info["final_result"] = final_result
            
            # Calculate total duration
            if "started_at" in stream_info:
                started = datetime.fromisoformat(stream_info["started_at"])
                duration = (datetime.utcnow() - started).total_seconds()
                stream_info["duration_seconds"] = duration
            
            # Notify WebSocket subscribers
            completion_update = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": stream_info["status"],
                "final_result": final_result,
                "duration": stream_info.get("duration_seconds")
            }
            
            await self._notify_websocket_subscribers(stream_id, completion_update)
            
            logger.info("Stream completed", 
                       stream_id=stream_id,
                       status=stream_info["status"],
                       duration=stream_info.get("duration_seconds"))
            
            return True
            
        except Exception as e:
            logger.error("Failed to complete stream", 
                        stream_id=stream_id, error=str(e))
            return False
    
    async def get_stream_status(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a stream."""
        if stream_id not in self.active_streams:
            return None
        
        return self.active_streams[stream_id].copy()
    
    async def get_stream_sse(self, stream_id: str) -> AsyncGenerator[str, None]:
        """Get Server-Sent Events stream for a stream ID."""
        if stream_id not in self.active_streams:
            yield f"data: {json.dumps({'error': 'Stream not found'})}\n\n"
            return
        
        stream_info = self.active_streams[stream_id]
        
        # Send initial state
        yield f"data: {json.dumps({'type': 'stream_start', 'stream_id': stream_id, 'stream_info': stream_info})}\n\n"
        
        # Send existing updates
        for update in stream_info.get("updates", []):
            yield f"data: {json.dumps({'type': 'update', 'stream_id': stream_id, **update})}\n\n"
        
        # Stream new updates
        last_update_count = len(stream_info.get("updates", []))
        
        while stream_info.get("status") == "active":
            await asyncio.sleep(0.5)  # Poll every 500ms
            
            current_updates = stream_info.get("updates", [])
            if len(current_updates) > last_update_count:
                # Send new updates
                for update in current_updates[last_update_count:]:
                    yield f"data: {json.dumps({'type': 'update', 'stream_id': stream_id, **update})}\n\n"
                last_update_count = len(current_updates)
        
        # Send completion message
        completion_data = {
            "type": "stream_end",
            "stream_id": stream_id,
            "status": stream_info.get("status"),
            "final_result": stream_info.get("final_result")
        }
        yield f"data: {json.dumps(completion_data)}\n\n"
    
    async def subscribe_websocket(self, stream_id: str, websocket: WebSocket) -> bool:
        """Subscribe a WebSocket connection to a stream."""
        if stream_id not in self.active_streams:
            return False
        
        try:
            await websocket.accept()
            connection_id = f"{stream_id}_{id(websocket)}"
            self.websocket_connections[connection_id] = websocket
            
            # Send initial stream state
            initial_data = {
                "type": "subscription_confirmed",
                "stream_id": stream_id,
                "stream_info": self.active_streams[stream_id]
            }
            await websocket.send_json(initial_data)
            
            logger.info("WebSocket subscribed to stream", 
                       stream_id=stream_id,
                       connection_id=connection_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to subscribe WebSocket to stream", 
                        stream_id=stream_id, error=str(e))
            return False
    
    async def unsubscribe_websocket(self, stream_id: str, websocket: WebSocket):
        """Unsubscribe a WebSocket connection from a stream."""
        connection_id = f"{stream_id}_{id(websocket)}"
        
        if connection_id in self.websocket_connections:
            del self.websocket_connections[connection_id]
            logger.info("WebSocket unsubscribed from stream", 
                       stream_id=stream_id,
                       connection_id=connection_id)
    
    async def cleanup_completed_streams(self, max_age_hours: int = 24):
        """Clean up completed streams older than specified age."""
        current_time = datetime.utcnow()
        streams_to_remove = []
        
        for stream_id, stream_info in self.active_streams.items():
            if stream_info.get("status") in ["completed", "failed"]:
                completed_at = stream_info.get("completed_at")
                if completed_at:
                    completed_time = datetime.fromisoformat(completed_at)
                    age_hours = (current_time - completed_time).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        streams_to_remove.append(stream_id)
        
        # Remove old streams
        for stream_id in streams_to_remove:
            del self.active_streams[stream_id]
        
        if streams_to_remove:
            logger.info("Cleaned up completed streams", count=len(streams_to_remove))
    
    async def get_active_streams(self, stream_type: Optional[StreamType] = None) -> List[Dict[str, Any]]:
        """Get list of active streams."""
        streams = []
        
        for stream_id, stream_info in self.active_streams.items():
            if stream_type is None or stream_info.get("type") == stream_type:
                if stream_info.get("status") == "active":
                    streams.append({
                        "stream_id": stream_id,
                        **stream_info
                    })
        
        return streams
    
    # Private helper methods
    async def _initialize_llm_clients(self):
        """Initialize LLM clients for streaming."""
        try:
            # Initialize OpenAI client
            if OPENAI_AVAILABLE:
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if openai_api_key:
                    self.llm_clients["openai"] = openai.AsyncOpenAI(api_key=openai_api_key)
                    logger.info("OpenAI streaming client initialized")
            
            # Initialize Anthropic client
            if ANTHROPIC_AVAILABLE:
                anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
                if anthropic_api_key:
                    self.llm_clients["anthropic"] = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
                    logger.info("Anthropic streaming client initialized")
            
        except Exception as e:
            logger.error("Failed to initialize LLM clients", error=str(e))
    
    async def _stream_anthropic_response(
        self,
        stream_id: str,
        model: str,
        prompt: str,
        parameters: Optional[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Stream response from Anthropic Claude."""
        try:
            client = self.llm_clients["anthropic"]
            
            # Prepare parameters
            params = {
                "model": model,
                "max_tokens": parameters.get("max_tokens", 1000),
                "temperature": parameters.get("temperature", 0.7),
                "messages": [{"role": "user", "content": prompt}],
                "stream": True
            }
            
            # Start streaming
            async with client.messages.stream(**params) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_delta":
                        if hasattr(chunk.delta, 'text'):
                            text_chunk = chunk.delta.text
                            
                            # Format as SSE
                            sse_data = {
                                "type": "chunk",
                                "stream_id": stream_id,
                                "content": text_chunk,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            
                            yield f"data: {json.dumps(sse_data)}\n\n"
            
            # Send completion
            completion_data = {
                "type": "completion",
                "stream_id": stream_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
            # Update stream status
            await self.complete_stream(stream_id, success=True)
            
        except Exception as e:
            logger.error("Anthropic streaming failed", stream_id=stream_id, error=str(e))
            
            error_data = {
                "type": "error",
                "stream_id": stream_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            
            await self.complete_stream(stream_id, success=False)
    
    async def _stream_openai_response(
        self,
        stream_id: str,
        model: str,
        prompt: str,
        parameters: Optional[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Stream response from OpenAI GPT."""
        try:
            client = self.llm_clients["openai"]
            
            # Prepare parameters
            params = {
                "model": model,
                "max_tokens": parameters.get("max_tokens", 1000),
                "temperature": parameters.get("temperature", 0.7),
                "stream": True
            }
            
            # Handle different model types
            if model.startswith("gpt-3.5") or model.startswith("gpt-4"):
                params["messages"] = [{"role": "user", "content": prompt}]
                stream = await client.chat.completions.create(**params)
            else:
                params["prompt"] = prompt
                stream = await client.completions.create(**params)
            
            # Process stream
            async for chunk in stream:
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    
                    # Extract content based on model type
                    if hasattr(choice, 'delta') and choice.delta:
                        content = choice.delta.content if hasattr(choice.delta, 'content') else None
                    elif hasattr(choice, 'text'):
                        content = choice.text
                    else:
                        content = None
                    
                    if content:
                        # Format as SSE
                        sse_data = {
                            "type": "chunk",
                            "stream_id": stream_id,
                            "content": content,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        yield f"data: {json.dumps(sse_data)}\n\n"
            
            # Send completion
            completion_data = {
                "type": "completion",
                "stream_id": stream_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
            await self.complete_stream(stream_id, success=True)
            
        except Exception as e:
            logger.error("OpenAI streaming failed", stream_id=stream_id, error=str(e))
            
            error_data = {
                "type": "error",
                "stream_id": stream_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            
            await self.complete_stream(stream_id, success=False)
    
    async def _stream_custom_response(
        self,
        stream_id: str,
        model: str,
        prompt: str,
        parameters: Optional[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Stream response from custom model."""
        try:
            # Simulate streaming response for custom models
            response_text = f"Custom response from {model} for prompt: {prompt[:50]}..."
            
            # Stream in chunks
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                
                sse_data = {
                    "type": "chunk",
                    "stream_id": stream_id,
                    "content": chunk,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                yield f"data: {json.dumps(sse_data)}\n\n"
                
                # Small delay to simulate streaming
                await asyncio.sleep(0.1)
            
            # Send completion
            completion_data = {
                "type": "completion",
                "stream_id": stream_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(completion_data)}\n\n"
            
            await self.complete_stream(stream_id, success=True)
            
        except Exception as e:
            logger.error("Custom streaming failed", stream_id=stream_id, error=str(e))
            
            error_data = {
                "type": "error",
                "stream_id": stream_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            
            await self.complete_stream(stream_id, success=False)
    
    async def _notify_websocket_subscribers(self, stream_id: str, update_data: Dict[str, Any]):
        """Notify WebSocket subscribers of stream updates."""
        disconnected_connections = []
        
        for connection_id, websocket in self.websocket_connections.items():
            if connection_id.startswith(stream_id):
                try:
                    await websocket.send_json({
                        "type": "stream_update",
                        "stream_id": stream_id,
                        **update_data
                    })
                except Exception as e:
                    logger.warning("Failed to send WebSocket update", 
                                 connection_id=connection_id, error=str(e))
                    disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            del self.websocket_connections[connection_id]

# Global streaming service instance
streaming_service = StreamingService()