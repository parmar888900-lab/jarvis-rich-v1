# JARVIS AI Architecture

## Phase 1

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
│  Dashboard │ Agent Chat │ Analytics │ Settings │ Sidebar │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP /api/*
┌──────────────────────────▼──────────────────────────────┐
│                   Backend (FastAPI)                      │
│  routes/  →  services/  →  models/  →  database.py     │
└──────────────┬───────────────────────────┬────────────────┘
               │                           │
        ┌──────▼──────┐             ┌──────▼──────┐
        │   SQLite    │             │   Ollama    │
        │  (local)    │             │  (local)    │
        └─────────────┘             └─────────────┘
```

## Data Flow (Chat)

1. User sends message from Agent page
2. Frontend POSTs to `/api/agents/chat`
3. Backend loads agent config from SQLite
4. Backend sends messages to Ollama `/api/chat`
5. Ollama runs local model inference
6. Response returned to frontend

## Future Phases

- **agents/**: Multi-agent orchestration and tool definitions
- **memory/**: Persistent long-term memory across sessions
- **configs/**: Environment and feature flags
