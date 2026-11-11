"""AI Compliance Testing Service - Main FastAPI application."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from services.shared.database import db_manager
from services.shared.redis_client import redis_client
from services.shared.exceptions import PlatformError
from services.compliance.routers import compliance, evaluators, reports, local_models, plugins, plugin_generator, models, model_configs, systems, system_tests
from services.compliance.services.milvus_service import milvus_service
from services.compliance.framework.core.registry import Registry

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
    logger.info("Starting AI Compliance Service")
    
    try:
        # Initialize database
        await db_manager.initialize()
        logger.info("Database initialized")
        
        # Initialize Redis
        await redis_client.initialize()
        logger.info("Redis initialized")
        
        # Initialize Milvus
        await milvus_service.initialize()
        logger.info("Milvus initialized")
        
        # Initialize framework registry and discover evaluators
        Registry.discover_evaluators()
        evaluators = Registry.list_evaluators()
        logger.info("Framework registry initialized", evaluators_discovered=len(evaluators), evaluators=evaluators)
        
        # Test unified API initialization
        try:
            from shared.unified_api import get_unified_api
            api = get_unified_api()
            providers = api.list_providers()
            logger.info("Unified API initialized", providers=providers)
        except ImportError as e:
            logger.warning(f"Could not initialize unified API: {e}")
            logger.info("Unified API will be available via manual testing")
        
        logger.info("AI Compliance Service started successfully")
        
    except Exception as e:
        logger.error("Failed to start service", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Compliance Service")
    
    await milvus_service.close()
    await redis_client.close()
    await db_manager.close()
    
    logger.info("AI Compliance Service shut down")

# Create FastAPI app
app = FastAPI(
    title="AI Compliance Testing Service",
    description="Service for AI model compliance evaluation and testing with unified model provider support",
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
    try:
        # Test unified API
        unified_api_providers = []
        try:
            from shared.unified_api import get_unified_api
            api = get_unified_api()
            unified_api_providers = api.list_providers()
        except ImportError:
            unified_api_providers = ["unified_api_not_available"]
        
        # Test database
        db_status = "healthy" if db_manager.engine is not None else "not_initialized"
        
        return {
            "status": "healthy",
            "service": "ai-compliance",
            "version": "1.0.0",
            "unified_api_providers": unified_api_providers,
            "database_status": db_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "ai-compliance",
            "version": "1.0.0",
            "error": str(e)
        }

# Include routers
app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
app.include_router(evaluators.router, prefix="/evaluators", tags=["evaluators"])
app.include_router(evaluators.router, prefix="/api/evaluators", tags=["evaluators-api"])  # For gateway proxy
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(local_models.router, prefix="/local-models", tags=["local-models"])
app.include_router(plugins.router, prefix="/plugins", tags=["plugins"])
app.include_router(plugin_generator.router, prefix="/plugin-generator", tags=["plugin-generator"])
app.include_router(models.router, prefix="/api", tags=["models"])  # Legacy unified API models
app.include_router(model_configs.router, prefix="/api", tags=["model-configs"])  # Full CRUD model configurations
app.include_router(systems.router, prefix="/api", tags=["systems"])  # Exposes /api/systems for gateway proxy
app.include_router(system_tests.router, prefix="/api", tags=["system-tests"])  # System compliance testing endpoints

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("PYTHON_ENV") == "development",
        log_config=None  # Use structlog instead
    )