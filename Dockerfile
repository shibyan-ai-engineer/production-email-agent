# Optimized Dockerfile for FastAPI Email Assistant
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install UV package manager
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files and source code
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8000

# Start application
CMD ["sh", "-c", "uv run uvicorn src.email_assistant.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
