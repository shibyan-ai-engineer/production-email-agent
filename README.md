# Email Assistant

A Python-based intelligent email management agent that automatically triages emails and generates contextual responses using LangGraph and FastAPI.

## Features

- **Smart Email Triage**: Automatically classify emails as ignore, notify, or respond
- **Intelligent Response Generation**: Generate contextual email replies using LLM
- **Human-in-the-Loop (HITL)**: Interactive workflow with user approval and editing
- **Memory & Learning**: Adaptive preferences for triage, responses, and calendar scheduling
- **REST API**: Clean FastAPI interface for integration
- **State Persistence**: Redis-backed workflow state management

## Prerequisites

- Python 3.11+
- Redis Stack server
- OpenAI API key

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/shibyan-ai-engineer/production-email-agent.git
   cd email-assistant-tutorial
   ```

2. **Install uv** (if not already installed)
   ```bash
   pip install uv
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key and other configurations
   ```

5. **Start Redis Stack**
   ```bash
   # Using Docker
   docker run -d -p 6379:6379 redis/redis-stack-server:latest
   
   # Or install locally and run
   redis-stack-server
   ```

## Usage

### Start the API Server

```bash
uv run uvicorn src.email_assistant.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### Process Email (Simple)
```bash
POST /process-email
```

#### Process Email with Human-in-the-Loop
```bash
POST /process-email-hitl
```

### Example Request

```json
{
  "email": {
    "author": "john@example.com",
    "to": "assistant@company.com",
    "subject": "Meeting Request",
    "email_thread": "Hi, could we schedule a meeting for next week to discuss the project?"
  }
}
```

### Example Response

```json
{
  "classification": "respond",
  "response": "Hi John, I'd be happy to schedule a meeting...",
  "metadata": {
    "reasoning": "Email contains a direct meeting request that requires scheduling"
  }
}
```

## Architecture

- **FastAPI**: REST API framework
- **LangGraph**: Agent workflow orchestration
- **LangChain**: LLM integration and tooling
- **Redis**: State persistence and memory
- **Pydantic**: Data validation and serialization

## Development

### Running Tests

```bash
uv run pytest
```

### Project Structure

```
src/email_assistant/
├── main.py              # FastAPI application
├── agent.py             # Core LangGraph agent
├── agent_hitl.py        # Human-in-the-loop agent
├── schemas.py           # Pydantic models
├── prompts.py           # LLM prompts
├── agent_tools.py       # Agent tool definitions
└── tools/               # Tool implementations
    ├── default/         # Default email and calendar tools
    ├── gmail/           # Gmail integration
    └── outlook/         # Outlook integration
```

## License

This project is licensed under the MIT License.
