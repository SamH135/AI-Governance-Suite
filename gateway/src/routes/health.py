"""Health check routes for the gateway service."""

from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import httpx

# Import custom logger
from ..logger_util import logger

from ..shared.database import get_db_pool
from ..shared.cache import get_redis_client
from ..shared.config import get_settings
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check():
    """Basic health check"""
    logger.debug("Basic health check requested", function="health_check")
    
    try:
        result = {
            "status": "healthy",
            "service": "api-gateway",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.debug("Basic health check completed successfully", function="health_check")
        return result
    except Exception as e:
        logger.error("Basic health check failed", function="health_check", error=str(e))
        raise HTTPException(status_code=500, detail="Health check failed")

@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with dependencies"""
    logger.info("Detailed health check requested", function="detailed_health_check")
    
    settings = get_settings()
    
    health = {
        "status": "healthy",
        "service": "api-gateway",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {"status": "unknown", "message": ""},
            "redis": {"status": "unknown", "message": ""},
            "services": {
                "compliance": {"status": "unknown", "url": settings.COMPLIANCE_SERVICE_URL},
                "prompts": {"status": "unknown", "url": settings.PROMPTS_SERVICE_URL},
                "documents": {"status": "unknown", "url": settings.DOCUMENTS_SERVICE_URL},
                "tests": {"status": "unknown", "url": settings.TESTS_SERVICE_URL}
            }
        }
    }
    
    # Check database
    logger.debug("Checking database connection", function="detailed_health_check")
    try:
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health["checks"]["database"] = {"status": "healthy", "message": "Database connection successful"}
        logger.debug("Database health check passed", function="detailed_health_check")
    except Exception as e:
        logger.warn("Database health check failed", function="detailed_health_check", error=str(e))
        health["checks"]["database"] = {"status": "unhealthy", "message": f"Database error: {str(e)}"}
        health["status"] = "degraded"
    
    # Check Redis
    logger.debug("Checking Redis connection", function="detailed_health_check")
    try:
        redis_client = get_redis_client()
        await redis_client.set("health_check", "ok", ex=10)
        result = await redis_client.get("health_check")
        if result == b"ok":
            health["checks"]["redis"] = {"status": "healthy", "message": "Redis connection successful"}
            logger.debug("Redis health check passed", function="detailed_health_check")
        else:
            logger.warn("Redis read/write test failed", function="detailed_health_check")
            health["checks"]["redis"] = {"status": "unhealthy", "message": "Redis read/write test failed"}
            health["status"] = "degraded"
    except Exception as e:
        logger.warn("Redis health check failed", function="detailed_health_check", error=str(e))
        health["checks"]["redis"] = {"status": "unhealthy", "message": f"Redis error: {str(e)}"}
        health["status"] = "degraded"
    
    # Check services
    logger.debug("Checking microservices health", function="detailed_health_check")
    services = [
        ("compliance", settings.COMPLIANCE_SERVICE_URL),
        ("prompts", settings.PROMPTS_SERVICE_URL),
        ("documents", settings.DOCUMENTS_SERVICE_URL),
        ("tests", settings.TESTS_SERVICE_URL)
    ]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_url in services:
            logger.debug("Checking service health", function="detailed_health_check", service=service_name, url=service_url)
            try:
                response = await client.get(f"{service_url}/health")
                if response.status_code == 200:
                    health["checks"]["services"][service_name]["status"] = "healthy"
                    logger.debug("Service health check passed", function="detailed_health_check", service=service_name)
                else:
                    logger.warn("Service health check failed", function="detailed_health_check", service=service_name, status_code=response.status_code)
                    health["checks"]["services"][service_name]["status"] = "unhealthy"
                    health["status"] = "degraded"
            except Exception as e:
                logger.warn("Service health check exception", function="detailed_health_check", service=service_name, error=str(e))
                health["checks"]["services"][service_name]["status"] = "unhealthy"
                health["status"] = "degraded"
    
    status_code = 200 if health["status"] == "healthy" else 503
    logger.info("Detailed health check completed", function="detailed_health_check", overall_status=health["status"], status_code=status_code)
    return JSONResponse(content=health, status_code=status_code)

@router.get("/ready")
async def readiness_check():
    """Readiness check (for Kubernetes)"""
    logger.debug("Readiness check requested", function="readiness_check")
    
    try:
        # Check if essential services are ready
        logger.debug("Checking database readiness", function="readiness_check")
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        result = {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.debug("Readiness check passed", function="readiness_check")
        return result
    except Exception as e:
        logger.error("Readiness check failed", function="readiness_check", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not ready",
                "error": "Essential services not available",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.get("/live")
async def liveness_check():
    """Liveness check (for Kubernetes)"""
    logger.debug("Liveness check requested", function="liveness_check")
    
    try:
        result = {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.debug("Liveness check completed", function="liveness_check")
        return result
    except Exception as e:
        logger.error("Liveness check failed", function="liveness_check", error=str(e))
        raise HTTPException(status_code=500, detail="Liveness check failed")