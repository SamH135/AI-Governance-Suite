FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from services directory
COPY services/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt

# Copy entire services directory
COPY services/ services/
COPY shared/ shared/

# Create logs directory
RUN mkdir -p logs

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "services.tests.main:app", "--host", "0.0.0.0", "--port", "8000"]