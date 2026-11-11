"""Analytics Service - Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from ..shared.database import db_manager
from ..shared.redis_client import redis_client
from ..shared.exceptions import PlatformError
from .routers import analytics, reports, dashboards
from .services.analytics_service import analytics_service

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Analytics Service")
    
    try:
        # Initialize database
        await db_manager.initialize()
        logger.info("Database initialized")
        
        # Initialize Redis
        await redis_client.initialize()
        logger.info("Redis initialized")
        
        # Initialize analytics service
        await analytics_service.initialize()
        logger.info("Analytics service initialized")
        
        logger.info("Analytics Service started successfully")
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Analytics Service")
    
    await analytics_service.close()
    await redis_client.close()
    await db_manager.close()
    
    logger.info("Analytics Service shut down")

# Create FastAPI app
app = FastAPI(
    title="AI Compliance Analytics Service",
    description="Advanced analytics and reporting for AI compliance platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler for platform errors
@app.exception_handler(PlatformError)
async def platform_error_handler(request: Request, exc: PlatformError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

# General exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "analytics",
        "version": "1.0.0"
    }

# Include routers
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("PYTHON_ENV") == "development",
        log_config=None  # Use structlog instead
    )