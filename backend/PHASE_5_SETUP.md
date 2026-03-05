# Phase 5: Google Calendar Integration - Setup Guide

## 🎯 What We Built

Phase 5 adds **real user data** to your V2 architecture:

- ✅ Google Calendar OAuth2 flow
- ✅ Periodic syncing every 15 minutes (background scheduler)
- ✅ Event storage in M1 (PostgreSQL) + M2 (Weaviate embeddings)
- ✅ API endpoints for manual sync and connection management

---

## 📋 Prerequisites

1. **Google Cloud Project**: Free tier is sufficient
2. **Google Calendar API**: Enabled in your project
3. **OAuth 2.0 Credentials**: Client ID and Secret
4. **Backend running**: Docker containers (PostgreSQL, Weaviate) operational

---

## 🔧 Step 1: Google Cloud Console Setup

### 1.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Note your **Project ID**

### 1.2 Enable Google Calendar API

1. Navigate to **APIs & Services** > **Library**
2. Search for "Google Calendar API"
3. Click **Enable**

### 1.3 Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. If prompted, configure OAuth consent screen:
   - **User Type**: External (for testing) or Internal (for organization)
   - **App name**: "Ethic Companion" (or your choice)
   - **User support email**: Your email
   - **Developer contact**: Your email
   - **Scopes**: Add `.../auth/calendar.readonly`
   - **Test users**: Add your Gmail address

4. Create OAuth Client ID:
   - **Application type**: Web application
   - **Name**: "Ethic Companion Backend"
   - **Authorized redirect URIs**: Add:
     ```
     http://localhost:8000/api/data-sources/oauth/google-calendar/callback
     ```
   - Click **CREATE**

5. **Download credentials**:
   - You'll see your **Client ID** and **Client Secret**
   - Click **DOWNLOAD JSON** (optional, for backup)
   - Copy Client ID and Client Secret

---

## 🔑 Step 2: Configure Environment Variables

Add to your `.env` file:

```bash
# Google OAuth (Phase 5)
GOOGLE_OAUTH_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret-here
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/data-sources/oauth/google-calendar/callback
```

**Security Note**:
- ⚠️ NEVER commit `.env` to git
- In production, use environment variables or secret management (AWS Secrets Manager, etc.)
- OAuth tokens should be encrypted in database (currently plain text for MVP)

---

## 🚀 Step 3: Start the Backend

```bash
cd backend

# Ensure Docker containers are running
docker-compose up -d

# Start FastAPI server
python main.py
```

You should see:
```
🚀 Ethic Companion Backend Starting...
⚖️  Ethical Safeguard Layer: ACTIVE
🎯 Mission: Trust over Engagement
🔄 Background Scheduler: STARTED
   - Calendar sync: Every 15 minutes
```

---

## 🧪 Step 4: Test the Integration

### Test 1: OAuth Flow

1. **Start OAuth**:
   ```bash
   curl http://localhost:8000/api/data-sources/oauth/google_calendar/authorize
   ```

   Response:
   ```json
   {
     "authorization_url": "https://accounts.google.com/o/oauth2/auth?..."
   }
   ```

2. **Authorize in Browser**:
   - Copy the `authorization_url`
   - Open in browser
   - Sign in with Google
   - Grant calendar read permission
   - You'll be redirected to: `http://localhost:8000/api/data-sources/oauth/google-calendar/callback?code=...&state=...`

3. **Check Connection**:
   ```bash
   curl http://localhost:8000/api/data-sources/connected
   ```

   Response:
   ```json
   [
     {
       "source_type": "google_calendar",
       "enabled": true,
       "last_sync": "2026-02-06T12:00:00Z",
       "status": "connected"
     }
   ]
   ```

### Test 2: Manual Sync

```bash
curl -X POST http://localhost:8000/api/data-sources/sync/google_calendar
```

Response:
```json
{
  "success": true,
  "message": "Synced 15 items from google_calendar",
  "items_synced": 15,
  "source_type": "google_calendar"
}
```

### Test 3: Verify Events in Database

```bash
psql -h localhost -U postgres -d ethic-companion -c "SELECT title, start_time, source FROM events LIMIT 5;"
```

Expected output:
```
          title          |       start_time        |     source
-------------------------+-------------------------+-----------------
 Team Meeting            | 2026-02-07 14:00:00+00  | google_calendar
 Python Workshop         | 2026-02-08 18:00:00+00  | google_calendar
```

### Test 4: Check Scheduler Status

```bash
curl http://localhost:8000/api/scheduler/status
```

(If you add this endpoint - optional)

---

## 📊 Step 5: Verify M1 + M2 Storage

### M1 (PostgreSQL) - Structured Storage

Events are stored with full metadata for SQL queries:

```sql
SELECT
    title,
    description,
    start_time,
    location,
    metadata->>'google_event_id' as google_id
FROM events
WHERE user_id = '00000000-0000-0000-0000-000000000000'
ORDER BY start_time DESC
LIMIT 5;
```

### M2 (Weaviate) - Semantic Search

Events are embedded for semantic queries:

```bash
curl -X POST http://localhost:8000/api/test/semantic-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "meeting with team",
    "limit": 5
  }'
```

This enables context-aware responses like:
> "What meetings do I have this week?"

---

## 🔄 How It Works

### OAuth Flow

