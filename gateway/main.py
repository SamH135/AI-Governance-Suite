"""
AI Compliance Platform - Python FastAPI Gateway
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, status, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, generate_latest
import structlog

# Import logging
from src.logger_util import logger

# Import local modules
from src.shared.config import get_settings
from src.shared.database import initialize_db_pool, get_db_pool, close_db_pool
from src.shared.cache import initialize_redis_client, get_redis_client, close_redis_client
from src.routes.auth import router as auth_router, get_current_user
from src.routes.health import router as health_router
from src.routes.models import router as models_router
from src.routes.api_keys import router as api_keys_router
from src.routes.systems import router as systems_router
from src.routes.test_execution import router as test_execution_router
from src.websocket.manager import websocket_manager, get_current_user_websocket
from src.websocket_routes import set_http_client as set_websocket_http_client
from src.websocket_routes import router as websocket_router

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Metrics
request_count = Counter('gateway_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('gateway_request_duration_seconds', 'Request duration')

# Structured logging
logger = structlog.get_logger()

# Global HTTP client
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Entering lifespan manager", function="lifespan")
    global http_client
    
    # Startup
    logger.info("Starting AI Compliance Gateway", function="lifespan", phase="startup")
    
    # Initialize database pool
    logger.info("Initializing database pool", function="lifespan", component="database")
    try:
        await initialize_db_pool()
        logger.info("Database pool initialized successfully", function="lifespan", component="database")
    except Exception as e:
        logger.error("Failed to initialize database pool", function="lifespan", component="database", error=str(e))
        raise
    
    # Initialize Redis
    logger.info("Initializing Redis client", function="lifespan", component="redis")
    try:
        await initialize_redis_client()
        logger.info("Redis connection established successfully", function="lifespan", component="redis")
    except Exception as e:
        logger.error("Failed to connect to Redis", function="lifespan", component="redis", error=str(e))
        raise
    
    # Initialize HTTP client
    logger.info("Initializing HTTP client", function="lifespan", component="http_client", timeout=30.0)
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("HTTP client initialized successfully", function="lifespan", component="http_client")
    
    # Set HTTP client for WebSocket routes
    set_websocket_http_client(http_client)
    
    # Initialize WebSocket manager
    logger.info("Initializing WebSocket manager", function="lifespan", component="websocket")
    try:
        await websocket_manager.initialize()
        logger.info("WebSocket manager initialized successfully", function="lifespan", component="websocket")
    except Exception as e:
        logger.error("Failed to initialize WebSocket manager", function="lifespan", component="websocket", error=str(e))
        # Don't fail startup if WebSocket manager fails
    
    logger.info("Application startup completed successfully", function="lifespan", phase="startup_complete")
    yield
    
    # Shutdown
    logger.info("Shutting down AI Compliance Gateway", function="lifespan", phase="shutdown")
    
    logger.info("Closing database pool", function="lifespan", component="database")
    await close_db_pool()
    
    logger.info("Closing Redis client", function="lifespan", component="redis")
    await close_redis_client()
    
    if http_client:
        logger.info("Closing HTTP client", function="lifespan", component="http_client")
        await http_client.aclose()
    
    logger.info("Application shutdown completed", function="lifespan", phase="shutdown_complete")

# FastAPI app
app = FastAPI(
    title="AI Compliance Platform Gateway",
    description="Central API gateway for the unified AI compliance platform",
    version="1.0.0",
    lifespan=lifespan
)

# Get settings
logger.info("Loading application settings", function="main")
settings = get_settings()
logger.info("Application settings loaded successfully", function="main")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost"]
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Helper functions for service proxying
async def forward_request(service_url: str, path: str, method: str, **kwargs) -> Dict[str, Any]:
    """Forward request to microservice"""
    url = f"{service_url.rstrip('/')}/{path.lstrip('/')}"
    logger.info("Forwarding request to microservice", function="forward_request", service_url=service_url, path=path, method=method, url=url)
    
    try:
        response = await http_client.request(method, url, **kwargs)
        logger.info("Received response from microservice", function="forward_request", status_code=response.status_code, url=url)
        response.raise_for_status()
        
        # Handle empty responses (like 204 No Content for DELETE operations)
        if response.status_code == 204 or not response.content:
            logger.info("Empty response received (likely 204 No Content)", function="forward_request", url=url)
            return {"success": True, "message": "Operation completed successfully"}
        
        result = response.json()
        logger.info("Successfully processed microservice response", function="forward_request", url=url)
        return result
    except httpx.HTTPError as e:
        logger.error("Service request failed", function="forward_request", service_url=service_url, path=path, method=method, error=str(e))
        raise HTTPException(status_code=500, detail="Service unavailable")
    except Exception as e:
        logger.error("Unexpected error in forward_request", function="forward_request", service_url=service_url, path=path, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    logger.info("Metrics endpoint accessed", function="metrics")
    try:
        result = generate_latest()
        logger.info("Metrics generated successfully", function="metrics")
        return result
    except Exception as e:
        logger.error("Failed to generate metrics", function="metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate metrics")

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(health_router)
app.include_router(models_router, prefix="/api")
app.include_router(api_keys_router, prefix="/api")
app.include_router(systems_router, prefix="/api")
app.include_router(test_execution_router, prefix="/api")
app.include_router(websocket_router)

# Service proxy endpoints
@app.api_route("/api/analytics/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_analytics(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """Proxy requests to analytics service"""
    logger.info("Proxying request to analytics service", function="proxy_analytics", path=path, method=request.method, user_id=current_user["user_id"])
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = str(current_user["user_id"])
    headers["X-User-Role"] = current_user["role"]
    
    # Analytics service doesn't use /api/ prefix, use path as-is
    try:
        result = await forward_request(
            settings.ANALYTICS_SERVICE_URL,
            path,
            request.method,
            content=body,
            headers=headers,
            params=dict(request.query_params)
        )
        logger.info("Analytics service request completed successfully", function="proxy_analytics", path=path, user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Analytics service request failed", function="proxy_analytics", path=path, user_id=current_user["user_id"], error=str(e))
        raise

@app.api_route("/api/compliance/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_compliance(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """Proxy requests to compliance service"""
    logger.info("Proxying request to compliance service", function="proxy_compliance", path=path, method=request.method, user_id=current_user["user_id"])
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = str(current_user["user_id"])
    headers["X-User-Role"] = current_user["role"]

    # Compliance service expects /api/ prefix
    service_path = f"api/{path}" if not path.startswith("api/") else path

    try:
        result = await forward_request(
            settings.COMPLIANCE_SERVICE_URL,
            service_path,
            request.method,
            content=body,
            headers=headers,
            params=dict(request.query_params)
        )
        logger.info("Compliance service request completed successfully", function="proxy_compliance", path=path, user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Compliance service request failed", function="proxy_compliance", path=path, user_id=current_user["user_id"], error=str(e))
        raise

@app.api_route("/api/prompts/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_prompts(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """Proxy requests to prompts service"""
    logger.info("Proxying request to prompts service", function="proxy_prompts", path=path, method=request.method, user_id=current_user["user_id"])
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = str(current_user["user_id"])
    headers["X-User-Role"] = current_user["role"]

    # Prompts service doesn't use /api/ prefix, use path as-is
    try:
        result = await forward_request(
            settings.PROMPTS_SERVICE_URL,
            path,
            request.method,
            content=body,
            headers=headers,
            params=dict(request.query_params)
        )
        logger.info("Prompts service request completed successfully", function="proxy_prompts", path=path, user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Prompts service request failed", function="proxy_prompts", path=path, user_id=current_user["user_id"], error=str(e))
        raise

@app.api_route("/api/documents/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_documents(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """Proxy requests to documents service"""
    logger.info("Proxying request to documents service", function="proxy_documents", path=path, method=request.method, user_id=current_user["user_id"])
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = str(current_user["user_id"])
    headers["X-User-Role"] = current_user["role"]
    
    # Documents service doesn't use /api/ prefix, use path as-is
    try:
        result = await forward_request(
            settings.DOCUMENTS_SERVICE_URL,
            path,
            request.method,
            content=body,
            headers=headers,
            params=dict(request.query_params)
        )
        logger.info("Documents service request completed successfully", function="proxy_documents", path=path, user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Documents service request failed", function="proxy_documents", path=path, user_id=current_user["user_id"], error=str(e))
        raise

@app.api_route("/api/tests/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_tests(
    request: Request,
    path: str,
    current_user: dict = Depends(get_current_user)
):
    """Proxy requests to tests service"""
    logger.info("Proxying request to tests service", function="proxy_tests", path=path, method=request.method, user_id=current_user["user_id"])
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = str(current_user["user_id"])
    headers["X-User-Role"] = current_user["role"]
    
    # Tests service expects /api/ prefix
    service_path = f"api/{path}" if not path.startswith("api/") else path

    try:
        result = await forward_request(
            settings.TESTS_SERVICE_URL,
            service_path,
            request.method,
            content=body,
            headers=headers,
            params=dict(request.query_params)
        )
        logger.info("Tests service request completed successfully", function="proxy_tests", path=path, user_id=current_user["user_id"])
        return result
    except Exception as e:
        logger.error("Tests service request failed", function="proxy_tests", path=path, user_id=current_user["user_id"], error=str(e))
        raise

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect request metrics"""
    start_time = datetime.utcnow()
    logger.debug("Processing HTTP request", function="metrics_middleware", method=request.method, path=request.url.path)
    
    try:
        response = await call_next(request)
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        request_duration.observe(duration)
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        logger.debug("HTTP request completed", function="metrics_middleware", method=request.method, path=request.url.path, status_code=response.status_code, duration=duration)
        return response
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error("HTTP request failed", function="metrics_middleware", method=request.method, path=request.url.path, duration=duration, error=str(e))
        raise

# Additional routers can be added here as needed

if __name__ == "__main__":
    logger.info("Starting application in development mode", function="main", host="0.0.0.0", port=8000)
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )