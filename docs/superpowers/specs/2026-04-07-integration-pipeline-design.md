# Integration Pipeline — Design Spec

**Date:** 2026-04-07
**Status:** Approved

---

## Goal

Close the core data loop: Calendar/Gmail tokens auto-refresh → sync writes real events and emails to `source_items` → LangGraph `ContextBuilder` injects that data into chat → responses reference real calendar events and emails.

---

## Problem Statement

All integration infrastructure (OAuth, connectors, `source_items` table, LangGraph graph) exists but the pipeline is broken:

- Access tokens for Google Calendar and Gmail expired 2026-03-25
- No auto-refresh logic — every token expiry silently breaks sync
- `source_items` has 7 rows (all `document` type); zero Calendar/Gmail rows
- `ContextBuilder` never reads `source_items`
- Chat has no real context to reason over

---

## Architecture

Five layers, each depending on the one before:

```
Token management
    └── Connector sync (Calendar, Gmail)
            └── source_items (normalized store)
                    └── ContextManager.get_recent_source_items
                            └── ContextBuilder node → chat system prompt
```

---

## Section 1: Token Management

### `DataIngestionService._get_valid_token(user_id, source_type) → str`

Called by every connector before making an API request.

**Algorithm:**
1. Load `oauth_token_encrypted`, `token_expires_at`, `oauth_refresh_token_encrypted` from `data_sources` WHERE `user_id` AND `source_type`
2. If `token_expires_at > now() + 5 minutes` → return token as-is
3. If expired → POST to Google token endpoint with `grant_type=refresh_token` and stored refresh token
4. On refresh success → UPDATE `oauth_token_encrypted`, `token_expires_at` in DB → return new token
5. On refresh failure (HTTP 400/401, or no refresh token stored):
   - UPDATE `data_sources SET enabled=FALSE, sync_error_message='Token expired — reconnect required'`
   - Raise `TokenExpiredError(source_type)`

**Google token refresh endpoint:** `POST https://oauth2.googleapis.com/token`
Fields: `client_id`, `client_secret`, `refresh_token`, `grant_type=refresh_token`
Response: `access_token`, `expires_in` (seconds)

### `TokenExpiredError`

New exception class in `services/data_ingestion.py`. Caught by `trigger_manual_sync` route — returns HTTP 422 with `{"detail": "Token expired — reconnect required", "reconnect_url": "/api/data-sources/oauth/{source_type}/authorize"}`.

---

## Section 2: Connector Sync

Both connectors replace their direct token reads with `await self._get_valid_token(user_id, source_type)`.

### GoogleCalendarConnector

Fetches events for the next 14 days via Google Calendar API `events.list`:
- `timeMin = now()`, `timeMax = now() + 14 days`, `singleEvents=True`, `orderBy=startTime`
- Max 50 events per sync

Each event writes to `source_items`:
```
source_type       = 'google_calendar'
source_item_type  = 'calendar_event'
external_id       = event['id']
title             = event['summary']
body              = f"{event.get('description','')}\nAttendees: {', '.join(attendee_names)}\n{start} → {end}"
item_at           = event start datetime (UTC)
metadata          = {location, hangoutLink, organizer_email}
```

### GmailConnector

Fetches last 50 messages from inbox via Gmail API `messages.list` + `messages.get`:
- Query: `in:inbox`, max 50 results
- Fetches `snippet`, `payload.headers` (Subject, From, Date)

Each message writes to `source_items`:
```
source_type       = 'gmail'
source_item_type  = 'email'
external_id       = message['id']
title             = subject header value
body              = f"From: {from_header}\n{snippet}"
item_at           = date header parsed to UTC datetime
metadata          = {thread_id, from_email, label_ids}
```

### Deduplication

Both connectors use:
```sql
INSERT INTO source_items (...) VALUES (...)
ON CONFLICT (user_id, source_type, external_id)
DO UPDATE SET title=EXCLUDED.title, body=EXCLUDED.body, item_at=EXCLUDED.item_at,
              metadata=EXCLUDED.metadata, synced_at=now()
```

Re-syncing is always safe.

### Sync response

`POST /api/data-sources/sync/{source_type}` response gains:
```json
{
  "success": true,
  "message": "Synced 12 items",
  "items_synced": 12,
  "source_type": "google_calendar",
  "recent": [
    {"title": "Team standup", "item_at": "2026-04-08T09:00:00Z"},
    {"title": "Design review", "item_at": "2026-04-09T14:00:00Z"},
    {"title": "1:1 with Alice", "item_at": "2026-04-10T10:00:00Z"}
  ]
}
```

---

## Section 3: Integrations UI

### `GET /api/data-sources/connected` — extended response

Each source object gains a `recent_items` field (max 3, most recent first):
```json
{
  "source_type": "google_calendar",
  "enabled": true,
  "last_sync": "2026-04-07T10:00:00Z",
  "token_expires_at": "2026-04-07T11:00:00Z",
  "status": "synced",
  "item_count": 23,
  "sync_error": null,
  "sync_error_count": 0,
  "recent_items": [
    {"title": "Team standup", "item_at": "2026-04-08T09:00:00Z"},
    {"title": "Design review", "item_at": "2026-04-09T14:00:00Z"}
  ]
}
```

### Status values (derived in backend, not stored)

