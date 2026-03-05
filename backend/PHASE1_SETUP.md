# Phase 1 Setup: Weaviate Infrastructure

## Prerequisites

1. Docker Desktop installed and running
2. Python 3.13+ with venv
3. Git

## Setup Steps

### 1. Install Dependencies

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file has been updated with:
- `WEAVIATE_URL=http://localhost:8080` (M2 - Semantic Memory)
- `GEMINI_API_KEY=` (add your Gemini API key)

**ACTION REQUIRED**: Add your Gemini API key to `.env`:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

Get a Gemini API key from: https://makersuite.google.com/app/apikey

### 3. Start Docker Services

```bash
cd backend
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432) - M1 structured memory
- Weaviate (port 8080) - M2 semantic memory

### 4. Verify Weaviate Setup

```bash
# Check Weaviate health
curl http://localhost:8080/v1/meta

# Run automated test
python scripts/test_weaviate.py
```

Expected output:
```
✅ Connected to Weaviate successfully
📚 Available Collections:
  - ConversationMemory
  - ContextualEvents
  - UserGoals
✅ All tests passed! Weaviate is ready for V2.
```

## Architecture Overview

### Two-Memory System

**M1 (PostgreSQL)**
- Structured data: users, user_values, goals, events
- Fast queries for exact matches
- Traditional relational database

**M2 (Weaviate)**
- Semantic embeddings: conversation history, events, goals
- Vector similarity search
- Enables contextual retrieval

### Weaviate Collections

1. **ConversationMemory**
   - User messages and AI responses
   - Enables "remember what we discussed" queries

2. **ContextualEvents**
   - Calendar events with semantic understanding
   - Enables "events related to my goals" queries

3. **UserGoals**
   - Goals with semantic embeddings
   - Enables relevance scoring based on goal alignment

## Troubleshooting

### Weaviate Connection Failed

```bash
# Check if Weaviate is running
docker ps | grep weaviate

# View Weaviate logs
docker-compose logs weaviate

# Restart Weaviate
docker-compose restart weaviate
```

### Port 8080 Already in Use

Edit `docker-compose.yml` and change:
```yaml
ports:
  - "8081:8080"  # Use 8081 on host
```

Then update `.env`:
```
WEAVIATE_URL=http://localhost:8081
```

## Next Steps

- Phase 1.2: Implement Firebase Authentication
- Phase 1.3: Migrate database schema for V2

## Files Created

- `backend/docker-compose.yml` - Added Weaviate service
- `backend/config/weaviate_config.py` - Schema definitions
- `backend/utils/weaviate_client.py` - Client wrapper
- `backend/scripts/test_weaviate.py` - Verification script
- `backend/.env` - Added WEAVIATE_URL and GEMINI_API_KEY
- `backend/config.py` - Updated with new env vars
- `backend/requirements.txt` - Added V2 dependencies
