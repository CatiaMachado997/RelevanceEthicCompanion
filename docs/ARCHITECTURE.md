# Ethic Companion Architecture

## Product Statement
Personal relevance + work orchestration assistant. Guided by user values, protected by ESL (Ethical Safeguard Layer).

## Auth
Supabase Auth (JWT). Backend validates tokens via `backend/utils/supabase_auth.py`.
Dev mode: set `ENVIRONMENT=development` to bypass auth checks (uses `DEV_USER_ID` from config).

## Stack
- **Backend**: FastAPI (Python 3.11+) on port 8000
- **Frontend**: Next.js 15 App Router on port 3000
- **DB M1**: PostgreSQL 15 — structured data (local Docker: `backend-db-1`, prod: Supabase)
- **DB M2**: Weaviate — semantic embeddings (local Docker: `backend-weaviate-1`, optional — app degrades gracefully if unavailable)
- **LLM**: Groq API (Llama 3.3 70B default, configurable)
- **Embeddings**: Gemini API (text-embedding-004)
- **Search**: Tavily API (web search tool)

## Run Locally
```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
docker compose up -d  # start Postgres + Weaviate
python main.py        # http://localhost:8000

# Frontend
cd frontend && npm install
cp .env.local.example .env.local
npm run dev           # http://localhost:3000
```

## Key Backend Services
| File | Responsibility |
|------|----------------|
| `esl/engine.py` | Ethical Safeguard Layer — evaluates all proposed actions |
| `esl/audit.py` | Mandatory audit logging for every ESL decision |
| `services/orchestrator_v2.py` | Main chat orchestration, LangChain tool loop |
| `services/context_manager.py` | M1+M2 retrieval — single entry point for user context |
| `services/data_ingestion.py` | OAuth data sync (Calendar, Gmail, Slack) |
| `services/feedback_processor.py` | Processes thumbs up/down, updates relevance weights |
| `services/langchain_tools.py` | LangChain tools: web_search, query_memory, query_calendar, get_user_goals, create_note |

## API Routes
| Prefix | Purpose |
|--------|---------|
| `/api/chat` | Streaming chat, conversation management, history |
| `/api/feedback` | Thumbs up/down, feedback storage |
| `/api/transparency` | ESL audit log for user-facing decisions |
| `/api/data-sources` | OAuth connect/disconnect/sync for integrations |
| `/api/values` | User values CRUD |
| `/api/goals` | User goals CRUD |
| `/api/profile` | User profile |
| `/api/settings` | User preferences |
| `/health` | Component health status |

## Domain Entities (Canonical)
`UserProfile` · `UserValue` · `Goal` · `Connection` · `SourceItem` · `Document`
`Conversation` · `ConversationTurn` · `Task` · `Insight` · `FeedbackEvent` · `TransparencyLog`

## Two-Memory System
- **M1 (PostgreSQL)**: Structured data — users, user_values, goals, esl_audit_log, conversation_turns, data_sources, feedback_events
- **M2 (Weaviate)**: Semantic embeddings — conversation history, calendar events, documents. pgvector (legacy V1 dependency, not currently used for M2)

## Frontend Structure
```
frontend/app/
  dashboard/
    chat/           # Main chat interface (SSE streaming)
    chat/[id]/      # Conversation by ID
    values/         # Values management
    goals/          # Goals tracking
    transparency/   # ESL decisions viewer
    integrations/   # OAuth connections
    settings/       # User preferences
  login/            # Supabase auth
```

## ESL — Non-Negotiable Rule
Every user-facing action MUST call `esl.evaluate_action()`. Never bypass for efficiency. The ESL is the product's core trust mechanism.
