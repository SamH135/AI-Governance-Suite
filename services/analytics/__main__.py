"""Entry point for running the analytics service as a module."""

import os
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "services.analytics.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("PYTHON_ENV") == "development",
        log_config=None  # Use structlog instead
    )