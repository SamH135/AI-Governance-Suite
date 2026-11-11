"""WebSocket manager for real-time communication across services."""

import asyncio
import json
import uuid
from typing import Dict, Set, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

logger = structlog.get_logger()

class MessageType(Enum):
    """WebSocket message types."""
    TEST_PROGRESS = "test_progress"
    TEST_COMPLETE = "test_complete"
    EVALUATION_UPDATE = "evaluation_update"
    DOCUMENT_GENERATED = "document_generated"
    PROMPT_OPTIMIZED = "prompt_optimized"
    SYSTEM_NOTIFICATION = "system_notification"
    USER_NOTIFICATION = "user_notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

@dataclass
class WebSocketMessage:
    """Standard WebSocket message format."""
    id: str
    type: MessageType
    data: Dict[str, Any]
    timestamp: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['type'] = self.type.value
        return result

class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        # Active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        # Room-based connections for group messaging
        self.rooms: Dict[str, Set[WebSocket]] = {}
        
        # Message handlers
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        
        # Connection stats
        self.connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0
        }
    
    async def connect(
        self, 
        websocket: WebSocket, 
        user_id: str,
        session_id: Optional[str] = None,
        rooms: Optional[List[str]] = None
    ):
        """Accept a new WebSocket connection."""
        
        await websocket.accept()
        
        # Add to user connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "session_id": session_id or str(uuid.uuid4()),
            "connected_at": datetime.utcnow().isoformat(),
            "rooms": rooms or []
        }
        
        # Add to rooms
        if rooms:
            for room in rooms:
                if room not in self.rooms:
                    self.rooms[room] = set()
                self.rooms[room].add(websocket)
        
        # Update stats
        self.connection_stats["total_connections"] += 1
        self.connection_stats["active_connections"] = len(self._get_all_connections())
        
        logger.info(
            "WebSocket connection established",
            user_id=user_id,
            session_id=self.connection_metadata[websocket]["session_id"],
            rooms=rooms
        )
        
        # Send welcome message
        await self.send_personal_message(
            WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.SYSTEM_NOTIFICATION,
                data={
                    "message": "Connected to AI Compliance Platform",
                    "connection_id": self.connection_metadata[websocket]["session_id"]
                },
                timestamp=datetime.utcnow().isoformat(),
                user_id=user_id
            ),
            websocket
        )
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        
        if websocket not in self.connection_metadata:
            return
        
        metadata = self.connection_metadata[websocket]
        user_id = metadata["user_id"]
        
        # Remove from user connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove from rooms
        for room in metadata.get("rooms", []):
            if room in self.rooms:
                self.rooms[room].discard(websocket)
                if not self.rooms[room]:
                    del self.rooms[room]
        
        # Remove metadata
        del self.connection_metadata[websocket]
        
        # Update stats
        self.connection_stats["active_connections"] = len(self._get_all_connections())
        
        logger.info(
            "WebSocket connection closed",
            user_id=user_id,
            session_id=metadata.get("session_id")
        )
    
    async def send_personal_message(self, message: WebSocketMessage, websocket: WebSocket):
        """Send message to a specific WebSocket connection."""
        
        try:
            await websocket.send_text(json.dumps(message.to_dict()))
            self.connection_stats["messages_sent"] += 1
            
        except Exception as e:
            logger.error(
                "Failed to send WebSocket message",
                error=str(e),
                message_type=message.type.value
            )
            # Connection might be dead, remove it
            self.disconnect(websocket)
    
    async def send_user_message(self, message: WebSocketMessage, user_id: str):
        """Send message to all connections for a specific user."""
        
        if user_id not in self.active_connections:
            logger.warning("No active connections for user", user_id=user_id)
            return
        
        # Send to all user's connections
        dead_connections = []
        for websocket in self.active_connections[user_id].copy():
            try:
                await websocket.send_text(json.dumps(message.to_dict()))
                self.connection_stats["messages_sent"] += 1
                
            except Exception as e:
                logger.error(
                    "Failed to send message to user connection",
                    user_id=user_id,
                    error=str(e)
                )
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(websocket)
    
    async def send_room_message(self, message: WebSocketMessage, room: str):
        """Send message to all connections in a room."""
        
        if room not in self.rooms:
            logger.warning("Room not found", room=room)
            return
        
        dead_connections = []
        for websocket in self.rooms[room].copy():
            try:
                await websocket.send_text(json.dumps(message.to_dict()))
                self.connection_stats["messages_sent"] += 1
                
            except Exception as e:
                logger.error(
                    "Failed to send message to room connection",
                    room=room,
                    error=str(e)
                )
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(websocket)
    
    async def broadcast_message(self, message: WebSocketMessage):
        """Send message to all active connections."""
        
        all_connections = self._get_all_connections()
        dead_connections = []
        
        for websocket in all_connections:
            try:
                await websocket.send_text(json.dumps(message.to_dict()))
                self.connection_stats["messages_sent"] += 1
                
            except Exception as e:
                logger.error(
                    "Failed to broadcast message",
                    error=str(e)
                )
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(websocket)
    
    def _get_all_connections(self) -> Set[WebSocket]:
        """Get all active WebSocket connections."""
        
        all_connections = set()
        for connections in self.active_connections.values():
            all_connections.update(connections)
        return all_connections
    
    def add_message_handler(self, message_type: MessageType, handler: Callable):
        """Add a message handler for a specific message type."""
        
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    async def handle_message(self, websocket: WebSocket, message_data: Dict[str, Any]):
        """Handle incoming WebSocket message."""
        
        try:
            message_type = MessageType(message_data.get("type"))
            self.connection_stats["messages_received"] += 1
            
            # Call registered handlers
            if message_type in self.message_handlers:
                for handler in self.message_handlers[message_type]:
                    try:
                        await handler(websocket, message_data)
                    except Exception as e:
                        logger.error(
                            "Message handler failed",
                            message_type=message_type.value,
                            error=str(e)
                        )
            
        except ValueError:
            logger.error(
                "Invalid message type received",
                message_type=message_data.get("type")
            )
        except Exception as e:
            logger.error(
                "Failed to handle WebSocket message",
                error=str(e),
                message_data=message_data
            )
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        
        return {
            **self.connection_stats,
            "users_online": len(self.active_connections),
            "rooms_active": len(self.rooms),
            "connections_per_user": {
                user_id: len(connections) 
                for user_id, connections in self.active_connections.items()
            }
        }
    
    def get_user_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """Get connection info for a specific user."""
        
        if user_id not in self.active_connections:
            return []
        
        connections_info = []
        for websocket in self.active_connections[user_id]:
            if websocket in self.connection_metadata:
                metadata = self.connection_metadata[websocket]
                connections_info.append({
                    "session_id": metadata["session_id"],
                    "connected_at": metadata["connected_at"],
                    "rooms": metadata.get("rooms", [])
                })
        
        return connections_info