| Condition | `status` value |
|---|---|
| `enabled=true`, `last_sync` within 24h | `"synced"` |
| `enabled=true`, `last_sync` > 24h or null | `"sync_needed"` |
| `sync_error_message` contains "reconnect required" | `"token_expired"` |
| Not in `data_sources` table | `"disconnected"` |

### Frontend integration card changes (`frontend/app/dashboard/integrations/page.tsx`)

**Status badge** — replaces binary connected/disconnected pill:
- 🟢 Synced
- 🟡 Sync needed
- 🔴 Token expired
- ⚫ Disconnected

**Action buttons:**
- "Sync now" button — when status is `synced` or `sync_needed`; calls `POST /api/data-sources/sync/{type}`; shows spinner; on success updates `item_count` and `recent_items` from response
- "Reconnect" button — when status is `token_expired`; links to `GET /api/data-sources/oauth/{type}/authorize`

**Recent items preview** — shown only when `item_count > 0`, below the stat row:
- Calendar row: `"{title} · {relative_time}"` (e.g. "Team standup · in 2h")
- Gmail row: `"{from_name}: {title}"` truncated to one line
- Max 3 items; no click action in v1

---

## Section 4: ContextManager

### New method: `get_recent_source_items(user_id, limit=20) → list[dict]`

```sql
SELECT source_type, source_item_type, title, body, item_at
FROM source_items
WHERE user_id = %s
  AND item_at >= now() - interval '7 days'
ORDER BY item_at DESC
LIMIT %s
```

Returns list of dicts: `{source_type, source_item_type, title, body, item_at_iso}`.

Returns `[]` gracefully if `source_items` is empty or query fails — never raises.

---

## Section 5: LangGraph ContextBuilder Node

### `AgentState` — new field

```python
source_context: list[dict]  # default []
```

### `context_builder_node` update

After existing `get_user_context` and `get_conversation_history` calls, add:

```python
source_context = await cm.get_recent_source_items(user_id, limit=20)
```

Returns updated state with `source_context` populated.

### `ResponseFormatter` node — system prompt injection

When `source_context` is non-empty, prepend to the system prompt:

```
## Your current context

[Calendar — next 7 days]
- {title} · {relative_time}
...

[Recent emails]
- {from}: {title} ({relative_time})
...
```

Items are grouped by `source_type`, sorted by `item_at`. Only calendar_event and email types rendered; other types silently skipped (future-proof). Section omitted entirely when `source_context` is empty.

---

## Section 6: Testing

### New test files

**`backend/tests/test_token_refresh.py`**
- `test_valid_token_returned_without_refresh` — token not expired, returned immediately
- `test_expired_token_triggers_refresh` — expired token, mock Google returns new token, DB updated
- `test_refresh_failure_disables_source` — refresh returns 400, `enabled=False` set, `TokenExpiredError` raised
- `test_missing_refresh_token_raises_error` — no refresh token stored, raises immediately

**`backend/tests/test_sync_source_items.py`**
- `test_calendar_sync_writes_source_items` — mock Google Calendar API, verify rows written
- `test_gmail_sync_writes_source_items` — mock Gmail API, verify rows written
- `test_sync_deduplication` — sync twice, verify no duplicate rows (ON CONFLICT)
- `test_sync_returns_recent_items` — response includes `recent` array

**`backend/tests/test_context_source_items.py`**
- `test_context_builder_populates_source_context` — mock `get_recent_source_items`, verify `source_context` in state
- `test_context_builder_empty_when_no_items` — no source_items, `source_context` is `[]`
- `test_system_prompt_includes_context_section` — non-empty `source_context`, verify prompt contains calendar/email section
- `test_system_prompt_omits_section_when_empty` — empty `source_context`, verify no context section in prompt

### Updated tests

**`backend/tests/test_langgraph_orchestrator.py`** — `base_state()` dict gains `"source_context": []`

### Manual smoke-test

1. Reconnect Google Calendar via integrations page
2. Click "Sync now" → card shows item count + 3 preview events
3. Open chat → ask "what's on my calendar this week?"
4. Response references real event titles from `source_items`

---

## Files Changed

| File | Change |
|---|---|
| `backend/services/data_ingestion.py` | `_get_valid_token`, `TokenExpiredError`, connector updates, `recent` in sync response |
| `backend/services/connectors/google_calendar.py` | Use `_get_valid_token`, write normalized `source_items` |
| `backend/services/connectors/gmail.py` | Use `_get_valid_token`, write normalized `source_items` |
| `backend/routes/data_sources.py` | `connected` response includes `recent_items` + `status`; `sync` returns `recent` |
| `backend/services/context_manager.py` | `get_recent_source_items` method |
| `backend/orchestrator/nodes/context.py` | Fetch + store `source_context` |
| `backend/orchestrator/nodes/response.py` | Inject context section into system prompt |
| `backend/orchestrator/state.py` | `source_context: list[dict]` field |
| `frontend/app/dashboard/integrations/page.tsx` | Status badge, Sync/Reconnect buttons, recent items preview |
| `frontend/lib/api.ts` | `ConnectedSource` type gains `recent_items`, `status` fields |
| `backend/tests/test_token_refresh.py` | New |
| `backend/tests/test_sync_source_items.py` | New |
| `backend/tests/test_context_source_items.py` | New |
| `backend/tests/test_langgraph_orchestrator.py` | Add `source_context: []` to `base_state()` |
