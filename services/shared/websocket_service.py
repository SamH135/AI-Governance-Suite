"""
Shared WebSocket Service
Provides real-time communication capabilities across all services
"""

import json
import asyncio
from typing import Dict, Set, Any, Optional, List
from datetime import datetime
import structlog
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

from .redis_client import redis_client
from .exceptions import PlatformError

logger = structlog.get_logger()

class WebSocketManager:
    """Manages WebSocket connections and real-time communication."""
    
    def __init__(self):
        # Active connections by user ID
        self.active_connections: Dict[int, WebSocket] = {}
        
        # User subscriptions to channels
        self.user_subscriptions: Dict[int, Set[str]] = {}
        
        # Channel subscriptions (which users are subscribed to which channels)
        self.channel_subscriptions: Dict[str, Set[int]] = {}
        
        # Service-specific connections
        self.service_connections: Dict[str, Set[int]] = {}
        
        self.initialized = False
        self._redis_subscriber = None
        self._subscriber_task = None
    
    async def initialize(self):
        """Initialize the WebSocket manager."""
        if self.initialized:
            return
        
        try:
            # Start Redis subscriber for cross-service communication
            await self._start_redis_subscriber()
            self.initialized = True
            logger.info("WebSocket manager initialized")
            
        except Exception as e:
            logger.error("Failed to initialize WebSocket manager", error=str(e))
            raise PlatformError("WebSocket initialization failed")
    
    async def connect(self, websocket: WebSocket, user_id: int, service: str = "gateway"):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        # Store connection
        self.active_connections[user_id] = websocket
        
        # Initialize user subscriptions
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        
        # Track service connections
        if service not in self.service_connections:
            self.service_connections[service] = set()
        self.service_connections[service].add(user_id)
        
        logger.info("WebSocket connected", user_id=user_id, service=service)
        
        # Send welcome message
        await self.send_personal_message(user_id, {
            "type": "connection_established",
            "service": service,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def disconnect(self, user_id: int, service: str = "gateway"):
        """Handle WebSocket disconnection."""
        # Remove from active connections
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        # Clean up subscriptions
        if user_id in self.user_subscriptions:
            # Remove user from all channels
            for channel in self.user_subscriptions[user_id]:
                if channel in self.channel_subscriptions:
                    self.channel_subscriptions[channel].discard(user_id)
                    if not self.channel_subscriptions[channel]:
                        del self.channel_subscriptions[channel]
            
            del self.user_subscriptions[user_id]
        
        # Remove from service connections
        if service in self.service_connections:
            self.service_connections[service].discard(user_id)
            if not self.service_connections[service]:
                del self.service_connections[service]
        
        logger.info("WebSocket disconnected", user_id=user_id, service=service)
    
    async def send_personal_message(self, user_id: int, message: Dict[str, Any]):
        """Send a message to a specific user."""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json({
                    **message,
                    "timestamp": datetime.utcnow().isoformat()
                })
                logger.debug("Message sent to user", user_id=user_id, type=message.get("type"))
                
            except Exception as e:
                logger.error("Failed to send WebSocket message", 
                           user_id=user_id, error=str(e))
                # Connection is broken, clean up
                self.disconnect(user_id)
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all users subscribed to a channel."""
        if channel in self.channel_subscriptions:
            user_ids = list(self.channel_subscriptions[channel])
            
            # Send to all subscribed users
            tasks = []
            for user_id in user_ids:
                task = self.send_personal_message(user_id, {
                    **message,
                    "channel": channel
                })
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.debug("Message broadcasted to channel", 
                           channel=channel, user_count=len(user_ids))
    
    async def broadcast_to_service(self, service: str, message: Dict[str, Any]):
        """Broadcast a message to all users connected to a specific service."""
        if service in self.service_connections:
            user_ids = list(self.service_connections[service])
            
            tasks = []
            for user_id in user_ids:
                task = self.send_personal_message(user_id, {
                    **message,
                    "service": service
                })
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.debug("Message broadcasted to service", 
                           service=service, user_count=len(user_ids))
    
    async def subscribe_user(self, user_id: int, channel: str):
        """Subscribe a user to a channel."""
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        
        self.user_subscriptions[user_id].add(channel)
        
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()
        
        self.channel_subscriptions[channel].add(user_id)
        
        logger.debug("User subscribed to channel", user_id=user_id, channel=channel)
        
        # Send confirmation
        await self.send_personal_message(user_id, {
            "type": "subscription_confirmed",
            "channel": channel
        })
    
    async def unsubscribe_user(self, user_id: int, channel: str):
        """Unsubscribe a user from a channel."""
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(channel)
        
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(user_id)
            if not self.channel_subscriptions[channel]:
                del self.channel_subscriptions[channel]
        
        logger.debug("User unsubscribed from channel", user_id=user_id, channel=channel)
        
        # Send confirmation
        await self.send_personal_message(user_id, {
            "type": "unsubscription_confirmed", 
            "channel": channel
        })
    
    async def publish_cross_service(self, channel: str, message: Dict[str, Any]):
        """Publish a message across services via Redis."""
        try:
            message_data = {
                **message,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "websocket_service"
            }
            
            await redis_client.publish(
                f"websocket:{channel}",
                json.dumps(message_data)
            )
            
            logger.debug("Message published cross-service", channel=channel)
            
        except Exception as e:
            logger.error("Failed to publish cross-service message", 
                        channel=channel, error=str(e))
    
    async def handle_message(self, user_id: int, message: Dict[str, Any]):
        """Handle incoming WebSocket message from client."""
        message_type = message.get("type")
        
        try:
            if message_type == "subscribe":
                channel = message.get("channel")
                if channel:
                    await self.subscribe_user(user_id, channel)
            
            elif message_type == "unsubscribe":
                channel = message.get("channel")
                if channel:
                    await self.unsubscribe_user(user_id, channel)
            
            elif message_type == "ping":
                await self.send_personal_message(user_id, {
                    "type": "pong"
                })
            
            elif message_type == "get_status":
                await self._send_user_status(user_id)
            
            else:
                logger.warning("Unknown message type", user_id=user_id, type=message_type)
                await self.send_personal_message(user_id, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
        
        except Exception as e:
            logger.error("Error handling WebSocket message", 
                        user_id=user_id, error=str(e))
            await self.send_personal_message(user_id, {
                "type": "error",
                "message": "Failed to process message"
            })
    
    async def _send_user_status(self, user_id: int):
        """Send current user status and subscriptions."""
        subscriptions = list(self.user_subscriptions.get(user_id, set()))
        
        await self.send_personal_message(user_id, {
            "type": "user_status",
            "user_id": user_id,
            "subscriptions": subscriptions,
            "active_connections": len(self.active_connections),
            "total_channels": len(self.channel_subscriptions)
        })
    
    async def _start_redis_subscriber(self):
        """Start Redis subscriber for cross-service messages."""
        try:
            # Create Redis subscriber
            self._redis_subscriber = redis_client.redis_client.pubsub()
            
            # Subscribe to websocket channels
            await self._redis_subscriber.psubscribe("websocket:*")
            
            # Start subscriber task
            self._subscriber_task = asyncio.create_task(self._redis_message_handler())
            
            logger.info("Redis WebSocket subscriber started")
            
        except Exception as e:
            logger.error("Failed to start Redis subscriber", error=str(e))
            raise
    
    async def _redis_message_handler(self):
        """Handle incoming Redis messages."""
        try:
            async for message in self._redis_subscriber.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"].decode()
                    data = message["data"].decode()
                    
                    try:
                        # Extract channel name (remove websocket: prefix)
                        ws_channel = channel.replace("websocket:", "")
                        
                        # Parse message data
                        message_data = json.loads(data)
                        
                        # Broadcast to subscribed users
                        await self.broadcast_to_channel(ws_channel, message_data)
                        
                    except Exception as e:
                        logger.error("Error processing Redis message", 
                                   channel=channel, error=str(e))
        
        except asyncio.CancelledError:
            logger.info("Redis message handler cancelled")
        except Exception as e:
            logger.error("Redis message handler error", error=str(e))
    
    async def close(self):
        """Close WebSocket manager and cleanup resources."""
        # Cancel Redis subscriber task
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        
        # Close Redis subscriber
        if self._redis_subscriber:
            await self._redis_subscriber.unsubscribe()
            await self._redis_subscriber.close()
        
        # Close all WebSocket connections
        close_tasks = []
        for user_id, websocket in list(self.active_connections.items()):
            try:
                close_tasks.append(websocket.close())
            except Exception:
                pass
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Clear all data structures
        self.active_connections.clear()
        self.user_subscriptions.clear()
        self.channel_subscriptions.clear()
        self.service_connections.clear()
        
        logger.info("WebSocket manager closed")

# Real-time update helpers
class RealTimeUpdates:
    """Helper class for sending real-time updates."""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
    
    async def test_progress_update(self, test_id: int, progress: int, status: str, details: Dict[str, Any]):
        """Send test progress update."""
        await self.ws_manager.broadcast_to_channel(f"test_progress:{test_id}", {
            "type": "test_progress",
            "test_id": test_id,
            "progress": progress,
            "status": status,
            "details": details
        })
    
    async def compliance_result_update(self, system_id: int, result: Dict[str, Any]):
        """Send compliance test result update."""
        await self.ws_manager.broadcast_to_channel(f"compliance_results:{system_id}", {
            "type": "compliance_result",
            "system_id": system_id,
            "result": result
        })
    
    async def document_generation_update(self, doc_id: int, status: str, progress: int):
        """Send document generation progress update."""
        await self.ws_manager.broadcast_to_channel(f"document_progress:{doc_id}", {
            "type": "document_progress",
            "document_id": doc_id,
            "status": status,
            "progress": progress
        })
    
    async def prompt_optimization_update(self, prompt_id: int, iteration: int, score: float):
        """Send prompt optimization progress update."""
        await self.ws_manager.broadcast_to_channel(f"prompt_optimization:{prompt_id}", {
            "type": "prompt_optimization",
            "prompt_id": prompt_id,
            "iteration": iteration,
            "score": score
        })
    
    async def system_alert(self, alert_type: str, message: str, severity: str = "info"):
        """Send system-wide alert."""
        await self.ws_manager.broadcast_to_channel("system_alerts", {
            "type": "system_alert",
            "alert_type": alert_type,
            "message": message,
            "severity": severity
        })
    
    async def user_notification(self, user_id: int, notification: Dict[str, Any]):
        """Send notification to specific user."""
        await self.ws_manager.send_personal_message(user_id, {
            "type": "notification",
            **notification
        })

# Global WebSocket manager instance
websocket_manager = WebSocketManager()
real_time_updates = RealTimeUpdates(websocket_manager)