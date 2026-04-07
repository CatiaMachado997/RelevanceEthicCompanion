# Integration Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the core data loop — Calendar/Gmail tokens auto-refresh → sync writes real events and emails to `source_items` → LangGraph `ContextBuilder` injects that data into chat → responses reference real calendar events and emails.

**Architecture:** `DataIngestionService._get_valid_token()` is the single source of truth for token refresh (persists new tokens to DB). Connectors normalize items into `source_items`. `ContextManager.get_recent_source_items()` queries the last 7 days. `context_builder_node` stores results in `AgentState.source_context`, and `_build_system_prompt` injects them into the LLM system prompt.

**Tech Stack:** Python/FastAPI, psycopg3 dict_row, `google.oauth2.credentials.Credentials` for token refresh, Next.js/TypeScript frontend.

---

## File Map

| File | Change |
|---|---|
| `backend/services/data_ingestion.py` | Add `TokenExpiredError`, `_get_valid_token()`, `_mark_token_expired()`, `_get_recent_synced_items()`, `_derive_status()`; update `sync_data_source()` and `get_connected_sources()` |
| `backend/services/connectors/google_calendar.py` | Fix `normalize_to_source_item()`: `source_item_type="calendar_event"`, rich body, correct metadata |
| `backend/services/gmail_sync.py` | Add `thread_id` and `label_ids` to message dict returned by `fetch_messages()` |
| `backend/services/connectors/gmail.py` | Fix `normalize_to_source_item()`: parse RFC-2822 date to UTC ISO, fix metadata keys |
| `backend/routes/data_sources.py` | Catch `TokenExpiredError` in `trigger_manual_sync`, return HTTP 422 |
| `backend/services/context_manager.py` | Add `get_recent_source_items(user_id, limit=20) → list` |
| `backend/orchestrator/state.py` | Add `source_context: list` field |
| `backend/orchestrator/nodes/context.py` | Call `get_recent_source_items`, store in both `user_context["source_context"]` and top-level `source_context` |
| `backend/orchestrator/nodes/tools.py` | Read `source_context` in `_build_system_prompt`, inject calendar/email section |
| `frontend/lib/api.ts` | Extend `DataSource` type with `status`, `recent_items`, `item_count`; update `sync()` return type |
| `frontend/app/dashboard/integrations/page.tsx` | `StatusBadge` component, `handleReconnect`, updated `handleSync`, recent items preview |
| `backend/tests/test_token_refresh.py` | New — 4 tests |
| `backend/tests/test_sync_source_items.py` | New — 4 tests |
| `backend/tests/test_context_source_items.py` | New — 4 tests |
| `backend/tests/test_langgraph_orchestrator.py` | Add `source_context: []` to `base_state()` |

---

## Task 1: TokenExpiredError + `_get_valid_token`

**Files:**
- Modify: `backend/services/data_ingestion.py`
- Create: `backend/tests/test_token_refresh.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_token_refresh.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from services.data_ingestion import DataIngestionService, TokenExpiredError
from services.context_manager import ContextManager


def _make_svc():
    return DataIngestionService(MagicMock(spec=ContextManager))


def _db_mock(row):
    """Return a mock context manager for get_db_connection that yields `row` from fetchone()."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = row
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


@pytest.mark.asyncio
async def test_valid_token_returned_without_refresh():
    """Token not expired — returned immediately, no refresh call made."""
    svc = _make_svc()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "valid_token",
        "oauth_refresh_token_encrypted": "refresh_tok",
        "token_expires_at": future,
    }
    mock_conn, _ = _db_mock(row)
    with patch("services.data_ingestion.get_db_connection", return_value=mock_conn), \
         patch("services.data_ingestion.Credentials") as mock_creds_cls:
        token = await svc._get_valid_token("user1", "google_calendar")
    assert token == "valid_token"
    mock_creds_cls.assert_not_called()


@pytest.mark.asyncio
async def test_expired_token_triggers_refresh():
    """Expired token — Google returns new token and DB is updated."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": "refresh_tok",
        "token_expires_at": past,
    }
    mock_conn, mock_cur = _db_mock(row)
    mock_creds = MagicMock()
    mock_creds.token = "new_access_token"
    mock_creds.expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    with patch("services.data_ingestion.get_db_connection", return_value=mock_conn), \
         patch("services.data_ingestion.Credentials", return_value=mock_creds), \
         patch("services.data_ingestion.Request"):
        token = await svc._get_valid_token("user1", "google_calendar")
    assert token == "new_access_token"
    execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "UPDATE" in execute_calls


@pytest.mark.asyncio
async def test_refresh_failure_disables_source():
    """Refresh fails (invalid_grant) — source disabled, TokenExpiredError raised."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": "bad_refresh",
        "token_expires_at": past,
    }
    mock_conn, mock_cur = _db_mock(row)
    mock_creds = MagicMock()
    mock_creds.refresh.side_effect = Exception("invalid_grant")
    with patch("services.data_ingestion.get_db_connection", return_value=mock_conn), \
         patch("services.data_ingestion.Credentials", return_value=mock_creds), \
         patch("services.data_ingestion.Request"):
        with pytest.raises(TokenExpiredError):
            await svc._get_valid_token("user1", "google_calendar")
    execute_calls = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "enabled = FALSE" in execute_calls


@pytest.mark.asyncio
async def test_missing_refresh_token_raises_error():
    """No refresh token stored — raises TokenExpiredError immediately, no network call."""
    svc = _make_svc()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    row = {
        "oauth_token_encrypted": "old_token",
        "oauth_refresh_token_encrypted": None,
        "token_expires_at": past,
    }
    mock_conn, _ = _db_mock(row)
    with patch("services.data_ingestion.get_db_connection", return_value=mock_conn), \
         patch("services.data_ingestion.Credentials") as mock_creds_cls:
        with pytest.raises(TokenExpiredError):
            await svc._get_valid_token("user1", "google_calendar")
    mock_creds_cls.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest tests/test_token_refresh.py -v 2>&1 | head -30
```
Expected: `ImportError: cannot import name 'TokenExpiredError' from 'services.data_ingestion'`

