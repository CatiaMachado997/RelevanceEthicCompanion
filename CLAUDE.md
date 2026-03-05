# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Philosophy: "Trust over Engagement"

Ethic Companion is an AI assistant that helps users make decisions while respecting their boundaries. The **Ethical Safeguard Layer (ESL)** is a mandatory gateway for ALL user-facing actions—this is non-negotiable and must never be bypassed.

## Build & Run Commands

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure API keys
docker compose up -d  # Start PostgreSQL & Weaviate
python main.py        # Run on localhost:8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev           # Run on localhost:3000
```

### Testing

```bash
# Backend
pytest                              # All tests
pytest tests/test_esl.py -v        # ESL tests specifically
pytest --cov=. --cov-report=html   # With coverage

# Frontend
npm run test
```

### Code Quality (Backend)

```bash
black .     # Format
flake8 .    # Lint
mypy .      # Type check
```

## Architecture

### Tech Stack

- **Backend**: FastAPI (Python) + Groq API (Llama 3) + Tavily Search + Google Cloud TTS
- **Frontend**: Next.js (App Router) + TypeScript + Tailwind CSS + Radix UI
- **Database**: PostgreSQL with pgvector (local via Docker, production on Supabase)
- **Deployment**: Google Cloud Run (backend), Vercel (frontend)

### The Ethical Safeguard Layer (ESL)

The ESL is the core architectural component. Every user-facing action must pass through it:

```python
from esl import EthicalSafeguardLayer, ProposedAction

esl = EthicalSafeguardLayer(context_manager)

proposed = ProposedAction(
    action_type="push_notification",
    content_type="work_summary",
    urgency="medium"
)

decision = await esl.evaluate_action(proposed, user_id)

if decision.status == "APPROVED":
    await execute_action(proposed)
elif decision.status == "MODIFIED":
    await execute_action(decision.modified_action)
# If VETOED: do nothing (correct behavior)
```

### Two-Memory System

- **M1 (PostgreSQL)**: Structured data—users, user_values, goals, esl_audit_log
- **M2 (pgvector)**: Semantic embeddings for conversation history and context

### Key Backend Components

- `esl/engine.py` - Core ESL evaluation logic
- `esl/models.py` - ProposedAction, ESLDecision, UserValue models
- `esl/rules.py` - TimeBasedRules, ManipulationDetector, EngagementDetector
- `esl/audit.py` - Mandatory audit logging
- `services/orchestrator.py` - Decision-making brain (calls ESL before all actions)
- `services/context_manager.py` - M1 & M2 interface

## Critical Development Rules

1. **ESL is mandatory**: Every user-facing action MUST call `esl.evaluate_action()`. Never bypass for efficiency.

2. **User values are sacred**: Boundaries in `user_values` table must be enforced without exception.

3. **Test ESL before committing**: Run `pytest tests/test_esl.py -v` when modifying ESL or Orchestrator.

4. **Anti-patterns to avoid**:
   - Never optimize for engagement metrics (clicks, time-in-app, DAU)
   - Never implement dark patterns (FOMO, urgency manipulation, infinite scroll)
   - Never ignore user boundaries "just this once"

## API Documentation

- Interactive Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health
