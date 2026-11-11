#!/usr/bin/env python3
"""
Development startup script for the AI Compliance Gateway
"""

import uvicorn
import os

# Import logging
from src.logger_util import logger

if __name__ == "__main__":
    logger.info("Starting AI Compliance Gateway in development mode", function="main")
    
    # Set development environment
    logger.info("Setting development environment", function="main", env="development")
    os.environ.setdefault("PYTHON_ENV", "development")
    
    # Run the application
    logger.info("Starting uvicorn server", function="main", host="0.0.0.0", port=8000, reload=True)
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error("Failed to start uvicorn server", function="main", error=str(e))
        raise
    finally:
        logger.info("Uvicorn server stopped", function="main")