- [ ] **Step 3: Add `TokenExpiredError`, module-level imports, `_get_valid_token`, `_mark_token_expired` to `data_ingestion.py`**

At the top of `backend/services/data_ingestion.py`, after existing imports, add:

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
```

After the `SUPPORTED_SOURCES` line, add:

```python
class TokenExpiredError(Exception):
    """Raised when an OAuth token has expired and cannot be refreshed."""
    def __init__(self, source_type: str):
        self.source_type = source_type
        super().__init__(f"Token expired for {source_type} — reconnect required")
```

Inside `DataIngestionService`, add these two methods (after `_get_data_source_tokens`):

```python
async def _get_valid_token(self, user_id: str, source_type: str) -> str:
    """
    Return a valid access token, refreshing if it expires within 5 minutes.
    Persists new token to DB on refresh. Raises TokenExpiredError if refresh fails.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT oauth_token_encrypted, oauth_refresh_token_encrypted, token_expires_at
                FROM data_sources
                WHERE user_id = %s AND source_type = %s AND enabled = TRUE
                """,
                (user_id, source_type),
            )
            row = cur.fetchone()

    if not row:
        raise TokenExpiredError(source_type)

    access_token = row["oauth_token_encrypted"]
    refresh_token = row["oauth_refresh_token_encrypted"]
    expires_at = row["token_expires_at"]

    # Normalise expires_at to an aware datetime
    if expires_at is not None:
        if hasattr(expires_at, "tzinfo"):
            expires_aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_aware = datetime.fromisoformat(str(expires_at)).replace(tzinfo=timezone.utc)
    else:
        expires_aware = None

    now = datetime.now(timezone.utc)
    if expires_aware and expires_aware > now + timedelta(minutes=5):
        return access_token  # Still valid

    # Token expired — try to refresh
    if not refresh_token:
        await self._mark_token_expired(user_id, source_type)
        raise TokenExpiredError(source_type)

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        )
        creds.refresh(Request())
        new_expires_at = now + timedelta(seconds=3600)  # Google default: 1h
        if creds.expiry:
            new_expires_at = datetime.fromtimestamp(
                creds.expiry.timestamp(), tz=timezone.utc
            )
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET oauth_token_encrypted = %s, token_expires_at = %s
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (creds.token, new_expires_at, user_id, source_type),
                )
            conn.commit()
        logger.info(f"✅ Token refreshed for {source_type}, user {user_id}")
        return creds.token
    except Exception as e:
        logger.warning(f"⚠️  Token refresh failed for {source_type}: {e}")
        await self._mark_token_expired(user_id, source_type)
        raise TokenExpiredError(source_type)

async def _mark_token_expired(self, user_id: str, source_type: str):
    """Disable source and record reconnect-required error."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE data_sources
                SET enabled = FALSE,
                    sync_error_message = 'Token expired — reconnect required'
                WHERE user_id = %s AND source_type = %s
                """,
                (user_id, source_type),
            )
        conn.commit()
```

Also add `timedelta` to the existing import at the top of the file — it's already imported as part of `from datetime import datetime, timezone`.

Change the existing import line from:
```python
from datetime import datetime, timezone
```
to:
```python
from datetime import datetime, timezone, timedelta
```

- [ ] **Step 4: Update `sync_data_source` to use `_get_valid_token`**

In `sync_data_source`, replace:
```python
tokens = await self._get_data_source_tokens(user_id, source_type)
if not tokens:
    return {"success": False, "message": f"{source_type} not connected", "items_synced": 0}

try:
    connector = get_connector(source_type)
    raw_items = await connector.fetch_raw_items(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
    )
```

With:
```python
try:
    access_token = await self._get_valid_token(user_id, source_type)
except TokenExpiredError:
    raise  # route layer handles this

try:
    connector = get_connector(source_type)
    raw_items = await connector.fetch_raw_items(
        access_token=access_token,
        refresh_token=None,  # token is already fresh
    )
```

- [ ] **Step 5: Catch `TokenExpiredError` in `trigger_manual_sync` route**

In `backend/routes/data_sources.py`, add the import at the top:
```python
from services.data_ingestion import DataIngestionService, TokenExpiredError
```

In `trigger_manual_sync`, wrap the existing try/except to catch `TokenExpiredError` first:

```python
@router.post("/sync/{source_type}")
async def trigger_manual_sync(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion)
) -> Dict[str, Any]:
    try:
        result = await ingestion.sync_data_source(user_id, source_type)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Token expired — reconnect required",
                "reconnect_url": f"/api/data-sources/oauth/{source_type}/authorize",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sync failed")