# Global connection manager instance
connection_manager = ConnectionManager()

class WebSocketNotifier:
    """High-level interface for sending notifications via WebSocket."""
    
    def __init__(self, manager: ConnectionManager = None):
        self.manager = manager or connection_manager
    
    async def notify_test_progress(
        self, 
        user_id: str, 
        test_id: str, 
        progress: float,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Notify about test execution progress."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.TEST_PROGRESS,
            data={
                "test_id": test_id,
                "progress": progress,
                "status": status,
                "details": details or {}
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def notify_test_complete(
        self, 
        user_id: str, 
        test_id: str, 
        results: Dict[str, Any]
    ):
        """Notify about test completion."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.TEST_COMPLETE,
            data={
                "test_id": test_id,
                "results": results
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def notify_evaluation_update(
        self, 
        user_id: str, 
        evaluation_id: str, 
        update_data: Dict[str, Any]
    ):
        """Notify about evaluation updates."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.EVALUATION_UPDATE,
            data={
                "evaluation_id": evaluation_id,
                **update_data
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def notify_document_generated(
        self, 
        user_id: str, 
        document_id: str, 
        document_info: Dict[str, Any]
    ):
        """Notify about document generation completion."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.DOCUMENT_GENERATED,
            data={
                "document_id": document_id,
                **document_info
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def notify_prompt_optimized(
        self, 
        user_id: str, 
        optimization_id: str, 
        optimization_results: Dict[str, Any]
    ):
        """Notify about prompt optimization completion."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.PROMPT_OPTIMIZED,
            data={
                "optimization_id": optimization_id,
                **optimization_results
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def notify_error(
        self, 
        user_id: str, 
        error_message: str, 
        error_details: Optional[Dict[str, Any]] = None
    ):
        """Notify about errors."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.ERROR,
            data={
                "message": error_message,
                "details": error_details or {}
            },
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id
        )
        
        await self.manager.send_user_message(message, user_id)
    
    async def broadcast_system_notification(
        self, 
        notification_message: str, 
        notification_data: Optional[Dict[str, Any]] = None
    ):
        """Broadcast system-wide notification."""
        
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.SYSTEM_NOTIFICATION,
            data={
                "message": notification_message,
                "data": notification_data or {}
            },
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.manager.broadcast_message(message)

# Global notifier instance
websocket_notifier = WebSocketNotifier()

@asynccontextmanager
async def websocket_connection(websocket: WebSocket, user_id: str, **kwargs):
    """Context manager for WebSocket connections."""
    
    await connection_manager.connect(websocket, user_id, **kwargs)
    try:
        yield websocket
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(websocket)

async def websocket_heartbeat():
    """Send periodic heartbeat messages to maintain connections."""
    
    while True:
        try:
            message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.HEARTBEAT,
                data={"timestamp": datetime.utcnow().isoformat()},
                timestamp=datetime.utcnow().isoformat()
            )
            
            await connection_manager.broadcast_message(message)
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
        except Exception as e:
            logger.error("Heartbeat failed", error=str(e))
            await asyncio.sleep(5)  # Retry after 5 seconds on error