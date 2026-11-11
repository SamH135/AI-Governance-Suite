"""WebSocket connection manager for the gateway service."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

# Import custom logger
from ..logger_util import logger

from ..shared.cache import get_redis_client
from ..shared.config import get_settings

class WebSocketManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        logger.info("Initializing WebSocket manager", function="__init__")
        # Map of user_id to list of WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # Map of user_id to set of subscribed channels
        self.user_subscriptions: Dict[int, Set[str]] = {}
        # Map of channel to set of user_ids
        self.channel_subscribers: Dict[str, Set[int]] = {}
        # Redis client for pub/sub
        self.redis_client = None
        self.redis_subscriber = None
        logger.info("WebSocket manager initialized", function="__init__")
        
    async def initialize(self):
        """Initialize Redis connections for pub/sub."""
        logger.info("Starting WebSocket manager Redis initialization", function="initialize")
        
        try:
            logger.debug("Getting Redis client", function="initialize")
            self.redis_client = get_redis_client()
            self.redis_subscriber = self.redis_client.pubsub()
            
            # Subscribe to relevant channels
            channels = [
                "test_progress:*",
                "compliance_update:*", 
                "document_update:*",
                "prompt_update:*",
                "system_notification"
            ]
            logger.info("Subscribing to Redis channels", function="initialize", channels=channels)
            await self.redis_subscriber.subscribe(*channels)
            
            # Start Redis message handler
            logger.debug("Starting Redis message handler task", function="initialize")
            asyncio.create_task(self._handle_redis_messages())
            
            logger.info("WebSocket manager initialized with Redis pub/sub successfully", function="initialize")
        except Exception as e:
            logger.error("Failed to initialize WebSocket manager", function="initialize", error=str(e))
            raise
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept a WebSocket connection."""
        logger.info("WebSocket connection attempt", function="connect", user_id=user_id)
        
        try:
            await websocket.accept()
            logger.debug("WebSocket connection accepted", function="connect", user_id=user_id)
            
            if user_id not in self.active_connections:
                logger.debug("Creating new user connection entry", function="connect", user_id=user_id)
                self.active_connections[user_id] = []
                self.user_subscriptions[user_id] = set()
            
            self.active_connections[user_id].append(websocket)
            connection_count = len(self.active_connections[user_id])
            total_users = len(self.active_connections)
            
            logger.info("WebSocket connected successfully", function="connect", user_id=user_id, user_connections=connection_count, total_users=total_users)
        except Exception as e:
            logger.error("Failed to establish WebSocket connection", function="connect", user_id=user_id, error=str(e))
            raise
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection."""
        logger.info("WebSocket disconnection request", function="disconnect", user_id=user_id)
        
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                logger.debug("WebSocket connection removed from active list", function="disconnect", user_id=user_id)
                
                # Clean up if no more connections for this user
                if not self.active_connections[user_id]:
                    logger.debug("No more connections for user, cleaning up subscriptions", function="disconnect", user_id=user_id)
                    del self.active_connections[user_id]
                    
                    # Remove user from all channel subscriptions
                    if user_id in self.user_subscriptions:
                        channels_unsubscribed = list(self.user_subscriptions[user_id])
                        for channel in channels_unsubscribed:
                            if channel in self.channel_subscribers:
                                self.channel_subscribers[channel].discard(user_id)
                                if not self.channel_subscribers[channel]:
                                    del self.channel_subscribers[channel]
                        del self.user_subscriptions[user_id]
                        logger.debug("User unsubscribed from all channels", function="disconnect", user_id=user_id, channels=channels_unsubscribed)
                
                remaining_connections = len(self.active_connections.get(user_id, []))
                total_users = len(self.active_connections)
                logger.info("WebSocket disconnected successfully", function="disconnect", user_id=user_id, remaining_connections=remaining_connections, total_users=total_users)
            except ValueError:
                logger.warn("Attempted to remove WebSocket that was already removed", function="disconnect", user_id=user_id)
        else:
            logger.warn("Attempted to disconnect user with no active connections", function="disconnect", user_id=user_id)
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user's WebSocket connections."""
        logger.debug("Sending personal message", function="send_personal_message", user_id=user_id, message_type=message.get("type"))
        
        if user_id not in self.active_connections:
            logger.debug("User has no active connections", function="send_personal_message", user_id=user_id)
            return
        
        message_with_timestamp = {
            **message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all connections for this user
        connections_to_remove = []
        connection_count = len(self.active_connections[user_id])
        logger.debug("Sending to user connections", function="send_personal_message", user_id=user_id, connection_count=connection_count)
        
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message_with_timestamp)
            except Exception as e:
                logger.error("Failed to send WebSocket message to connection", function="send_personal_message", user_id=user_id, error=str(e))
                connections_to_remove.append(websocket)
        
        # Clean up failed connections
        if connections_to_remove:
            logger.warn("Cleaning up failed connections", function="send_personal_message", user_id=user_id, failed_count=len(connections_to_remove))
            for websocket in connections_to_remove:
                self.disconnect(websocket, user_id)
        
        successful_sends = connection_count - len(connections_to_remove)
        logger.debug("Personal message sent", function="send_personal_message", user_id=user_id, successful_sends=successful_sends)
    
    async def broadcast_to_channel(self, message: dict, channel: str):
        """Broadcast a message to all users subscribed to a channel."""
        logger.debug("Broadcasting message to channel", function="broadcast_to_channel", channel=channel, message_type=message.get("type"))
        
        if channel not in self.channel_subscribers:
            logger.debug("Channel has no subscribers", function="broadcast_to_channel", channel=channel)
            return
        
        subscribers = list(self.channel_subscribers[channel])
        logger.info("Broadcasting to channel subscribers", function="broadcast_to_channel", channel=channel, subscriber_count=len(subscribers))
        
        for user_id in subscribers:
            await self.send_personal_message(message, user_id)
        
        logger.debug("Channel broadcast completed", function="broadcast_to_channel", channel=channel, subscriber_count=len(subscribers))
    
    def subscribe_user(self, user_id: int, channel: str):
        """Subscribe a user to a channel."""
        logger.info("User channel subscription request", function="subscribe_user", user_id=user_id, channel=channel)
        
        if user_id not in self.user_subscriptions:
            logger.debug("Creating user subscription set", function="subscribe_user", user_id=user_id)
            self.user_subscriptions[user_id] = set()
        
        # Check if already subscribed
        if channel in self.user_subscriptions[user_id]:
            logger.debug("User already subscribed to channel", function="subscribe_user", user_id=user_id, channel=channel)
            return
        
        self.user_subscriptions[user_id].add(channel)
        
        if channel not in self.channel_subscribers:
            logger.debug("Creating channel subscriber set", function="subscribe_user", channel=channel)
            self.channel_subscribers[channel] = set()
        
        self.channel_subscribers[channel].add(user_id)
        
        channel_subscriber_count = len(self.channel_subscribers[channel])
        user_subscription_count = len(self.user_subscriptions[user_id])
        
        logger.info("User subscribed to channel successfully", function="subscribe_user", user_id=user_id, channel=channel, channel_subscribers=channel_subscriber_count, user_subscriptions=user_subscription_count)
    
    def unsubscribe_user(self, user_id: int, channel: str):
        """Unsubscribe a user from a channel."""
        logger.info("User channel unsubscription request", function="unsubscribe_user", user_id=user_id, channel=channel)
        
        was_subscribed = False
        
        if user_id in self.user_subscriptions:
            if channel in self.user_subscriptions[user_id]:
                was_subscribed = True
                self.user_subscriptions[user_id].discard(channel)
                logger.debug("Removed channel from user subscriptions", function="unsubscribe_user", user_id=user_id, channel=channel)
        
        if channel in self.channel_subscribers:
            self.channel_subscribers[channel].discard(user_id)
            if not self.channel_subscribers[channel]:
                logger.debug("Channel has no more subscribers, removing", function="unsubscribe_user", channel=channel)
                del self.channel_subscribers[channel]
        
        if was_subscribed:
            remaining_channel_subscribers = len(self.channel_subscribers.get(channel, set()))
            remaining_user_subscriptions = len(self.user_subscriptions.get(user_id, set()))
            logger.info("User unsubscribed from channel successfully", function="unsubscribe_user", user_id=user_id, channel=channel, remaining_channel_subscribers=remaining_channel_subscribers, remaining_user_subscriptions=remaining_user_subscriptions)
        else:
            logger.debug("User was not subscribed to channel", function="unsubscribe_user", user_id=user_id, channel=channel)
    
    async def handle_message(self, websocket: WebSocket, user_id: int, message_data: dict):
        """Handle incoming WebSocket messages."""
        message_type = message_data.get("type")
        logger.debug("Handling WebSocket message", function="handle_message", user_id=user_id, message_type=message_type)
        
        try:
            if message_type == "subscribe":
                channel = message_data.get("channel")
                if channel:
                    logger.info("Processing subscription request", function="handle_message", user_id=user_id, channel=channel)
                    self.subscribe_user(user_id, channel)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "channel": channel,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.debug("Subscription confirmation sent", function="handle_message", user_id=user_id, channel=channel)
                else:
                    logger.warn("Subscribe request missing channel", function="handle_message", user_id=user_id)
            
            elif message_type == "unsubscribe":
                channel = message_data.get("channel")
                if channel:
                    logger.info("Processing unsubscription request", function="handle_message", user_id=user_id, channel=channel)
                    self.unsubscribe_user(user_id, channel)
                    await websocket.send_json({
                        "type": "unsubscription_confirmed",
                        "channel": channel,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.debug("Unsubscription confirmation sent", function="handle_message", user_id=user_id, channel=channel)
                else:
                    logger.warn("Unsubscribe request missing channel", function="handle_message", user_id=user_id)
            
            elif message_type == "ping":
                logger.debug("Processing ping request", function="handle_message", user_id=user_id)
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            else:
                logger.warn("Unknown WebSocket message type received", function="handle_message", user_id=user_id, message_type=message_type)
        
        except Exception as e:
            logger.error("Error handling WebSocket message", function="handle_message", user_id=user_id, message_type=message_type, error=str(e))
    
    async def _handle_redis_messages(self):
        """Handle messages from Redis pub/sub."""
        logger.info("Starting Redis message handler", function="_handle_redis_messages")
        
        if not self.redis_subscriber:
            logger.error("No Redis subscriber available", function="_handle_redis_messages")
            return
        
        try:
            async for message in self.redis_subscriber.listen():
                if message["type"] == "message":
                    channel = message["channel"].decode()
                    data = message["data"].decode()
                    logger.debug("Received Redis message", function="_handle_redis_messages", channel=channel)
                    await self._process_redis_message(channel, data)
        except Exception as e:
            logger.error("Redis message handler error occurred", function="_handle_redis_messages", error=str(e))
    
    async def _process_redis_message(self, channel: str, data: str):
        """Process a message received from Redis."""
        logger.debug("Processing Redis message", function="_process_redis_message", channel=channel)
        
        try:
            message_data = json.loads(data)
            logger.debug("Redis message parsed successfully", function="_process_redis_message", channel=channel)
            
            if channel.startswith("test_progress:"):
                execution_id = channel.split(":", 1)[1]
                target_channel = f"test_execution:{execution_id}"
                logger.info("Broadcasting test progress update", function="_process_redis_message", execution_id=execution_id, target_channel=target_channel)
                await self.broadcast_to_channel({
                    "type": "test_progress_update",
                    "payload": message_data
                }, target_channel)
            
            elif channel.startswith("compliance_update:"):
                system_id = channel.split(":", 1)[1]
                target_channel = f"compliance:{system_id}"
                logger.info("Broadcasting compliance update", function="_process_redis_message", system_id=system_id, target_channel=target_channel)
                await self.broadcast_to_channel({
                    "type": "compliance_update",
                    "payload": message_data
                }, target_channel)
            
            elif channel.startswith("document_update:"):
                document_id = channel.split(":", 1)[1]
                target_channel = f"document:{document_id}"
                logger.info("Broadcasting document update", function="_process_redis_message", document_id=document_id, target_channel=target_channel)
                await self.broadcast_to_channel({
                    "type": "document_update",
                    "payload": message_data
                }, target_channel)
            
            elif channel.startswith("prompt_update:"):
                prompt_id = channel.split(":", 1)[1]
                target_channel = f"prompt:{prompt_id}"
                logger.info("Broadcasting prompt update", function="_process_redis_message", prompt_id=prompt_id, target_channel=target_channel)
                await self.broadcast_to_channel({
                    "type": "prompt_update",
                    "payload": message_data
                }, target_channel)
            
            elif channel == "system_notification":
                # Broadcast to all connected users
                connected_users = list(self.active_connections.keys())
                logger.info("Broadcasting system notification to all users", function="_process_redis_message", user_count=len(connected_users))
                
                for user_id in connected_users:
                    await self.send_personal_message({
                        "type": "system_notification",
                        "payload": message_data
                    }, user_id)
            
            else:
                logger.warn("Unknown Redis channel pattern", function="_process_redis_message", channel=channel)
        
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in Redis message", function="_process_redis_message", channel=channel, data=data, error=str(e))
        except Exception as e:
            logger.error("Error processing Redis message", function="_process_redis_message", channel=channel, error=str(e))
    
    def get_connection_stats(self) -> dict:
        """Get connection statistics."""
        logger.debug("Generating connection statistics", function="get_connection_stats")
        
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        total_users = len(self.active_connections)
        total_channels = len(self.channel_subscribers)
        total_subscriptions = sum(len(subs) for subs in self.user_subscriptions.values())
        
        stats = {
            "total_users": total_users,
            "total_connections": total_connections,
            "channels": total_channels,
            "subscriptions": total_subscriptions
        }
        
        logger.debug("Connection statistics generated", function="get_connection_stats", **stats)
        return stats
    
    def get_user_connections(self, user_id: int) -> List[dict]:
        """Get connection information for a specific user."""
        logger.debug("Getting user connection information", function="get_user_connections", user_id=user_id)
        
        if user_id not in self.active_connections:
            logger.debug("User has no active connections", function="get_user_connections", user_id=user_id)
            return []
        
        connections = []
        user_subscriptions = list(self.user_subscriptions.get(user_id, set()))
        
        for i, websocket in enumerate(self.active_connections[user_id]):
            connections.append({
                "connection_id": i,
                "state": websocket.client_state.name,
                "subscriptions": user_subscriptions
            })
        
        logger.debug("User connection information retrieved", function="get_user_connections", user_id=user_id, connection_count=len(connections), subscription_count=len(user_subscriptions))
        return connections
    
    async def broadcast_system_notification(self, message: str, data: dict = None):
        """Broadcast a system-wide notification."""
        connected_users = list(self.active_connections.keys())
        logger.info("Broadcasting system notification", function="broadcast_system_notification", message=message, user_count=len(connected_users))
        
        notification = {
            "type": "system_notification",
            "payload": {
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Send to all connected users
        for user_id in connected_users:
            await self.send_personal_message(notification, user_id)
        
        logger.info("System notification broadcast completed", function="broadcast_system_notification", user_count=len(connected_users))

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

async def get_current_user_websocket(token: str) -> Optional[dict]:
    """Get current user from WebSocket token."""
    logger.debug("Authenticating WebSocket user from token", function="get_current_user_websocket", has_token=bool(token))
    
    if not token:
        logger.debug("No token provided for WebSocket authentication", function="get_current_user_websocket")
        return None
    
    try:
        settings = get_settings()
        logger.debug("Decoding WebSocket JWT token", function="get_current_user_websocket")
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("sub")
        
        if user_id is None:
            logger.warn("JWT token missing user_id", function="get_current_user_websocket")
            return None
        
        # In a real implementation, you might want to verify the user exists in the database
        user_info = {
            "user_id": user_id,
            "username": username,
            "role": payload.get("role")
        }
        
        logger.debug("WebSocket user authenticated successfully", function="get_current_user_websocket", user_id=user_id, username=username)
        return user_info
        
    except JWTError as e:
        logger.warn("JWT error during WebSocket authentication", function="get_current_user_websocket", error=str(e))
        return None
    except Exception as e:
        logger.error("Unexpected error during WebSocket authentication", function="get_current_user_websocket", error=str(e))
        return None