```

- [ ] **Step 6: Run tests — should pass**

```bash
pytest tests/test_token_refresh.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
git add services/data_ingestion.py routes/data_sources.py tests/test_token_refresh.py
git commit -m "feat: add TokenExpiredError and _get_valid_token with auto-refresh and DB persistence"
```

---

## Task 2: Fix GoogleCalendarConnector + `_store_normalized_item` bug

**Files:**
- Modify: `backend/services/connectors/google_calendar.py`
- Modify: `backend/services/data_ingestion.py` (fix DO UPDATE missing `item_at`)
- Create: `backend/tests/test_sync_source_items.py` (first 2 tests)

- [ ] **Step 1: Write the failing calendar tests**

Create `backend/tests/test_sync_source_items.py`:

```python
import pytest
from services.connectors.google_calendar import GoogleCalendarConnector
from services.connectors.gmail import GmailConnector
from services import data_ingestion
import inspect


def _calendar_raw():
    return {
        "id": "evt123",
        "summary": "Team standup",
        "description": "Daily sync",
        "start": {"dateTime": "2026-04-08T09:00:00+00:00"},
        "end": {"dateTime": "2026-04-08T09:30:00+00:00"},
        "attendees": [
            {"displayName": "Alice", "email": "alice@example.com"},
            {"email": "bob@example.com"},
        ],
        "organizer": {"email": "alice@example.com"},
        "location": "Zoom",
        "hangoutLink": "https://meet.google.com/abc",
    }


def _gmail_raw():
    return {
        "id": "msg456",
        "thread_id": "thread789",
        "subject": "Hello world",
        "from": "Alice <alice@example.com>",
        "date": "Tue, 08 Apr 2026 10:00:00 +0000",
        "snippet": "Just checking in",
        "label_ids": ["INBOX", "UNREAD"],
    }


def test_calendar_sync_writes_source_items():
    """normalize_to_source_item produces source_item_type=calendar_event with rich body."""
    connector = GoogleCalendarConnector(redirect_uri="http://localhost")
    item = connector.normalize_to_source_item(_calendar_raw(), "user1")

    assert item.source_item_type == "calendar_event"
    assert item.external_id == "evt123"
    assert item.title == "Team standup"
    assert "Alice" in item.body
    assert "bob@example.com" in item.body
    assert item.item_at is not None and "2026-04-08" in item.item_at
    assert item.metadata["location"] == "Zoom"
    assert item.metadata["hangoutLink"] == "https://meet.google.com/abc"
    assert item.metadata["organizer_email"] == "alice@example.com"


def test_gmail_sync_writes_source_items():
    """normalize_to_source_item produces source_item_type=email with parsed UTC date and metadata."""
    connector = GmailConnector(redirect_uri="http://localhost")
    item = connector.normalize_to_source_item(_gmail_raw(), "user1")

    assert item.source_item_type == "email"
    assert item.external_id == "msg456"
    assert item.title == "Hello world"
    assert "Alice" in item.body
    assert "Just checking in" in item.body
    assert item.item_at is not None and "2026" in item.item_at
    assert item.metadata["thread_id"] == "thread789"
    assert item.metadata["from_email"] == "Alice <alice@example.com>"
    assert "INBOX" in item.metadata["label_ids"]


def test_sync_deduplication():
    """_store_normalized_item SQL upserts on (user_id, source_type, external_id) and updates item_at."""
    source = inspect.getsource(data_ingestion.DataIngestionService._store_normalized_item)
    assert "ON CONFLICT (user_id, source_type, external_id)" in source
    assert "item_at = EXCLUDED.item_at" in source


def test_sync_returns_recent_items():
    """sync_data_source return value includes a 'recent' key."""
    source = inspect.getsource(data_ingestion.DataIngestionService.sync_data_source)
    assert '"recent"' in source or "'recent'" in source
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_sync_source_items.py -v 2>&1 | head -30
```
Expected: `test_calendar_sync_writes_source_items FAILED` (source_item_type assertion fails — currently "event")

- [ ] **Step 3: Rewrite `GoogleCalendarConnector.normalize_to_source_item`**

Replace the entire method in `backend/services/connectors/google_calendar.py`:

```python
def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
    from datetime import datetime, timezone

    start = raw.get("start", {})
    end = raw.get("end", {})
    start_str = start.get("dateTime") or start.get("date") or ""
    end_str = end.get("dateTime") or end.get("date") or ""

    # Parse start datetime to UTC ISO string
    item_at: Optional[str] = None
    if start_str:
        try:
            dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            item_at = dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            item_at = start_str

    # Build attendee display names
    attendees = raw.get("attendees", [])
    attendee_names = [
        a.get("displayName") or a.get("email", "") for a in attendees
    ]
    attendee_str = ", ".join(attendee_names) if attendee_names else "none"

    # Rich body: description + attendees + time range
    desc = (raw.get("description") or "").strip()
    body_parts = []
    if desc:
        body_parts.append(desc)
    body_parts.append(f"Attendees: {attendee_str}")
    body_parts.append(f"{start_str} → {end_str}")
    body = "\n".join(body_parts)

    return SourceItem(
        user_id=user_id,
        source_type=self.source_type,
        source_item_type="calendar_event",
        external_id=raw["id"],
        title=raw.get("summary", "(no title)"),
        body=body,
        item_at=item_at,
        metadata={
            "location": raw.get("location"),
            "hangoutLink": raw.get("hangoutLink"),
            "organizer_email": raw.get("organizer", {}).get("email"),
        },
    )
