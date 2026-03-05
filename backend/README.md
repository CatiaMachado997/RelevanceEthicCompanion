# Ethic Companion Backend

**Version 1.0 - "The Official Start"**

## 🎯 Our Purpose

> *"AI as our Companion in Decision-Making"*

Ethic Companion is built on the premise that **trust is more valuable than engagement**. This backend implements an **Ethical Safeguard Layer (ESL)** as a core architectural component—not an afterthought, but the foundation of every user-facing action.

### Core Values

1. **User Well-being is Primary Metric** - We explicitly reject misaligned proxy metrics like "time in-app" or "engagement maximization"
2. **User Control is Crucial** - Users define explicit boundaries that the system MUST enforce
3. **Commitment to Non-Manipulation** - Active detection and blocking of dark patterns, FOMO, and addictive loops
4. **Continuous Research and Alignment** - Ongoing dedication to ethical AI research and safety

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ API Requests
┌──────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Orchestrator (Brain)                      │ │
│  │  "User has meeting in 15min, should I generate        │ │
│  │   a summary?"                                          │ │
│  └────────────┬──────────────────┬────────────────────────┘ │
│               │                  │                           │
│               │    ┌─────────────▼───────────────┐          │
│               │    │ ETHICAL SAFEGUARD LAYER     │          │
│               │    │ ⚖️  (THE MANDATORY GATEWAY) │          │
│               │    │                             │          │
│               │    │ • Checks User Boundaries    │          │
│               │    │ • Detects Manipulation      │          │
│               │    │ • Enforces Non-Engagement   │          │
│               │    │ • Logs Every Decision       │          │
│               │    │                             │          │
│               │    │ Returns: APPROVED/VETOED/   │          │
│               │    │          MODIFIED           │          │
│               │    └─────────────┬───────────────┘          │
│               │                  │ Decision                 │
│  ┌────────────▼──────────────────▼────────────────────────┐ │
│  │         Context Manager + Services                     │ │
│  │  • User Values Store (M1: Postgres)                   │ │
│  │  • Semantic Memory (M2: pgvector)                     │ │
│  │  • LLM Service (Groq API - Llama 3)                   │ │
│  │  • Relevance Engine                                   │ │
│  │  • Data Ingest (Calendar, etc.)                       │ │
│  └───────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Local PostgreSQL (Docker)                       │
│  • M1: Postgres (users, values, goals, esl_audit_log)      │
│  • M2: pgvector (semantic embeddings)                       │
└─────────────────────────────────────────────────────────────┘
```

## 🛡️ The Ethical Safeguard Layer (ESL)

**The ESL is not optional. It is mandatory for every user-facing action.**

### How It Works

1. **Orchestrator proposes an action**: 
   ```python
   proposed_action = ProposedAction(
       action_type="push_notification",
       content_type="work_summary",
       urgency="medium"
   )
   ```

2. **ESL evaluates against user boundaries**:
   - Queries Context Manager for user values
   - Checks time-based boundaries (e.g., "no_work_after_19h")
   - Detects manipulation patterns (FOMO, urgency abuse)
   - Verifies intent (assistance vs. engagement)

3. **ESL returns decision**:
   ```python
   ESLDecision(
       status="VETOED",
       reason="Violates user boundary: no_work_after_19h",
       modified_action="queue_for_morning_briefing"
   )
   ```

4. **Every decision is logged** for ethical research and transparency

### ESL Components

- **`esl/models.py`** - Data models (ProposedAction, ESLDecision, UserValue)
- **`esl/engine.py`** - Core EthicalSafeguardLayer class with `evaluate_action()`
- **`esl/rules.py`** - Rule system (TimeBasedRules, ManipulationDetector)
- **`esl/audit.py`** - Comprehensive audit logging

## 📁 Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration & environment variables
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── docker-compose.yml      # Docker Compose for local database
│
├── db/
│   └── init.sql            # Database schema initialization
│
├── esl/                   # 🛡️ ETHICAL SAFEGUARD LAYER
│   ├── __init__.py
│   ├── models.py          # ESL data models
│   ├── engine.py          # Core ESL evaluation logic
│   ├── rules.py           # Rule checking system
│   └── audit.py           # Audit & logging
│
├── models/                # Data models (Pydantic)
│   ├── __init__.py
│   ├── user.py            # User models
│   └── context.py         # Context, Goals, Events
│
├── services/              # Business logic & integrations
│   ├── __init__.py
│   ├── context_manager.py # M1 & M2 management
│   ├── orchestrator.py    # Decision-making brain
│   ├── llm_service.py     # Groq API integration
│   ├── relevance_engine.py # Relevance detection
│   ├── data_ingest.py     # Calendar & data connectors
│   └── tts_service.py     # Google Cloud TTS
│
├── routes/                # API endpoints
│   ├── __init__.py
│   ├── values.py          # User values CRUD
│   ├── actions.py         # Action endpoints
│   ├── integrations.py    # OAuth callbacks
│   └── audio.py           # TTS generation
│
├── utils/                 # Utilities
│   └── __init__.py
│
└── tests/                 # Test suite
    ├── __init__.py
    └── test_esl.py        # ESL integration tests
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Groq API key (free developer tier)
- Tavily API key (free tier)
- Google Cloud account (for TTS - generous free tier)

### Installation & Setup

1. **Clone the repository**
   ```bash
   cd backend
   ```

2. **Start the local database**
   ```bash
   docker-compose up -d
   ```
   This will start a PostgreSQL database in a Docker container.

3. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

6. **Run development server**
   ```bash
   python main.py
   # Or use uvicorn directly:
   uvicorn main:app --reload
   ```

7. **Access the API**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run ESL tests specifically
pytest tests/test_esl.py -v
```

## 📊 Tech Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Framework** | FastAPI | Modern, fast, async Python framework |
| **Database** | PostgreSQL (Docker) | Local, portable, and powerful database |
| **LLM** | Groq API (Llama 3) | Blazing fast inference (our speed advantage) |
| **Search** | Tavily | AI-optimized search, robust free tier |
| **TTS** | Google Cloud TTS | Natural voices, generous free tier |
| **Hosting** | Google Cloud Run | Generous free tier, scales to zero |

## 🔐 Environment Variables

See `.env.example` for all required variables:

- **PostgreSQL**: `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- **APIs**: `GROQ_API_KEY`, `TAVILY_API_KEY`
- **Google Cloud**: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`

## 📈 Deployment (Google Cloud Run)

```bash
# Build Docker image
docker build -t ethic-companion-backend .

# Deploy to Cloud Run
gcloud run deploy ethic-companion-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## 🎯 MVP Scope (v1.0)

**IN SCOPE:**
- ✅ Ethical Safeguard Layer (core)
- ✅ User values/boundaries management
- ✅ Google Calendar integration (read-only)
- ✅ Relevance detection for upcoming meetings
- ✅ Context summarization (Groq + Tavily)
- ✅ Text-to-Speech (Google Cloud TTS)
- ✅ ESL audit logging & transparency

**OUT OF SCOPE (v1.1+):**
- ❌ Image/Video generation
- ❌ Email integration
- ❌ Write actions (calendar modifications)
- ❌ Mobile apps

## 🤝 Contributing

This project is built on ethical principles. When contributing:

1. The ESL must never be bypassable
2. User boundaries are sacred
3. Optimize for assistance, never engagement
4. Log all decisions for transparency
5. Think: "Does this serve the user's values?"

## 📄 License

TBD

## 👩‍💻 Founder

**Cátia Machado**  
November 4, 2025

---

*"Trust over Engagement. Always."*
