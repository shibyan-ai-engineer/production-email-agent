# Single-stage Dockerfile for FastAPI Email Assistant - Optimized for Render
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (minimal set)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install UV package manager
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files first (for better Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application source code
COPY src/ ./src/

# Expose port (Render will set PORT environment variable)
EXPOSE 8000

# Health check with improved timeout and start period
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start command with proper port handling
CMD ["/bin/sh", "-c", "uv run uvicorn src.email_assistant.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