```

- [ ] **Step 4: Fix `_store_normalized_item` — add `item_at` to DO UPDATE**

In `backend/services/data_ingestion.py`, in `_store_normalized_item`, change the DO UPDATE clause from:
```python
DO UPDATE SET
    title = EXCLUDED.title,
    body = EXCLUDED.body,
    metadata = EXCLUDED.metadata,
    synced_at = NOW()
```
to:
```python
DO UPDATE SET
    title = EXCLUDED.title,
    body = EXCLUDED.body,
    item_at = EXCLUDED.item_at,
    metadata = EXCLUDED.metadata,
    synced_at = NOW()
```

- [ ] **Step 5: Run calendar tests — should pass (gmail still fails)**

```bash
pytest tests/test_sync_source_items.py::test_calendar_sync_writes_source_items tests/test_sync_source_items.py::test_sync_deduplication -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit calendar changes**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
git add services/connectors/google_calendar.py services/data_ingestion.py tests/test_sync_source_items.py
git commit -m "fix: GoogleCalendarConnector source_item_type, rich body, and fix _store_normalized_item item_at upsert"
```

---

## Task 3: Fix GmailSync + GmailConnector

**Files:**
- Modify: `backend/services/gmail_sync.py`
- Modify: `backend/services/connectors/gmail.py`

- [ ] **Step 1: Update `GmailSync.fetch_messages` — raise max_results to 50 and add `thread_id`/`label_ids`**

In `backend/services/gmail_sync.py`, change the method signature default from `max_results: int = 20` to `max_results: int = 50`.

Then, inside the `for msg in result.get('messages', []):` loop, change the `messages.append({...})` call from:

```python
messages.append({
    'id': msg['id'],
    'subject': headers.get('Subject', '(no subject)'),
    'from': headers.get('From', ''),
    'date': headers.get('Date', ''),
    'snippet': detail.get('snippet', ''),
})
```

to:

```python
messages.append({
    'id': msg['id'],
    'thread_id': msg.get('threadId', ''),
    'subject': headers.get('Subject', '(no subject)'),
    'from': headers.get('From', ''),
    'date': headers.get('Date', ''),
    'snippet': detail.get('snippet', ''),
    'label_ids': detail.get('labelIds', []),
})
```

- [ ] **Step 2: Rewrite `GmailConnector.normalize_to_source_item`**

Replace the entire class in `backend/services/connectors/gmail.py` with:

```python
# backend/services/connectors/gmail.py
"""Gmail connector — wraps GmailSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.gmail_sync import GmailSync


def _parse_email_date(date_str: str) -> Optional[str]:
    """Parse RFC-2822 email date string (e.g. 'Tue, 08 Apr 2026 10:00:00 +0000') to UTC ISO string."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        from datetime import timezone
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return date_str  # fallback: store as-is


class GmailConnector(BaseConnector):
    source_type = "gmail"

    def __init__(self, redirect_uri: str):
        self._sync = GmailSync(redirect_uri=redirect_uri)

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._sync.fetch_messages(
            access_token=access_token,
            refresh_token=refresh_token or "",
        )

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        sender = raw.get("from", "")
        subject = raw.get("subject") or "(no subject)"
        snippet = raw.get("snippet", "")
        body = f"From: {sender}\n{snippet}" if snippet else f"From: {sender}"

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="email",
            external_id=raw["id"],
            title=subject,
            body=body,
            item_at=_parse_email_date(raw.get("date", "")),
            metadata={
                "thread_id": raw.get("thread_id", ""),
                "from_email": sender,
                "label_ids": raw.get("label_ids", []),
            },
        )
```

- [ ] **Step 3: Run all sync tests — should pass**

```bash
pytest tests/test_sync_source_items.py -v
```
Expected: `4 passed`

- [ ] **Step 4: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
git add services/gmail_sync.py services/connectors/gmail.py
git commit -m "fix: GmailConnector normalizes RFC-2822 date to UTC, adds thread_id/label_ids to metadata"
```

---

## Task 4: Sync response `recent` field + `get_connected_sources` status/recent_items

**Files:**
- Modify: `backend/services/data_ingestion.py`

- [ ] **Step 1: Add `_get_recent_synced_items` and `_derive_status` methods**

In `backend/services/data_ingestion.py`, add these two methods inside `DataIngestionService` (after `_clear_sync_error`):

