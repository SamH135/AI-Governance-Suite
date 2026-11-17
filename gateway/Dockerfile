FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY gateway/requirements.txt .
RUN pip install --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt

# Copy application code + the shared libs gateway imports (services.shared.*)
COPY gateway/ .
COPY shared/ shared/
COPY services/__init__.py services/__init__.py
COPY services/shared services/shared

# Create non-root user
RUN useradd --create-home --shell /bin/bash gateway
RUN chown -R gateway:gateway /app
USER gateway

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application (dev hot-reload lives in docker-compose.dev.yml)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
