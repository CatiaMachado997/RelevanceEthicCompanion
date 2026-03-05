# Copilot Instructions for Ethic Companion

## Project Philosophy: "Trust over Engagement"

This is NOT a typical AI application. Every architectural decision stems from ethical principles, not technical convenience.

**Core Mission**: Build AI that assists users without manipulating them. Reject engagement metrics, embrace user well-being.

## Critical Architectural Concept: The Ethical Safeguard Layer (ESL)

The ESL is the **mandatory gateway** for ALL user-facing actions. This is non-negotiable and must never be bypassed.

### ESL Flow (Required Pattern)

```python
# In services/orchestrator.py - ALWAYS follow this pattern:
from esl import EthicalSafeguardLayer, ProposedAction

esl = EthicalSafeguardLayer(context_manager)

# 1. Orchestrator proposes action
proposed_action = ProposedAction(
    action_type="push_notification",
    content_type="work_summary",
    urgency="medium"
)

# 2. ESL MUST evaluate (never skip this)
decision = await esl.evaluate_action(proposed_action, user_id)

# 3. Only proceed if approved
if decision.status == "APPROVED":
    await execute_action(proposed_action)
elif decision.status == "MODIFIED":
    await execute_action(decision.modified_action)
# If VETOED, action is blocked - this is correct behavior
```

**When adding ANY feature that affects users**: notifications, content generation, proactive summaries, reminders → it MUST call `esl.evaluate_action()` first.

## Architecture: The Two-Memory System (M1 + M2)

- **M1 (Postgres)**: Structured data via Supabase
  - `users`, `user_values` (ESL boundaries), `goals`, `esl_audit_log`
  - Access via `services/context_manager.py`
  
- **M2 (pgvector)**: Semantic memory for conversations, notes, context
  - Embeddings stored in Supabase with pgvector extension
  - Query via `context_manager.query_semantic_memory()`

## Directory Structure & Responsibilities

```
backend/
├── esl/              # 🛡️ ESL core - touch carefully, test thoroughly
│   ├── models.py     # ProposedAction, ESLDecision, UserValue
│   ├── engine.py     # EthicalSafeguardLayer.evaluate_action()
│   ├── rules.py      # TimeBasedRules, ManipulationDetector
│   └── audit.py      # Mandatory logging of all decisions
├── services/         # Business logic - must integrate with ESL
│   ├── orchestrator.py    # Decision brain - calls ESL before acting
│   ├── context_manager.py # M1 & M2 interface
│   ├── llm_service.py     # Groq API (Llama 3 for speed)
│   └── relevance_engine.py # Detects when user needs assistance
├── routes/           # FastAPI endpoints
│   └── values.py     # Critical: user boundary management
└── models/           # Pydantic models (separate from ESL models)
```

## Key Conventions

### 1. User Values are Sacred

User-defined boundaries in `user_values` table must be enforced by ESL. Never implement features that circumvent or ignore them.

```python
# Example user_values entries:
{"type": "boundary", "value": "no_work_after_19h", "priority": 1}
{"type": "boundary", "value": "no_politics_topics", "priority": 1}
{"type": "preference", "value": "focus_mode_9am_11am", "priority": 2}
```

### 2. Configuration Management

All config via `config.py` (pydantic-settings):
- Uses `.env` file (never commit `.env`)
- Copy `.env.example` to `.env` for local dev
- Access via `from config import settings`

### 3. Testing ESL is Non-Negotiable

When modifying ESL or Orchestrator:
```bash
pytest tests/test_esl.py -v  # Must pass before committing
```

Test scenarios must include: boundary violations, manipulation detection, context-aware decisions, audit logging.

## Development Workflow

### Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Then configure your API keys
```

### Run Development Server
```bash
python main.py  # Starts on port 8000 with auto-reload
# Or: uvicorn main:app --reload
```

### API Documentation
Visit http://localhost:8000/docs for interactive Swagger UI

### Testing
```bash
pytest                              # Run all tests
pytest --cov=. --cov-report=html   # With coverage
pytest tests/test_esl.py -v        # ESL tests specifically
```

## Integration Points

### Supabase (Database + Auth)
- Connection configured in `config.py` via `SUPABASE_URL` and `SUPABASE_KEY`
- Access via `supabase` client in services
- Auth handled by Supabase Auth (Email + Google OAuth)

### Groq API (LLM - Speed Advantage)
- Used for fast inference (Llama 3)
- Access via `services/llm_service.py`
- Config: `GROQ_API_KEY` in `.env`

### External APIs
- **Tavily**: Web search for context enrichment
- **Google Cloud TTS**: Text-to-speech for multimodal output
- **Google Calendar**: Read-only access for event detection

## Code Style

- **Formatting**: Use `black` (already in requirements.txt)
- **Linting**: `flake8` for code quality
- **Type hints**: Use them consistently (checked by `mypy`)
- **Docstrings**: Required for all public functions/classes

## Anti-Patterns to Avoid

❌ **Never** optimize for engagement metrics (clicks, time-in-app, DAU)  
❌ **Never** bypass ESL evaluation for "efficiency"  
❌ **Never** implement dark patterns (FOMO, urgency manipulation, infinite scroll)  
❌ **Never** ignore user boundaries "just this once"  

✅ **Always** think: "Does this serve the user's stated values?"  
✅ **Always** log ESL decisions for transparency  
✅ **Always** prioritize user control over AI autonomy  

## Frontend Integration (When Ready)

Frontend will be Next.js 14 (App Router) in `/frontend`:
- API calls to FastAPI backend
- Supabase client for direct auth
- Must respect ESL decisions (show transparency)

## Deployment

- **Backend**: Google Cloud Run (see `backend/README.md`)
- **Frontend**: Vercel (when implemented)
- **Database**: Supabase (managed service)

## When Unsure

1. Check `backend/README.md` for detailed architecture
2. Review ESL philosophy in `esl/__init__.py` comments
3. Ask: "Does this align with 'Trust over Engagement'?"
4. When in doubt, add more ESL checks, not fewer

---

**Remember**: We're building an AI companion that respects humans, not exploits them. Every line of code should reflect that mission.
