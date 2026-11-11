"""WebSocket routes for the gateway service."""

import asyncio
import json
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
import structlog
import httpx

from .websocket.manager import websocket_manager, get_current_user_websocket
from .routes.auth import get_current_user
from .shared.config import get_settings

logger = structlog.get_logger()
security = HTTPBearer()

# Global HTTP client for service calls
http_client: Optional[httpx.AsyncClient] = None

def set_http_client(client: httpx.AsyncClient):
    """Set the HTTP client for WebSocket routes (called from main.py)."""
    global http_client
    http_client = client

router = APIRouter(prefix="/ws", tags=["websocket"])

# Background task for heartbeat
heartbeat_task = None

async def refresh_dashboard_data() -> dict:
    """Refresh dashboard data from all services."""
    settings = get_settings()
    dashboard_data = {
        "active_tests": 0,
        "completed_tests": 0,
        "active_users": len(websocket_manager.active_connections),
        "system_status": "healthy",
        "last_updated": "now"
    }

    try:
        # Fetch test statistics from tests service
        tests_response = await http_client.get(
            f"{settings.TESTS_SERVICE_URL}/api/executions/?status=running",
            headers={"X-User-ID": "0"}
        )
        if tests_response.status_code == 200:
            tests_data = tests_response.json()
            dashboard_data["active_tests"] = len(tests_data.get("data", {}).get("items", []))

        completed_response = await http_client.get(
            f"{settings.TESTS_SERVICE_URL}/api/executions/?status=completed",
            headers={"X-User-ID": "0"}
        )
        if completed_response.status_code == 200:
            completed_data = completed_response.json()
            dashboard_data["completed_tests"] = len(completed_data.get("data", {}).get("items", []))

        # Fetch analytics data
        analytics_response = await http_client.get(
            f"{settings.ANALYTICS_SERVICE_URL}/api/metrics/summary",
            headers={"X-User-ID": "0"}
        )
        if analytics_response.status_code == 200:
            analytics_data = analytics_response.json()
            dashboard_data["analytics"] = analytics_data.get("data", {})

        # Fetch compliance data
        compliance_response = await http_client.get(
            f"{settings.COMPLIANCE_SERVICE_URL}/api/systems/",
            headers={"X-User-ID": "0"}
        )
        if compliance_response.status_code == 200:
            compliance_data = compliance_response.json()
            dashboard_data["total_systems"] = len(compliance_data.get("data", []))

    except Exception as e:
        logger.error("Failed to refresh dashboard data", error=str(e))
        dashboard_data["system_status"] = "degraded"

    return dashboard_data

async def get_user_from_token(token: Optional[str] = None) -> Optional[dict]:
    """Extract user from WebSocket token parameter."""
    
    if not token:
        return None
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        return await get_current_user_websocket(token)
        
    except Exception as e:
        logger.error("WebSocket authentication failed", error=str(e))
        return None

@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    rooms: Optional[str] = Query(None)
):
    """Main WebSocket endpoint for real-time communication."""
    
    # Authenticate user
    user_data = await get_user_from_token(token)
    if not user_data:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    user_id = user_data.get("user_id")
    if not user_id:
        await websocket.close(code=4002, reason="Invalid user data")
        return
    
    # Parse rooms and subscribe user to them
    room_list = []
    if rooms:
        room_list = [room.strip() for room in rooms.split(",") if room.strip()]
    
    # Connect to WebSocket manager
    await websocket_manager.connect(websocket, user_id)
    
    # Subscribe to requested rooms
    for room in room_list:
        websocket_manager.subscribe_user(user_id, room)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                await websocket_manager.handle_message(websocket, user_id, message_data)
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received from WebSocket", data=data)
                await websocket.send_json({
                    "type": "error",
                    "payload": {
                        "message": "Invalid message format",
                        "received_data": data
                    }
                })
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", user_id=user_id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user_id, error=str(e))
    finally:
        websocket_manager.disconnect(websocket, user_id)

