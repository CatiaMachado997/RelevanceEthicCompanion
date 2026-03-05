# Quick Start Guide - V2 MVP

## Prerequisites

1. **Docker Desktop** must be running
2. **Python 3.9+** installed
3. **PostgreSQL** and **Weaviate** via Docker

---

## Step 1: Start Infrastructure

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend

# Start PostgreSQL + Weaviate
docker-compose up -d

# Verify services are running
docker-compose ps

# Expected output:
# backend-db-1        running
# backend-weaviate-1  running
```

---

## Step 2: Set Up Database

```bash
# Initialize PostgreSQL schema (creates V2 tables)
psql -h localhost -U postgres -d ethic-companion -f database/schema_local.sql

# Password: postgres

# Expected output:
# ✅ Database schema initialized successfully!
# ✅ V2 tables created: data_sources, relevance_feedback, context_snapshots
```

---

## Step 3: Configure Environment Variables

Edit `backend/.env` and add:

```bash
# Gemini API (for embeddings) - REQUIRED FOR V2
GEMINI_API_KEY=your_gemini_api_key_here

# Get your key from: https://makersuite.google.com/app/apikey
```

**Note**: Firebase and Google Calendar OAuth can be added later. For now, the system will use the existing JWT auth and mock data.

---

## Step 4: Install Python Dependencies

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend

# Activate virtual environment
source venv/bin/activate

# Install V2 dependencies (already in requirements.txt)
pip install -r requirements.txt

# Verify Weaviate client installed
python -c "import weaviate; print('✅ Weaviate client installed')"

# Verify Gemini installed
python -c "import google.generativeai; print('✅ Gemini installed')"
```

---

## Step 5: Initialize Weaviate Schemas

```bash
# Run Python script to create Weaviate collections
python -c "
from utils.weaviate_client import get_weaviate_client
client = get_weaviate_client()
print('✅ Weaviate schemas initialized')
"

# Expected output:
# ✅ Connected to Weaviate at http://localhost:8080
# ✅ Created collection: ConversationMemory
# ✅ Created collection: ContextualEvents
# ✅ Created collection: UserGoals
# ✅ All Weaviate schemas initialized
```

---

## Step 6: Run Backend Server

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend

# Start FastAPI server
python main.py

# Expected output:
# INFO:     Started server process
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 7: Test V2 Endpoints

### Test 1: Health Check
```bash
curl http://localhost:8000/health

# Expected:
# {"status":"healthy"}
```

### Test 2: Test Embedding Service
```bash
# Create a test script
cat > test_embedding.py << 'EOF'
import asyncio
from services.embedding_service import EmbeddingService
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    service = EmbeddingService(os.getenv("GEMINI_API_KEY"))
    embedding = await service.generate_embedding("Test sentence")
    print(f"✅ Generated embedding with {len(embedding)} dimensions")

asyncio.run(test())
EOF

python test_embedding.py

# Expected:
# ✅ Generated embedding with 768 dimensions
```

### Test 3: Test Relevance Scoring
```bash
# Create a test script
cat > test_scoring.py << 'EOF'
import asyncio
from services.relevance_scoring import RelevanceScoringEngine
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from models.relevance import CandidateItem, RelevanceContext, ItemType
from datetime import datetime

async def test():
    # Initialize components
    context_mgr = ContextManager()
    esl = EthicalSafeguardLayer(context_mgr)
    scoring = RelevanceScoringEngine(esl)

    # Create test candidates
    candidates = [
        CandidateItem(
            id="1",
            type=ItemType.SEARCH_RESULT,
            content="Python tutorial for beginners",
            title="Learn Python",
            source="test",
            timestamp=datetime.utcnow()
        ),
        CandidateItem(
            id="2",
            type=ItemType.SEARCH_RESULT,
            content="Cat videos compilation",
            title="Funny Cats",
            source="test",
            timestamp=datetime.utcnow()
        )
    ]

    # Create context with query
    context = RelevanceContext(
        user_id="00000000-0000-0000-0000-000000000000",
        query="learn programming",
        active_goals=["Learn Python"],
        upcoming_events=[],
        recent_topics=[],
        focus_mode=False,
        user_values=[]
    )

    # Score candidates
    scored = await scoring.score_candidates(
        user_id="00000000-0000-0000-0000-000000000000",
        candidates=candidates,
        context=context
    )

    print("\n✅ Relevance Scoring Test Results:")
    for item in scored:
        print(f"\nItem: {item.item.title}")
        print(f"Score: {item.relevance_score:.2f}/100")
        print(f"Explanation: {item.explanation}")
        print(f"Breakdown: {item.score_breakdown}")

asyncio.run(test())
EOF

python test_scoring.py

# Expected: Python tutorial ranked higher than cat videos
```