```python
async def _get_recent_synced_items(
    self, user_id: str, source_type: str, limit: int = 3
) -> List[Dict[str, Any]]:
    """Return the most-recent source items for display in sync responses and the connected list."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, item_at
                FROM source_items
                WHERE user_id = %s AND source_type = %s
                ORDER BY item_at DESC NULLS LAST
                LIMIT %s
                """,
                (user_id, source_type, limit),
            )
            rows = cur.fetchall()
    return [
        {
            "title": row["title"],
            "item_at": row["item_at"].isoformat() if row["item_at"] else None,
        }
        for row in rows
    ]

def _derive_status(self, row: dict) -> str:
    """Derive display status from a data_sources row dict."""
    if row.get("sync_error_message") and "reconnect required" in (
        row["sync_error_message"] or ""
    ):
        return "token_expired"
    if not row["enabled"]:
        return "disconnected"
    last_sync = row.get("last_sync")
    if last_sync is None:
        return "sync_needed"
    if not hasattr(last_sync, "tzinfo"):
        last_sync = datetime.fromisoformat(str(last_sync))
    if last_sync.tzinfo is None:
        last_sync = last_sync.replace(tzinfo=timezone.utc)
    if last_sync < datetime.now(timezone.utc) - timedelta(hours=24):
        return "sync_needed"
    return "synced"
```

- [ ] **Step 2: Update `sync_data_source` to return `recent`**

After `await self._clear_sync_error(user_id, source_type)`, and before the final return, add:

```python
recent = await self._get_recent_synced_items(user_id, source_type, limit=3)
```

Then change the success return dict from:
```python
return {
    "success": True,
    "message": f"Synced {items_synced} items from {source_type}",
    "items_synced": items_synced,
    "source_type": source_type,
}
```
to:
```python
return {
    "success": True,
    "message": f"Synced {items_synced} items",
    "items_synced": items_synced,
    "source_type": source_type,
    "recent": recent,
}
```

- [ ] **Step 3: Update `get_connected_sources` to include `status` and `recent_items`**

Replace the entire `get_connected_sources` method with:

```python
async def get_connected_sources(self, user_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ds.source_type,
                    ds.enabled,
                    ds.last_sync,
                    ds.token_expires_at,
                    ds.sync_error_message,
                    ds.sync_error_count,
                    COUNT(si.id) AS item_count
                FROM data_sources ds
                LEFT JOIN source_items si
                    ON si.user_id = ds.user_id AND si.source_type = ds.source_type
                WHERE ds.user_id = %s
                GROUP BY ds.source_type, ds.enabled, ds.last_sync,
                         ds.token_expires_at, ds.sync_error_message, ds.sync_error_count
                ORDER BY ds.source_type
                """,
                (user_id,),
            )
            rows = cur.fetchall()

    sources = []
    for row in rows:
        recent_items = await self._get_recent_synced_items(user_id, row["source_type"])
        sources.append(
            {
                "source_type": row["source_type"],
                "enabled": row["enabled"],
                "last_sync": row["last_sync"].isoformat() if row["last_sync"] else None,
                "token_expires_at": (
                    row["token_expires_at"].isoformat() if row["token_expires_at"] else None
                ),
                "status": self._derive_status(row),
                "item_count": row["item_count"],
                "sync_error": row["sync_error_message"],
                "sync_error_count": row["sync_error_count"],
                "recent_items": recent_items,
            }
        )
    return sources
```

- [ ] **Step 4: Run sync_source_items tests (incl. `test_sync_returns_recent_items`)**

```bash
pytest tests/test_sync_source_items.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
git add services/data_ingestion.py
git commit -m "feat: sync response includes recent[] array; connected sources return status + recent_items"
```

---

