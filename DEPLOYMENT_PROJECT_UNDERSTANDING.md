# Email Assistant Project - Deployment Guide

## Project Overview

The Email Assistant is a Python-based intelligent email management system that uses LangGraph and FastAPI to automatically triage emails and generate contextual responses. The application features Human-in-the-Loop (HITL) workflows with persistent memory backed by Redis Stack.

### Core Technologies
- **Framework**: FastAPI (REST API)
- **AI/ML**: LangGraph (workflow orchestration), LangChain (LLM integration), OpenAI GPT-4
- **Database**: Redis Stack (state persistence & memory)
- **Package Manager**: UV (Python package management)
- **Language**: Python 3.11+

## Architecture Components

### 1. Application Structure
```
src/email_assistant/
├── main.py              # FastAPI application entry point
├── agent.py             # Core LangGraph agent (non-HITL)
├── agent_hitl.py        # Human-in-the-loop agent with memory
├── schemas.py           # Pydantic models and data validation
├── prompts.py           # LLM system prompts and templates
├── agent_tools.py       # Agent tool definitions
├── utils.py             # Utility functions
└── tools/               # Tool implementations
    ├── default/         # Default email and calendar tools
    ├── gmail/           # Gmail integration (empty - future)
    └── outlook/         # Outlook integration (empty - future)
```

### 2. Runtime Dependencies

#### Critical Services
- **Redis Stack**: Required for workflow state persistence and memory storage
  - Port: 6379 (default)
  - Connection: `redis://localhost:6379`
  - Used by: LangGraph checkpointer and memory store

#### External APIs
- **OpenAI API**: Required for LLM functionality
  - Environment variable: `OPENAI_API_KEY`
  - Model: GPT-4.1 (temperature: 0.0)

#### Optional Services
- **LangSmith**: Tracing and monitoring (optional)
  - Environment variables: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`

## Application Configuration

### 1. Environment Variables
```bash
# Required
OPENAI_API_KEY=sk-proj-xxx...

# Optional (LangSmith tracing)
LANGSMITH_API_KEY=lsv2_pt_xxx...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_PROJECT="LangGraph-Production-Agent"
```

### 2. Network Configuration
- **Application Port**: 8000 (configurable in main.py)
- **Host**: 0.0.0.0 (accepts connections from all interfaces)
- **Redis Port**: 6379 (hardcoded in agent_hitl.py)

### 3. Python Dependencies (from pyproject.toml)
```toml
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "langchain>=0.3.9",
    "langchain-core>=0.3.59",
    "langchain-openai",
    "langgraph>=0.4.2",
    "langsmith>=0.3.4",
    "python-dotenv",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "ipython>=9.4.0",
    "pytest>=8.4.1",
    "langgraph-checkpoint-redis>=0.0.8",
]
```

## API Endpoints

### Core Endpoints
1. **POST /process-email** - Simple email processing (non-HITL)
2. **POST /process-email-hitl** - Human-in-the-loop email processing
3. **GET /process-email-hitl/{thread_id}** - Get HITL thread state
4. **GET /health** - Health check endpoint

### Request/Response Flow
- Accepts email input with author, subject, thread content
- Returns classification (ignore/notify/respond) and generated responses
- Supports workflow interruption for human review and approval
- Maintains persistent memory across sessions

## Memory System

### Memory Namespaces
The application uses Redis to store three types of user preferences:

1. **Triage Preferences**: `("email_assistant", "triage_preferences")`
   - Email classification decisions
   - Which emails to ignore/notify/respond

2. **Response Preferences**: `("email_assistant", "response_preferences")`
   - Email writing style and tone
   - Response patterns and templates

3. **Calendar Preferences**: `("email_assistant", "cal_preferences")`
   - Meeting scheduling preferences
   - Calendar management patterns

## Deployment Requirements

### 1. Container Requirements
```dockerfile
# Base requirements for containerization:
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# UV package manager
RUN pip install uv

# Application dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Application code
COPY src/ ./src/
```

### 2. Redis Stack Deployment
```yaml
# Docker Compose or separate container
services:
  redis:
    image: redis/redis-stack-server:latest
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
```

### 3. Application Startup
```bash
# Production startup command
uvicorn src.email_assistant.main:app --host 0.0.0.0 --port 8000

# Development with reload
uvicorn src.email_assistant.main:app --host 0.0.0.0 --port 8000 --reload
```

## Platform-Specific Considerations

### Render Platform Deployment
1. **Runtime**: Python 3.11+
2. **Build Command**: `uv sync && uv pip compile pyproject.toml`
3. **Start Command**: `uvicorn src.email_assistant.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**: Configure OpenAI API key and optional LangSmith settings
5. **Redis**: Use Render's Redis add-on or external Redis Stack service

### Docker Deployment
1. **Multi-stage build**: Optimize for production
2. **Non-root user**: Security best practices
3. **Health checks**: Use `/health` endpoint
4. **Volume mounts**: For persistent Redis data

### GitHub Actions CI/CD
1. **Testing**: Run pytest suite before deployment
2. **Environment management**: Secure secret handling for API keys
3. **Multi-environment**: Support staging and production deployments
4. **Dependency caching**: Cache UV dependencies

## Monitoring and Health Checks

### Application Health
- **Endpoint**: `GET /health`
- **Response**: `{"status": "healthy", "service": "email-assistant"}`

### Redis Health
- Check Redis connectivity before application startup
- Monitor Redis memory usage and persistence

### External Dependencies
- Monitor OpenAI API rate limits and usage
- Track LangSmith tracing if enabled

## Security Considerations

### API Keys
- Store sensitive credentials as environment variables
- Never commit API keys to version control
- Use secret management services in production

### Network Security
- Application runs on 0.0.0.0 (all interfaces) - configure firewall/load balancer appropriately
- Redis should not be exposed publicly without authentication

### Data Privacy
- Email content processed through OpenAI API
- Memory data persisted in Redis
- Consider data retention policies

## Testing and Quality Assurance

### Test Suite
- Located in `tests/` directory
- Uses pytest with LangSmith integration
- Tests tool calling verification
- Parametrized tests for different email scenarios

### Test Commands
```bash
# Run all tests
uv run pytest

# Run with LangSmith integration
uv run pytest -m langsmith
```

## Troubleshooting

### Common Issues
1. **Redis Connection Failed**: Ensure Redis Stack is running on port 6379
2. **OpenAI API Errors**: Check API key validity and rate limits
3. **Memory Persistence Issues**: Verify Redis data persistence configuration
4. **Port Conflicts**: Default port 8000 may conflict with other services

### Debug Mode
- Enable FastAPI reload mode for development
- Check LangSmith tracing for workflow debugging
- Monitor Redis keys for memory state inspection

## Scalability Considerations

### Horizontal Scaling
- Application is stateless (state stored in Redis)
- Multiple instances can share same Redis backend
- Load balancer configuration needed

### Resource Requirements
- **CPU**: Moderate (LLM API calls are external)
- **Memory**: Low to moderate (depends on workflow complexity)
- **Storage**: Minimal (Redis handles persistence)
- **Network**: High for OpenAI API communication

---

This documentation provides comprehensive deployment context for setting up the Email Assistant project using Docker, GitHub Actions, and cloud platforms like Render.