---

## Troubleshooting

### Issue: "Cannot connect to Docker daemon"
**Solution**: Start Docker Desktop application

### Issue: "Connection refused" when connecting to PostgreSQL
**Solution**:
```bash
docker-compose down
docker-compose up -d
```

### Issue: "Weaviate connection failed"
**Solution**:
```bash
# Check if Weaviate is running
curl http://localhost:8080/v1/meta

# If not, restart:
docker-compose restart weaviate
```

### Issue: "GEMINI_API_KEY not found"
**Solution**:
1. Get API key from https://makersuite.google.com/app/apikey
2. Add to `backend/.env`:
   ```bash
   GEMINI_API_KEY=your_key_here
   ```

### Issue: "ModuleNotFoundError"
**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Verification Checklist

- [ ] Docker containers running (db + weaviate)
- [ ] PostgreSQL schema initialized with V2 tables
- [ ] Weaviate collections created
- [ ] GEMINI_API_KEY configured in .env
- [ ] Backend server starts without errors
- [ ] Health check returns 200
- [ ] Embedding service test passes
- [ ] Relevance scoring test passes

---

## What's Working (V2)

✅ **Database**: PostgreSQL with V2 tables
✅ **Vector DB**: Weaviate with 3 collections
✅ **Embeddings**: Gemini embedding-001
✅ **Relevance Scoring**: Custom multi-factor algorithm
✅ **ESL Integration**: Content safety checks
✅ **Models**: All V2 Pydantic models

---

## What's NOT Working Yet (TODO)

❌ **Context Manager**: Still using in-memory (needs refactor)
❌ **Google Calendar**: No OAuth integration yet
❌ **LangChain Orchestrator**: Not refactored yet
❌ **Firebase Auth**: Still using JWT
❌ **Frontend**: Not updated for V2 yet

---

## Next Development Steps

1. **Refactor context_manager.py**:
   - Replace in-memory with PostgreSQL + Weaviate queries
   - This is the critical blocker

2. **Test end-to-end flow**:
   - User query → context retrieval → relevance scoring → response

3. **Add Google Calendar integration**:
   - Create data_ingestion.py
   - Create google_calendar_sync.py

4. **Refactor orchestrator**:
   - Use LangChain agents
   - Create custom tools

---

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Access PostgreSQL
psql -h localhost -U postgres -d ethic-companion

# Check Weaviate health
curl http://localhost:8080/v1/meta

# Run tests
pytest tests/ -v

# Run specific V2 test
pytest tests/test_relevance_scoring.py -v

# Check code coverage
pytest --cov=. --cov-report=html
```

---

## Support

If you encounter issues:
1. Check `docker-compose logs` for errors
2. Verify all services are running: `docker-compose ps`
3. Check `.env` file has all required variables
4. Ensure virtual environment is activated

For architecture questions, see:
- `CLAUDE.md` - Project philosophy and guidelines
- `V2_IMPLEMENTATION_STATUS.md` - Detailed implementation status
- Implementation plan (provided separately)