@router.websocket("/test/{test_id}")
async def test_websocket(
    websocket: WebSocket,
    test_id: str,
    token: Optional[str] = Query(None)
):
    """WebSocket endpoint for test-specific updates."""
    
    # Authenticate user
    user_data = await get_user_from_token(token)
    if not user_data:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    user_id = user_data.get("user_id")
    if not user_id:
        await websocket.close(code=4002, reason="Invalid user data")
        return
    
    # Connect to test-specific room
    room = f"test_{test_id}"
    
    # Connect to WebSocket manager
    await websocket_manager.connect(websocket, user_id)
    websocket_manager.subscribe_user(user_id, room)
    
    try:
        # Send initial test status
        await websocket.send_json({
            "type": "test_progress_update",
            "payload": {
                "test_id": test_id,
                "progress": 0.0,
                "status": "connected",
                "message": f"Connected to test {test_id} updates"
            }
        })
        
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                
                # Handle test-specific commands
                if message_data.get("type") == "get_status":
                    # Get actual test status from tests service
                    try:
                        from src.shared.config import get_settings
                        settings = get_settings()
                        
                        # Call tests service to get execution status
                        status_response = await http_client.get(
                            f"{settings.TESTS_SERVICE_URL}/api/executions/{test_id}/status",
                            headers={"X-User-ID": str(user_id)}
                        )
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            await websocket.send_json({
                                "type": "test_progress_update",
                                "payload": {
                                    "test_id": test_id,
                                    "progress": status_data.get("data", {}).get("progress", 0),
                                    "status": status_data.get("data", {}).get("status", "unknown"),
                                    "message": status_data.get("data", {}).get("message", "Test status retrieved")
                                }
                            })
                        else:
                            logger.error("Failed to get test status from tests service", status_code=status_response.status_code)
                            await websocket.send_json({
                                "type": "test_progress_update",
                                "payload": {
                                    "test_id": test_id,
                                    "progress": 0,
                                    "status": "error",
                                    "message": "Failed to retrieve test status"
                                }
                            })
                    except Exception as e:
                        logger.error("Error fetching test status from tests service", error=str(e))
                        await websocket.send_json({
                            "type": "test_progress_update",
                            "payload": {
                                "test_id": test_id,
                                "progress": 0,
                                "status": "error",
                                "message": "Error retrieving test status"
                            }
                        })
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in test WebSocket", data=data)
            
    except WebSocketDisconnect:
        logger.info("Test WebSocket disconnected", user_id=user_id, test_id=test_id)
    except Exception as e:
        logger.error("Test WebSocket error", user_id=user_id, test_id=test_id, error=str(e))
    finally:
        websocket_manager.disconnect(websocket, user_id)

@router.websocket("/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """WebSocket endpoint for dashboard real-time updates."""
    
    # Authenticate user
    user_data = await get_user_from_token(token)
    if not user_data:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    user_id = user_data.get("user_id")
    if not user_id:
        await websocket.close(code=4002, reason="Invalid user data")
        return
    
    # Connect to dashboard room
    room = "dashboard"
    
    # Connect to WebSocket manager
    await websocket_manager.connect(websocket, user_id)
    websocket_manager.subscribe_user(user_id, room)
    
    try:
        # Send initial dashboard data
        dashboard_data = await refresh_dashboard_data()
        await websocket.send_json({
            "type": "dashboard_data",
            "payload": dashboard_data
        })
        
        while True:
            # Handle dashboard-specific messages
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                
                if message_data.get("type") == "refresh_dashboard":
                    updated_data = await refresh_dashboard_data()
                    await websocket.send_json({
                        "type": "dashboard_data",
                        "payload": updated_data
                    })
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in dashboard WebSocket", data=data)
            
    except WebSocketDisconnect:
        logger.info("Dashboard WebSocket disconnected", user_id=user_id)
    except Exception as e:
        logger.error("Dashboard WebSocket error", user_id=user_id, error=str(e))
    finally:
        websocket_manager.disconnect(websocket, user_id)

# HTTP endpoints for WebSocket management

@router.get("/stats")
async def get_websocket_stats(current_user: dict = Depends(get_current_user)):
    """Get WebSocket connection statistics."""
    
    try:
        stats = websocket_manager.get_connection_stats()
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error("Failed to get WebSocket stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get WebSocket statistics")

@router.get("/connections/{user_id}")
async def get_user_connections(
    user_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get connection information for a specific user."""
    
    # Check if current user can view this information
    if current_user.get("user_id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        connections = websocket_manager.get_user_connections(user_id)
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "connections": connections,
                "total_connections": len(connections)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get user connections", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get user connections")

@router.post("/notify/user/{user_id}")
async def send_user_notification(
    user_id: int,
    notification_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Send notification to a specific user."""
    
    # Check permissions (admin or self)
    if current_user.get("user_id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        message = notification_data.get("message", "")
        details = notification_data.get("details", {})
        
        await websocket_manager.send_personal_message({
            "type": "notification",
            "payload": {
                "message": message,
                "details": details
            }
        }, user_id)
        
        return {
            "success": True,
            "message": "Notification sent successfully"
        }
        
    except Exception as e:
        logger.error("Failed to send user notification", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send notification")

@router.post("/broadcast")
async def broadcast_notification(
    notification_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Broadcast notification to all connected users."""
    
    # Only admins can broadcast
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        message = notification_data.get("message", "")
        data = notification_data.get("data", {})
        
        await websocket_notifier.broadcast_system_notification(message, data)
        
        return {
            "success": True,
            "message": "Broadcast sent successfully"
        }
        
    except Exception as e:
        logger.error("Failed to broadcast notification", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to broadcast notification")

@router.delete("/connections/{user_id}")
async def disconnect_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Disconnect all WebSocket connections for a user."""
    
    # Only admins can disconnect other users
    if current_user.get("user_id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        if user_id in websocket_manager.active_connections:
            connections = list(websocket_manager.active_connections[user_id])
            
            for websocket in connections:
                try:
                    await websocket.close(code=4003, reason="Disconnected by admin")
                except:
                    pass  # Connection might already be closed
                websocket_manager.disconnect(websocket)
            
            return {
                "success": True,
                "message": f"Disconnected {len(connections)} connections for user {user_id}"
            }
        else:
            return {
                "success": True,
                "message": f"No active connections found for user {user_id}"
            }
        
    except Exception as e:
        logger.error("Failed to disconnect user", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to disconnect user")