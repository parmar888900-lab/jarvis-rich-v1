# JARVIS AI

**JARVIS AI** is a local-first AI assistant built entirely with open-source software. No paid APIs, no cloud dependencies — everything runs on your machine.

## Phase 1 Overview

This is the foundation release. It includes:

- **FastAPI backend** with SQLite database
- **Next.js + TypeScript frontend** with dashboard, agent chat, analytics, and settings
- **Ollama integration** for running local LLMs (Llama, Mistral, etc.)
- Project scaffolding for agents, memory, configs, scripts, and tests

## Tech Stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Backend  | Python, FastAPI, SQLAlchemy, SQLite |
| Frontend | Next.js 15, React 19, TypeScript    |
| LLM      | [Ollama](https://ollama.com) (local) |
| Database | SQLite (local file)                 |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Ollama** — [Download](https://ollama.com/download)

## Project Structure

```
jarvis.ai/
├── backend/           # FastAPI application
│   ├── app.py         # Entry point
│   ├── config.py      # Settings
│   ├── database.py    # SQLAlchemy setup
│   ├── routes/        # API endpoints
│   ├── services/      # Business logic
│   └── models/        # ORM + Pydantic schemas
├── frontend/          # Next.js application
│   ├── app/           # Pages (dashboard, agent, analytics, settings)
│   └── components/    # Sidebar and shared UI
├── agents/            # Agent definitions (Phase 2+)
├── memory/            # Long-term memory store
├── database/          # SQLite database files
├── configs/           # Environment configuration
├── scripts/           # Setup and utility scripts
├── logs/              # Application logs
├── tests/             # Test suite
└── docs/              # Documentation
```

## Setup

### 1. Clone and enter the project

```bash
cd jarvis.ai
```

### 2. Create Python virtual environment

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Install Ollama and pull a model

```bash
# Install Ollama from https://ollama.com, then:
ollama pull llama3.2
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure (optional)

Copy the example config:

```bash
cp configs/.env.example configs/.env
```

Edit `configs/.env` to change Ollama URL, model, or debug settings.

## Running

### Start the backend

```bash
cd backend
# With venv activated:
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Start the frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## API Endpoints

| Method | Path                  | Description              |
|--------|-----------------------|--------------------------|
| GET    | `/api/health`         | System health check      |
| GET    | `/api/agents/`        | List all agents          |
| POST   | `/api/agents/`        | Create an agent          |
| POST   | `/api/agents/chat`    | Chat with an agent       |
| GET    | `/api/analytics/summary` | Usage statistics     |
| GET    | `/api/settings/`      | Get settings             |
| PATCH  | `/api/settings/`      | Update settings          |

## Local-Only Policy

- No OpenAI, Anthropic, or other paid API keys
- All inference via Ollama on localhost
- SQLite database stored in `database/`
- Memory and logs stay on disk locally

## Roadmap

- **Phase 1** (current): Project scaffold, basic chat, dashboard
- **Phase 2**: Multi-agent orchestration, memory persistence
- **Phase 3**: Voice interface, tool use, plugins
- **Phase 4**: Autonomous task execution

## License

MIT — use freely, modify openly.