## Task 5: Frontend — types + integrations UI

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/dashboard/integrations/page.tsx`

- [ ] **Step 1: Update `DataSource` type and `dataSourcesApi.sync` return type in `api.ts`**

In `frontend/lib/api.ts`, replace:

```typescript
export interface DataSource {
  source_type: string
  enabled: boolean
  last_sync: string | null
  token_expires_at: string | null
  status: 'connected' | 'disconnected'
}
```

with:

```typescript
export interface DataSource {
  source_type: string
  enabled: boolean
  last_sync: string | null
  token_expires_at: string | null
  status: 'synced' | 'sync_needed' | 'token_expired' | 'disconnected'
  item_count?: number
  sync_error?: string | null
  sync_error_count?: number
  recent_items?: Array<{ title: string; item_at: string | null }>
}
```

In `dataSourcesApi.sync`, update the return type to include `recent`:

```typescript
sync: async (sourceType: string) => {
  return apiRequest<{
    success: boolean
    message: string
    items_synced: number
    source_type: string
    recent: Array<{ title: string; item_at: string | null }>
  }>(`/api/data-sources/sync/${sourceType}`, {
    method: 'POST',
  })
},
```

- [ ] **Step 2: Add helpers and `StatusBadge` to `integrations/page.tsx`**

In `frontend/app/dashboard/integrations/page.tsx`, add these two functions after the existing icon functions (before `IntegrationsContent`):

```tsx
function formatRelativeTime(isoStr: string | null | undefined): string {
  if (!isoStr) return ''
  const date = new Date(isoStr)
  const diffMs = date.getTime() - Date.now()
  const diffHours = Math.round(diffMs / (1000 * 60 * 60))
  if (diffHours < 0) return 'past'
  if (diffHours === 0) return 'now'
  if (diffHours < 24) return `in ${diffHours}h`
  return `in ${Math.round(diffHours / 24)}d`
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'synced') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e6f4ee', color: '#2d6a4f', border: '1px solid #c8e6d3' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#4A7C59' }} />
        Synced
      </span>
    )
  }
  if (status === 'sync_needed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#fff8e1', color: '#8a6600', border: '1px solid #ffe082' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#f59e0b' }} />
        Sync needed
      </span>
    )
  }
  if (status === 'token_expired') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: 'rgba(176,74,58,0.08)', color: '#B04A3A', border: '1px solid rgba(176,74,58,0.25)' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#B04A3A' }} />
        Token expired
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: '#f5f2ef', color: '#7a6e65', border: '1px solid #e4dcd7' }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#9e9e9e' }} />
      Disconnected
    </span>
  )
}
```

- [ ] **Step 3: Update `ConnectedSource` interface and `isConnected` / `handleSync` / add `handleReconnect`**

In `frontend/app/dashboard/integrations/page.tsx`, replace the `ConnectedSource` interface:

```tsx
interface ConnectedSource {
  source_type: string
  last_sync?: string | null
  enabled: boolean
  status: 'synced' | 'sync_needed' | 'token_expired' | 'disconnected'
  item_count?: number
  sync_error?: string | null
  sync_error_count?: number
  recent_items?: Array<{ title: string; item_at: string | null }>
  token_expires_at?: string | null
}
```

Inside `IntegrationsContent`, replace the `isConnected` and `lastSync` helpers:

```tsx
const sourceData = (type: SourceType) => connected.find(s => s.source_type === type)
const getStatus = (type: SourceType): string => sourceData(type)?.status ?? 'disconnected'
const isConnected = (type: SourceType) => {
  const s = getStatus(type)
  return s === 'synced' || s === 'sync_needed' || s === 'token_expired'
}
const lastSync = (type: SourceType) => sourceData(type)?.last_sync
```

Replace `handleSync` with:

```tsx
const handleSync = async (type: SourceType) => {
  setSyncing(type)
  try {
    await dataSourcesApi.sync(type)
  } catch (e) {
    const label = INTEGRATIONS.find(i => i.type === type)?.label ?? type
    setErrorFlash(`Sync failed for ${label}. If the problem persists, try reconnecting.`)
    setTimeout(() => setErrorFlash(null), 6000)
  } finally {
    setSyncing(null)
    await loadConnected()
  }
}
```

Add `handleReconnect` after `handleSync`:

```tsx
const handleReconnect = async (type: SourceType) => {
  try {
    const { authorization_url } = await dataSourcesApi.getAuthUrl(type)
    window.location.href = authorization_url
  } catch (e) {
    const label = INTEGRATIONS.find(i => i.type === type)?.label ?? type
    setErrorFlash(`Could not start ${label} reconnection. Make sure you're signed in and try again.`)
    setTimeout(() => setErrorFlash(null), 6000)
  }
}
```

- [ ] **Step 4: Update the card JSX — status badge, action buttons, recent items preview**

Inside the `INTEGRATIONS.map(...)` block, before the `return (`, add a local variable:
```tsx
const src = sourceData(type)
const status = getStatus(type)
```

Replace the existing `{isConn && (<span ...>Connected</span>)}` badge with:
```tsx
{isConn && <StatusBadge status={status} />}
```

Replace the action buttons section (the `{isConn ? (<> ... </>) : (...)}` block) with:

```tsx
{isConn ? (
  <>
    {status === 'token_expired' ? (
      <button
        onClick={() => handleReconnect(type)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
        style={{ background: 'rgba(176,74,58,0.1)', border: '1px solid rgba(176,74,58,0.3)', color: '#B04A3A' }}
      >
        Reconnect
      </button>
    ) : (
      <button
        onClick={() => handleSync(type)}
        disabled={isSyncing}
        className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-40"
        style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.08)' }}
        title={`Sync ${label}`}
        aria-label={`Sync ${label}`}
      >
        <RefreshCw size={13} style={{ color: '#695e6e' }} className={isSyncing ? 'animate-spin' : ''} />
      </button>
    )}
    <button
      onClick={() => handleDisconnect(type)}
      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
      style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.1)', color: '#695e6e' }}
    >
      Disconnect
    </button>
  </>
) : (
  <button
    onClick={() => handleConnect(type)}
    className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
    style={{ background: accentColor, color: '#ffffff' }}
  >
    Connect
  </button>
)}
```

After the closing `</div>` of the "Info" section (where `description` / `last_sync` text is shown), and before the benefits row, add the recent items preview:

```tsx
{/* Recent items preview — shown when synced and items exist */}
{isConn && (src?.recent_items ?? []).length > 0 && (
  <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
    <div className="space-y-1">
      {(src?.recent_items ?? []).slice(0, 3).map((item, i) => (
        <p key={i} className="text-[11px] truncate" style={{ color: '#695e6e' }}>
          {type === 'google_calendar'
            ? `${item.title} · ${formatRelativeTime(item.item_at)}`
            : item.title
          }
        </p>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 5: Verify TypeScript compiles without errors**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1 | head -30
```
Expected: no output (zero errors)

- [ ] **Step 6: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
git add lib/api.ts app/dashboard/integrations/page.tsx
git commit -m "feat: integrations UI — status badges (synced/sync_needed/token_expired), Reconnect button, recent items preview"
```

---

## Task 6: ContextManager + LangGraph wiring

**Files:**
- Modify: `backend/services/context_manager.py`
- Modify: `backend/orchestrator/state.py`
- Modify: `backend/orchestrator/nodes/context.py`
- Modify: `backend/orchestrator/nodes/tools.py`
- Modify: `backend/tests/test_langgraph_orchestrator.py`
- Create: `backend/tests/test_context_source_items.py`

- [ ] **Step 1: Write the failing context tests**

Create `backend/tests/test_context_source_items.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ─── ContextManager tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_context_builder_populates_source_context():
    """context_builder_node calls get_recent_source_items and stores result in state."""
    from orchestrator.nodes.context import context_builder_node

    fake_items = [
        {"source_type": "google_calendar", "source_item_type": "calendar_event",
         "title": "Standup", "body": "", "item_at": "2026-04-08T09:00:00+00:00"},
    ]

    with patch("orchestrator.nodes.context.get_context_manager") as mock_gcm:
        cm = MagicMock()
        cm.get_user_context = AsyncMock(return_value=MagicMock(
            active_goals=[], user_values=[], focus_mode=False, additional_context={}
        ))
        cm.get_conversation_history = AsyncMock(return_value=[])
        cm.get_recent_source_items = AsyncMock(return_value=fake_items)
        mock_gcm.return_value = cm

        state = {
            "user_id": "u1", "conversation_id": None,
            "source_context": [],
        }
        result = await context_builder_node(state)

    assert "source_context" in result
    assert result["source_context"] == fake_items
    assert result["user_context"]["source_context"] == fake_items


@pytest.mark.asyncio
async def test_context_builder_empty_when_no_items():
    """`source_context` is [] when get_recent_source_items returns empty."""
    from orchestrator.nodes.context import context_builder_node

    with patch("orchestrator.nodes.context.get_context_manager") as mock_gcm:
        cm = MagicMock()
        cm.get_user_context = AsyncMock(return_value=MagicMock(
            active_goals=[], user_values=[], focus_mode=False, additional_context={}
        ))
        cm.get_conversation_history = AsyncMock(return_value=[])
        cm.get_recent_source_items = AsyncMock(return_value=[])
        mock_gcm.return_value = cm

        result = await context_builder_node({"user_id": "u1", "conversation_id": None})

    assert result["source_context"] == []


def test_system_prompt_includes_context_section():
    """Non-empty source_context → system prompt contains '## Your current context'."""
    from orchestrator.nodes.tools import _build_system_prompt

    state = {
        "user_context": {
            "active_goals": [],
            "user_values": [],
            "snapshot": {},
            "source_context": [
                {"source_type": "google_calendar", "source_item_type": "calendar_event",
                 "title": "Team standup", "body": "", "item_at": "2026-04-08T09:00:00+00:00"},
                {"source_type": "gmail", "source_item_type": "email",
                 "title": "Hello world", "body": "From: alice", "item_at": "2026-04-07T10:00:00+00:00"},
            ],
        },
    }
    prompt = _build_system_prompt(state)
    assert "## Your current context" in prompt
    assert "Team standup" in prompt
    assert "Hello world" in prompt


def test_system_prompt_omits_section_when_empty():
    """Empty source_context → no '## Your current context' section in prompt."""
    from orchestrator.nodes.tools import _build_system_prompt

    state = {
        "user_context": {
            "active_goals": [],
            "user_values": [],
            "snapshot": {},
            "source_context": [],
        },
    }
    prompt = _build_system_prompt(state)
    assert "## Your current context" not in prompt
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest tests/test_context_source_items.py -v 2>&1 | head -30
```
Expected: failures because `get_recent_source_items` doesn't exist and `source_context` not in state.

- [ ] **Step 3: Add `get_recent_source_items` to `ContextManager`**

In `backend/services/context_manager.py`, add this method (before the last method in the class, or at the end of the M1 section):

```python
async def get_recent_source_items(self, user_id: str, limit: int = 20) -> list:
    """
    Fetch recent calendar events and emails from source_items for context injection.
    Returns [] gracefully on empty table or any query failure — never raises.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_type, source_item_type, title, body, item_at
                    FROM source_items
                    WHERE user_id = %s
                      AND item_at >= now() - interval '7 days'
                    ORDER BY item_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "source_type": row["source_type"],
                "source_item_type": row["source_item_type"],
                "title": row["title"],
                "body": row["body"],
                "item_at": row["item_at"].isoformat() if row["item_at"] else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"⚠️  get_recent_source_items failed: {e}")
        return []
```

- [ ] **Step 4: Add `source_context: list` to `AgentState`**

In `backend/orchestrator/state.py`, add at the end of the class:

```python
# Source items context from synced integrations
source_context: list           # [{source_type, source_item_type, title, body, item_at}]
```

- [ ] **Step 5: Update `context_builder_node` to call `get_recent_source_items`**

In `backend/orchestrator/nodes/context.py`, replace the entire `context_builder_node` function with:

```python
async def context_builder_node(state: AgentState) -> dict:
    """Populate user_context, conversation_history, and source_context from M1 + M2."""
    cm = get_context_manager()
    ctx = await cm.get_user_context(state["user_id"])
    history = await cm.get_conversation_history(
        state["user_id"], limit=20, conversation_id=state.get("conversation_id")
    )

    # Compute 360° snapshot (tasks, projects, events) — non-blocking on failure
    snapshot: dict = {}
    try:
        from services.context_snapshot import ContextSnapshotService
        snapshot = ContextSnapshotService().compute(state["user_id"])
    except Exception:
        pass

    # Fetch recent source items (calendar + email) — non-blocking on failure
    source_context: list = []
    try:
        source_context = await cm.get_recent_source_items(state["user_id"], limit=20)
    except Exception:
        pass

    return {
        "user_context": {
            "active_goals": [g.__dict__ if hasattr(g, '__dict__') else g for g in (ctx.active_goals or [])],
            "user_values": [v.__dict__ if hasattr(v, '__dict__') else v for v in (ctx.user_values or [])],
            "focus_mode": getattr(ctx, "focus_mode", False),
            "additional_context": getattr(ctx, "additional_context", {}),
            "snapshot": snapshot,
            "source_context": source_context,
        },
        "conversation_history": history or [],
        "source_context": source_context,
    }
```

- [ ] **Step 6: Update `_build_system_prompt` to inject source_context**

In `backend/orchestrator/nodes/tools.py`, inside `_build_system_prompt`, add the following block immediately after the `projects` section (after the `snapshot_sections.append(f"Active projects:\n{project_lines}")` block) and before `pressure`:

```python
    # Source context from synced integrations
    source_context = ctx.get("source_context", [])
    if source_context:
        cal_items = [
            i for i in source_context if i.get("source_item_type") == "calendar_event"
        ]
        email_items = [
            i for i in source_context if i.get("source_item_type") == "email"
        ]
        source_parts = []
        if cal_items:
            cal_lines = "\n".join(
                f"  - {item['title']} · {(item.get('item_at') or '')[:16]}"
                for item in cal_items[:10]
            )
            source_parts.append(f"[Calendar — next 7 days]\n{cal_lines}")
        if email_items:
            email_lines = "\n".join(
                f"  - {item['title']} ({(item.get('item_at') or '')[:16]})"
                for item in email_items[:10]
            )
            source_parts.append(f"[Recent emails]\n{email_lines}")
        if source_parts:
            snapshot_sections.append(
                "## Your current context\n\n" + "\n\n".join(source_parts)
            )
```

- [ ] **Step 7: Add `source_context: []` to `base_state()` in `test_langgraph_orchestrator.py`**

In `backend/tests/test_langgraph_orchestrator.py`, find `base_state()` and add `"source_context": []` to the returned dict:

```python
def base_state() -> dict:
    return {
        "user_id": "u1", "message": "", "conversation_id": None, "model": "llama",
        "user_context": {}, "conversation_history": [], "intent": "",
        "tool_calls": [], "tool_results": [], "esl_decision": None,
        "proposed_content": "", "response_text": "", "response_events": [],
        "token_count": 0, "token_warning": None,
        "source_context": [],
    }
```

- [ ] **Step 8: Run all context tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest tests/test_context_source_items.py -v
```
Expected: `4 passed`

- [ ] **Step 9: Run full test suite**

```bash
pytest -v 2>&1 | tail -20
```
Expected: all previously passing tests still pass; 12 new tests pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
git add services/context_manager.py orchestrator/state.py orchestrator/nodes/context.py \
        orchestrator/nodes/tools.py tests/test_context_source_items.py \
        tests/test_langgraph_orchestrator.py
git commit -m "feat: wire source_items into LangGraph — get_recent_source_items, source_context in AgentState, system prompt injection"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Run full backend test suite, confirm no regressions**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest -v 2>&1 | tail -30
```
Expected: all tests pass. Count should include at minimum:
- 4 tests in `test_token_refresh.py`
- 4 tests in `test_sync_source_items.py`
- 4 tests in `test_context_source_items.py`

- [ ] **Step 2: Confirm TypeScript clean**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no output.

- [ ] **Step 3: Manual smoke test — sync flow**

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000/dashboard/integrations`
4. For a connected Google Calendar source, click the sync icon
5. Verify the card updates to show:
   - Status badge changes to "Synced" (green)
   - Recent items preview appears below the stat row
6. Check `GET /api/data-sources/connected` response in Network tab — confirm `recent_items` array is present

- [ ] **Step 4: Manual smoke test — token expired flow**

1. In Postgres: `UPDATE data_sources SET token_expires_at = now() - interval '2 hours', oauth_refresh_token_encrypted = NULL WHERE source_type = 'google_calendar';`
2. Reload integrations page
3. Verify card shows "Token expired" (red) badge
4. Verify action button is "Reconnect" (not Sync)
5. Restore test data if needed

- [ ] **Step 5: Manual smoke test — context in chat**

1. Ensure at least one calendar event exists in `source_items` with `item_at` within the next 7 days
2. Open chat (`/dashboard/chat`)
3. Ask: "What's on my calendar this week?"
4. Verify response references actual event titles from `source_items`

- [ ] **Step 6: Final commit (if any tweaks needed)**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion
git add -p  # stage only intended changes
git commit -m "feat: integration pipeline — token auto-refresh, calendar/gmail sync, context in chat"
```