```
User → Frontend → Backend → Google OAuth
                              ↓
                         Authorization Code
                              ↓
Backend ← Exchange for Tokens ← Google
   ↓
Store in database (data_sources table)
   ↓
Trigger initial sync
```

### Background Sync (Every 15 Minutes)

```
Scheduler (APScheduler)
   ↓
Get all users with calendar connected
   ↓
For each user:
   ↓
   1. Fetch events from Google Calendar API
   2. Normalize to Event model
   3. Store in M1 (PostgreSQL)
   4. Generate embeddings (Gemini)
   5. Store in M2 (Weaviate)
   6. Update last_sync timestamp
```

### Data Flow

```
Google Calendar API
   ↓
google_calendar_sync.py
   ↓
data_ingestion.py (orchestrator)
   ↓
├─> M1: context_manager.store_event()  (PostgreSQL)
└─> M2: context_manager.store_semantic_memory()  (Weaviate)
```

---

## 🗂️ Database Schema

Events are stored in the `events` table:

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    location TEXT,
    source TEXT NOT NULL,  -- 'google_calendar', 'manual', etc.
    source_id TEXT,  -- Google event ID
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

OAuth credentials are stored in `data_sources`:

```sql
CREATE TABLE data_sources (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    source_type TEXT NOT NULL,  -- 'google_calendar'
    oauth_token_encrypted TEXT,  -- ⚠️ Plain text in MVP, encrypt for production
    oauth_refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,
    enabled BOOLEAN DEFAULT TRUE,
    last_sync TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);
```

---

## 🔐 Security Considerations

### ⚠️ MVP Security (Current State)

- OAuth tokens stored in **plain text** in database
- No token encryption
- OAuth flow uses HTTP (localhost)

### ✅ Production Security (TODO)

Before going to production:

1. **Encrypt OAuth tokens** in database:
   ```python
   from cryptography.fernet import Fernet

   cipher = Fernet(settings.ENCRYPTION_KEY)
   encrypted_token = cipher.encrypt(access_token.encode())
   ```

2. **Use HTTPS** for OAuth redirect:
   ```
   https://yourdomain.com/api/data-sources/oauth/google-calendar/callback
   ```

3. **Implement token refresh** before expiration:
   - Tokens expire after 1 hour
   - Refresh tokens are long-lived
   - Implement automatic refresh in scheduler

4. **Add rate limiting** to OAuth endpoints

5. **Audit logging** for all data source operations

---

## 🎯 Next Steps

### Immediate Testing:

1. **Set up Google OAuth** (Steps 1-2)
2. **Test OAuth flow** (Step 4, Test 1)
3. **Verify calendar sync** (Step 4, Test 2-3)
4. **Check background scheduler** (watch logs for 15-minute sync)

### Integration with V2:

Your orchestrator can now use real calendar data:

```python
# In orchestrator_v2.py, user's events are automatically included in context
context = await self.context_manager.get_current_context(user_id)
# context.upcoming_events now contains Google Calendar events!
```

Example Gemini response:
> "You have a Team Meeting at 2 PM today and Python Workshop at 6 PM. Given your 'No work after 7pm' value, the workshop is cutting it close."

---

## 📝 API Endpoints Reference

### OAuth

- `GET /api/data-sources/oauth/{source_type}/authorize`
  - Returns authorization URL

- `GET /api/data-sources/oauth/{source_type}/callback?code=...&state=...`
  - Handles OAuth callback

### Sync

- `POST /api/data-sources/sync/{source_type}`
  - Manually trigger sync

- `GET /api/data-sources/connected`
  - List connected sources

- `DELETE /api/data-sources/{source_type}`
  - Disconnect source

### Health

- `GET /api/data-sources/health`
  - Service health check

---

## 🐛 Troubleshooting

### "OAuth credentials not found"

**Cause**: GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET not set

**Fix**: Add to `.env` file

---

### "Redirect URI mismatch"

**Cause**: Google Console redirect URI doesn't match application

**Fix**: Ensure Google Console has exact URI:
```
http://localhost:8000/api/data-sources/oauth/google-calendar/callback
```

---

### "Token expired"

**Cause**: Access token expired (1 hour lifetime)

**Fix**:
- Scheduler will attempt refresh automatically
- Or re-authorize via OAuth flow

---

### "Scheduler not starting"

**Check**:
1. Weaviate is running: `curl http://localhost:8080/v1/meta`
2. PostgreSQL is running: `psql -h localhost -U postgres -c "SELECT 1"`
3. Check logs for error messages

---

## 📊 Files Created

```
backend/
├── services/
│   ├── google_calendar_sync.py  (OAuth + API integration)
│   ├── data_ingestion.py         (M1 + M2 orchestration)
│   └── scheduler.py               (Background tasks)
├── routes/
│   └── data_sources.py            (API endpoints)
├── config.py                      (Added OAuth settings)
└── main.py                        (Added scheduler startup)
```

---

## ✅ Success Criteria

Phase 5 is complete when:

1. ✅ User can authorize Google Calendar
2. ✅ Events sync to database
3. ✅ Events appear in M2 (Weaviate) for semantic search
4. ✅ Background scheduler runs every 15 minutes
5. ✅ Orchestrator V2 includes calendar events in context
6. ✅ Gemini responses reference calendar events

---

**Phase 5 Status**: Ready for testing!

**Next**: Phase 6 (Feedback & UI) or Phase 7 (Documentation)
