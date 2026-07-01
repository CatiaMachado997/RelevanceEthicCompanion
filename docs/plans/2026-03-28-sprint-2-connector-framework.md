# Sprint 2: Connector Framework + End-to-End Integrations

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor data ingestion into an interface-based connector framework, wire all three sources (Calendar, Gmail, Slack) to write normalized `source_items`, and upgrade the integrations UI to show item counts and sync health.

**Architecture:** Introduce `BaseConnector` abstract class in `backend/services/connectors/`. Refactor the three existing sync classes to implement it. Each connector writes to both the source-specific table AND the normalized `source_items` table. `DataIngestionService` becomes a thin orchestrator that delegates to connectors and tracks errors. New `/api/data-sources/stats` endpoint surfaces counts. Frontend integrations page shows counts + error state.

**Tech Stack:** FastAPI · Python 3.11 · psycopg3 (dict_row) · google-api-python-client · httpx · Next.js 15 · TypeScript

---

## File Map

### New files
- `backend/services/connectors/__init__.py` — connector factory (`get_connector(source_type, ...) -> BaseConnector`)
- `backend/services/connectors/base.py` — `BaseConnector` ABC with normalize_to_source_item()
- `backend/services/connectors/google_calendar.py` — wraps existing `GoogleCalendarSync`, implements `BaseConnector`
- `backend/services/connectors/gmail.py` — wraps existing `GmailSync`, implements `BaseConnector`
- `backend/services/connectors/slack.py` — wraps existing `SlackSync`, implements `BaseConnector`
- `backend/database/migration_sprint2.sql` — add `sync_error_message` + `sync_error_count` to `data_sources`
- `tests/test_connectors.py` — unit tests for BaseConnector + all three connectors

### Modified files
- `backend/services/data_ingestion.py` — use connector factory, write to `source_items`, track errors, add `get_source_stats()`
- `backend/routes/data_sources.py` — add `GET /api/data-sources/stats` endpoint
- `frontend/app/dashboard/integrations/page.tsx` — show item counts + error state per card
- `frontend/lib/api.ts` — add `dataSourcesApi.stats()`

### Untouched files (read-only reference)
- `backend/services/google_calendar_sync.py` — existing, used by new connector wrapper
- `backend/services/gmail_sync.py` — existing, used by new connector wrapper
- `backend/services/slack_sync.py` — existing, used by new connector wrapper
- `backend/database/schema_local.sql` — `data_sources` table already defined here

---

## Task 1: Database Migration

**Files:**
- Create: `backend/database/migration_sprint2.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Sprint 2: Add sync error tracking to data_sources
-- Run against local Docker Postgres: psql -h localhost -U postgres -d ethic_companion -f migration_sprint2.sql

ALTER TABLE data_sources
    ADD COLUMN IF NOT EXISTS sync_error_message TEXT,
    ADD COLUMN IF NOT EXISTS sync_error_count INTEGER NOT NULL DEFAULT 0;
```

- [ ] **Step 2: Apply to local DB**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion
psql -h localhost -U postgres -d ethic_companion -f backend/database/migration_sprint2.sql
```

Expected: `ALTER TABLE` (no errors).

- [ ] **Step 3: Verify columns exist**

```bash
psql -h localhost -U postgres -d ethic_companion -c "\d data_sources"
```

Expected: `sync_error_message` and `sync_error_count` columns appear.

- [ ] **Step 4: Commit**

```bash
git add backend/database/migration_sprint2.sql
git commit -m "feat: add sync error tracking columns to data_sources"
```

---

## Task 2: BaseConnector Abstract Class

**Files:**
- Create: `backend/services/connectors/__init__.py`
- Create: `backend/services/connectors/base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_connectors.py
import pytest
from unittest.mock import MagicMock
from services.connectors.base import BaseConnector, SourceItem


class ConcreteConnector(BaseConnector):
    """Minimal concrete subclass for testing the ABC."""

    source_type = "test_source"

    def get_authorization_url(self, user_id: str, state: str = None) -> str:
        return "https://example.com/auth"

    def exchange_code_for_tokens(self, code: str):
        return {"access_token": "tok", "refresh_token": "ref", "expires_at": None}

    async def fetch_raw_items(self, access_token: str, refresh_token: str = None):
        return [{"id": "1", "title": "Test Item", "content": "body"}]

    def normalize_to_source_item(self, raw: dict, user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="test",
            external_id=raw["id"],
            title=raw["title"],
            body=raw.get("content"),
        )


def test_base_connector_interface():
    conn = ConcreteConnector()
    assert conn.source_type == "test_source"
    url = conn.get_authorization_url("user-123")
    assert url.startswith("https://")


def test_normalize_to_source_item():
    conn = ConcreteConnector()
    item = conn.normalize_to_source_item({"id": "x1", "title": "Hello", "content": "World"}, "user-1")
    assert item.external_id == "x1"
    assert item.title == "Hello"
    assert item.source_type == "test_source"


def test_source_item_has_required_fields():
    item = SourceItem(
        user_id="u",
        source_type="google_calendar",
        source_item_type="event",
        external_id="evt_123",
        title="Meeting",
    )
    assert item.embedding_status == "pending"
    assert item.sensitivity == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py -v
```

Expected: `ModuleNotFoundError: No module named 'services.connectors'`

- [ ] **Step 3: Write `base.py`**

```python
# backend/services/connectors/base.py
"""
BaseConnector — abstract interface for all data source connectors.

Each connector is responsible for:
  1. Generating the OAuth authorization URL
  2. Exchanging an auth code for tokens
  3. Fetching raw items from the external API
  4. Normalizing each raw item into a SourceItem dataclass

DataIngestionService drives the storage layer.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceItem:
    """Normalized representation of an item from any external source."""
    user_id: str
    source_type: str               # e.g. 'google_calendar'
    source_item_type: str          # e.g. 'event', 'email', 'message'
    external_id: str               # original ID in the external system
    title: str
    body: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    item_at: Optional[str] = None  # ISO-8601 timestamp of when item occurred
    embedding_status: str = "pending"
    sensitivity: int = 0           # 0=normal, 1=sensitive, 2=private


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    source_type: str  # must be set on subclass

    @abstractmethod
    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        """Return the OAuth authorization URL for this source."""
        ...

    @abstractmethod
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange an auth code for tokens. Return dict with access_token, refresh_token, expires_at."""
        ...

    @abstractmethod
    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw items from the external API using the provided tokens."""
        ...

    @abstractmethod
    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        """Convert a raw item dict into a normalized SourceItem."""
        ...
```

- [ ] **Step 4: Write `__init__.py` (connector factory)**

```python
# backend/services/connectors/__init__.py
"""Connector factory — returns the right BaseConnector for a source_type."""
from typing import Optional
from services.connectors.base import BaseConnector
from config import settings


def get_connector(source_type: str) -> BaseConnector:
    """
    Return the connector instance for the given source_type.

    Raises ValueError for unsupported source types.
    """
    if source_type == "google_calendar":
        from services.connectors.google_calendar import GoogleCalendarConnector
        return GoogleCalendarConnector(redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI)
    elif source_type == "gmail":
        from services.connectors.gmail import GmailConnector
        return GmailConnector(redirect_uri=settings.GMAIL_OAUTH_REDIRECT_URI)
    elif source_type == "slack":
        from services.connectors.slack import SlackConnector
        return SlackConnector()
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_base_connector_interface ../tests/test_connectors.py::test_normalize_to_source_item ../tests/test_connectors.py::test_source_item_has_required_fields -v
```

Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/services/connectors/ tests/test_connectors.py
git commit -m "feat: add BaseConnector ABC and connector factory"
```

---

## Task 3: GoogleCalendarConnector

**Files:**
- Create: `backend/services/connectors/google_calendar.py`
- Modify: `tests/test_connectors.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_connectors.py`:

```python
from unittest.mock import patch, MagicMock
from services.connectors.google_calendar import GoogleCalendarConnector


def test_google_calendar_connector_source_type():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    assert conn.source_type == "google_calendar"


def test_google_calendar_normalize_event():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "evt_abc",
        "summary": "Standup",
        "description": "Daily sync",
        "start": {"dateTime": "2026-03-28T09:00:00Z"},
        "end": {"dateTime": "2026-03-28T09:30:00Z"},
        "location": "Zoom",
        "attendees": [{"email": "a@b.com"}],
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "evt_abc"
    assert item.title == "Standup"
    assert item.source_item_type == "event"
    assert item.source_type == "google_calendar"
    assert item.item_at == "2026-03-28T09:00:00Z"
    assert "location" in item.metadata


def test_google_calendar_normalize_all_day_event():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "evt_allday",
        "summary": "Holiday",
        "start": {"date": "2026-03-28"},
        "end": {"date": "2026-03-29"},
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "evt_allday"
    assert item.item_at == "2026-03-28"  # date string for all-day events
```

- [ ] **Step 2: Run test to verify they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_google_calendar_connector_source_type -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Write the connector**

```python
# backend/services/connectors/google_calendar.py
"""Google Calendar connector — wraps GoogleCalendarSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.google_calendar_sync import GoogleCalendarSync


class GoogleCalendarConnector(BaseConnector):
    source_type = "google_calendar"

    def __init__(self, redirect_uri: str):
        self._sync = GoogleCalendarSync(redirect_uri=redirect_uri)

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._sync.fetch_events(
            access_token=access_token,
            refresh_token=refresh_token or "",
        )

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        start = raw.get("start", {})
        item_at = start.get("dateTime") or start.get("date")

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="event",
            external_id=raw["id"],
            title=raw.get("summary", "(no title)"),
            body=raw.get("description"),
            item_at=item_at,
            metadata={
                "location": raw.get("location"),
                "end": raw.get("end", {}),
                "attendee_count": len(raw.get("attendees", [])),
                "organizer": raw.get("organizer", {}).get("email"),
            },
        )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py -k "google_calendar" -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/services/connectors/google_calendar.py tests/test_connectors.py
git commit -m "feat: add GoogleCalendarConnector implementing BaseConnector"
```

---

## Task 4: GmailConnector

**Files:**
- Create: `backend/services/connectors/gmail.py`
- Modify: `tests/test_connectors.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_connectors.py`:

```python
from services.connectors.gmail import GmailConnector


def test_gmail_connector_source_type():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    assert conn.source_type == "gmail"


def test_gmail_normalize_message():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "msg_abc",
        "subject": "Sprint review notes",
        "from": "alice@example.com",
        "date": "Fri, 28 Mar 2026 10:00:00 +0000",
        "snippet": "Here are the notes from today...",
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "msg_abc"
    assert item.title == "Sprint review notes"
    assert item.source_item_type == "email"
    assert item.source_type == "gmail"
    assert "alice@example.com" in item.body
    assert item.metadata["from"] == "alice@example.com"


def test_gmail_normalize_no_subject():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    raw = {"id": "msg_1", "subject": "", "from": "b@c.com", "date": "", "snippet": "hi"}
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.title == "(no subject)"
```

- [ ] **Step 2: Run test to verify they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_gmail_connector_source_type -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write the connector**

```python
# backend/services/connectors/gmail.py
"""Gmail connector — wraps GmailSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.gmail_sync import GmailSync


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
            item_at=raw.get("date"),
            metadata={
                "from": sender,
                "date": raw.get("date"),
            },
        )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py -k "gmail" -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/services/connectors/gmail.py tests/test_connectors.py
git commit -m "feat: add GmailConnector implementing BaseConnector"
```

---

## Task 5: SlackConnector

**Files:**
- Create: `backend/services/connectors/slack.py`
- Modify: `tests/test_connectors.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_connectors.py`:

```python
from services.connectors.slack import SlackConnector


def test_slack_connector_source_type():
    conn = SlackConnector()
    assert conn.source_type == "slack"


def test_slack_normalize_message():
    conn = SlackConnector()
    raw = {
        "channel": "general",
        "text": "Deployment done ✓",
        "ts": "1743160800.000000",
        "user": "U01ABCDEF",
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "general_1743160800.000000"
    assert item.title == "#general"
    assert item.body == "Deployment done ✓"
    assert item.source_item_type == "message"
    assert item.source_type == "slack"
    assert item.metadata["channel"] == "general"
    assert item.metadata["ts"] == "1743160800.000000"


def test_slack_normalize_empty_text():
    conn = SlackConnector()
    raw = {"channel": "dev", "text": "", "ts": "111.0", "user": "U123"}
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.title == "#dev"
    assert item.body == ""
```

- [ ] **Step 2: Run test to verify they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_slack_connector_source_type -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write the connector**

```python
# backend/services/connectors/slack.py
"""Slack connector — wraps SlackSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.slack_sync import SlackSync


class SlackConnector(BaseConnector):
    source_type = "slack"

    def __init__(self):
        self._sync = SlackSync()

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,  # Slack tokens don't refresh
    ) -> List[Dict[str, Any]]:
        return self._sync.fetch_messages(access_token=access_token)

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        channel = raw.get("channel", "")
        ts = raw.get("ts", "")

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="message",
            external_id=f"{channel}_{ts}",
            title=f"#{channel}",
            body=raw.get("text", ""),
            metadata={
                "channel": channel,
                "ts": ts,
                "user": raw.get("user"),
            },
        )
```

- [ ] **Step 4: Run all connector tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py -v
```

Expected: All tests pass (≥ 12 PASSED).

- [ ] **Step 5: Commit**

```bash
git add backend/services/connectors/slack.py tests/test_connectors.py
git commit -m "feat: add SlackConnector implementing BaseConnector"
```

---

## Task 6: Refactor DataIngestionService

Replace the monolithic per-source sync methods with connector-based dispatch.
Add `source_items` writes, error tracking, and `get_source_stats()`.

**Files:**
- Modify: `backend/services/data_ingestion.py`

This is a full replacement of the internal sync logic. The public interface (`initiate_oauth`, `handle_oauth_callback`, `sync_data_source`, `get_connected_sources`, `disconnect_source`) stays identical so routes need no changes.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_connectors.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.data_ingestion import DataIngestionService
from services.connectors.base import SourceItem


@pytest.mark.asyncio
async def test_sync_writes_to_source_items(tmp_path):
    """Sync should write normalized items to source_items table."""
    mock_cm = MagicMock()
    mock_cm.weaviate = None  # Weaviate offline — should not block sync

    service = DataIngestionService(mock_cm)

    # Mock the connector
    fake_item = SourceItem(
        user_id="user-1",
        source_type="google_calendar",
        source_item_type="event",
        external_id="evt_1",
        title="Standup",
    )
    mock_connector = MagicMock()
    mock_connector.fetch_raw_items = AsyncMock(return_value=[{"id": "evt_1", "summary": "Standup", "start": {}, "end": {}}])
    mock_connector.normalize_to_source_item.return_value = fake_item

    written_items = []

    async def fake_store_source_item(item):
        written_items.append(item)

    with patch("services.data_ingestion.get_connector", return_value=mock_connector), \
         patch.object(service, "_get_data_source_tokens", new_callable=AsyncMock,
                      return_value={"access_token": "tok", "refresh_token": "ref", "expires_at": None}), \
         patch.object(service, "_store_normalized_item", side_effect=fake_store_source_item), \
         patch.object(service, "_update_last_sync", new_callable=AsyncMock), \
         patch.object(service, "_clear_sync_error", new_callable=AsyncMock):
        result = await service.sync_data_source("user-1", "google_calendar")

    assert result["success"] is True
    assert result["items_synced"] == 1
    assert len(written_items) == 1
    assert written_items[0].external_id == "evt_1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_sync_writes_to_source_items -v
```

Expected: FAIL — `_store_normalized_item` and `_clear_sync_error` don't exist yet.

- [ ] **Step 3: Rewrite `data_ingestion.py`**

Replace the entire file content with the following:

```python
"""
Data Ingestion Service (Sprint 2)

Orchestrates data ingestion from external sources using the connector framework.
Each source maps to a BaseConnector; this service drives OAuth, sync, M1 storage,
M2 embedding, and error tracking.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.connectors import get_connector
from services.connectors.base import SourceItem
from services.context_manager import ContextManager
from models.context import SemanticMemoryEntry
from utils.db import get_db_connection
from config import settings

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = ["google_calendar", "gmail", "slack"]


class DataIngestionService:
    """
    Thin orchestrator: delegates auth + fetch + normalize to connectors;
    drives storage in M1 (source_items + source-specific tables) and M2.
    """

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        logger.info("✅ DataIngestionService initialized")

    # ── OAuth ──────────────────────────────────────────────────────────────

    async def initiate_oauth(
        self, user_id: str, source_type: str, oauth_state: Optional[str] = None
    ) -> str:
        connector = get_connector(source_type)
        url = connector.get_authorization_url(user_id, state=oauth_state)
        logger.info(f"✅ OAuth URL generated for {source_type}, user {user_id}")
        return url

    async def handle_oauth_callback(
        self, source_type: str, authorization_code: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            connector = get_connector(source_type)
            tokens = connector.exchange_code_for_tokens(authorization_code)

            await self._store_data_source(
                user_id=user_id,
                source_type=source_type,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_at=tokens.get("expires_at"),
            )
            logger.info(f"✅ OAuth completed for {source_type}, user {user_id}")

            try:
                await self.sync_data_source(user_id, source_type)
            except Exception as sync_err:
                logger.warning(
                    f"⚠️ Initial sync failed for {source_type} (tokens stored): {sync_err}"
                )

            return {"success": True, "message": f"{source_type} connected", "source_type": source_type}
        except Exception as e:
            logger.error(f"❌ OAuth callback failed: {e}")
            return {"success": False, "message": str(e), "source_type": source_type}

    # ── Sync ───────────────────────────────────────────────────────────────

    async def sync_data_source(self, user_id: str, source_type: str) -> Dict[str, Any]:
        logger.info(f"🔄 Starting sync: {source_type} for user {user_id}")

        tokens = await self._get_data_source_tokens(user_id, source_type)
        if not tokens:
            return {"success": False, "message": f"{source_type} not connected", "items_synced": 0}

        try:
            connector = get_connector(source_type)
            raw_items = await connector.fetch_raw_items(
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
            )

            items_synced = 0
            for raw in raw_items:
                try:
                    source_item = connector.normalize_to_source_item(raw, user_id)
                    await self._store_normalized_item(source_item)
                    await self._maybe_embed(source_item, user_id)
                    items_synced += 1
                except Exception as item_err:
                    logger.warning(f"⚠️ Failed to process item from {source_type}: {item_err}")

            await self._update_last_sync(user_id, source_type)
            await self._clear_sync_error(user_id, source_type)

            logger.info(f"✅ Sync complete: {items_synced} items from {source_type}")
            return {
                "success": True,
                "message": f"Synced {items_synced} items from {source_type}",
                "items_synced": items_synced,
                "source_type": source_type,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Sync failed for {source_type}: {error_msg}", exc_info=True)
            await self._record_sync_error(user_id, source_type, error_msg)
            return {
                "success": False,
                "message": f"Sync failed: {error_msg}",
                "items_synced": 0,
                "source_type": source_type,
            }

    # ── Storage helpers ────────────────────────────────────────────────────

    async def _store_normalized_item(self, item: SourceItem):
        """Upsert a normalized item into source_items (M1)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO source_items
                        (user_id, source_type, source_item_type, external_id,
                         title, body, metadata, item_at, embedding_status, sensitivity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, source_type, external_id)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        body = EXCLUDED.body,
                        metadata = EXCLUDED.metadata,
                        synced_at = NOW()
                    """,
                    (
                        item.user_id,
                        item.source_type,
                        item.source_item_type,
                        item.external_id,
                        item.title,
                        item.body,
                        json.dumps(item.metadata),
                        item.item_at,
                        item.embedding_status,
                        item.sensitivity,
                    ),
                )
            conn.commit()

    async def _maybe_embed(self, item: SourceItem, user_id: str):
        """Store in M2 (Weaviate) if available — best-effort."""
        if not (self.context_manager.weaviate and self.context_manager.embedding_service):
            return
        try:
            content = f"{item.title}. {item.body or ''}"
            memory_entry = SemanticMemoryEntry(
                user_id=user_id,
                content=content,
                source=item.source_type,
                timestamp=datetime.now(timezone.utc),
                metadata={"external_id": item.external_id, **item.metadata},
            )
            await self.context_manager.store_semantic_memory(memory_entry)
        except Exception as e:
            logger.warning(f"⚠️ M2 embed failed for {item.external_id}: {e}")

    async def _store_data_source(
        self,
        user_id: str,
        source_type: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[str],
    ):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM data_sources WHERE user_id = %s AND source_type = %s",
                    (user_id, source_type),
                )
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        """
                        UPDATE data_sources
                        SET oauth_token_encrypted = %s,
                            oauth_refresh_token_encrypted = %s,
                            token_expires_at = %s,
                            enabled = TRUE,
                            last_sync = NULL,
                            sync_error_message = NULL,
                            sync_error_count = 0
                        WHERE user_id = %s AND source_type = %s
                        """,
                        (access_token, refresh_token, expires_at, user_id, source_type),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO data_sources
                            (user_id, source_type, oauth_token_encrypted,
                             oauth_refresh_token_encrypted, token_expires_at, enabled)
                        VALUES (%s, %s, %s, %s, %s, TRUE)
                        """,
                        (user_id, source_type, access_token, refresh_token, expires_at),
                    )
            conn.commit()

    async def _get_data_source_tokens(
        self, user_id: str, source_type: str
    ) -> Optional[Dict[str, str]]:
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
                    return None
                return {
                    "access_token": row["oauth_token_encrypted"],
                    "refresh_token": row["oauth_refresh_token_encrypted"],
                    "expires_at": row["token_expires_at"],
                }

    async def _update_last_sync(self, user_id: str, source_type: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE data_sources SET last_sync = %s WHERE user_id = %s AND source_type = %s",
                    (datetime.now(timezone.utc), user_id, source_type),
                )
            conn.commit()

    async def _record_sync_error(self, user_id: str, source_type: str, message: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET sync_error_message = %s,
                        sync_error_count = COALESCE(sync_error_count, 0) + 1
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (message[:500], user_id, source_type),
                )
            conn.commit()

    async def _clear_sync_error(self, user_id: str, source_type: str):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE data_sources
                    SET sync_error_message = NULL, sync_error_count = 0
                    WHERE user_id = %s AND source_type = %s
                    """,
                    (user_id, source_type),
                )
            conn.commit()

    # ── Query ──────────────────────────────────────────────────────────────

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
                sources = []
                for row in cur.fetchall():
                    sources.append(
                        {
                            "source_type": row["source_type"],
                            "enabled": row["enabled"],
                            "last_sync": row["last_sync"].isoformat() if row["last_sync"] else None,
                            "token_expires_at": (
                                row["token_expires_at"].isoformat()
                                if row["token_expires_at"]
                                else None
                            ),
                            "status": "connected" if row["enabled"] else "disconnected",
                            "item_count": row["item_count"],
                            "sync_error": row["sync_error_message"],
                            "sync_error_count": row["sync_error_count"],
                        }
                    )
                return sources

    async def get_source_stats(self, user_id: str) -> Dict[str, Any]:
        """Return item counts per source for the stats endpoint."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_type, COUNT(*) AS item_count
                    FROM source_items
                    WHERE user_id = %s
                    GROUP BY source_type
                    """,
                    (user_id,),
                )
                counts = {row["source_type"]: row["item_count"] for row in cur.fetchall()}
        return {
            "google_calendar": counts.get("google_calendar", 0),
            "gmail": counts.get("gmail", 0),
            "slack": counts.get("slack", 0),
            "total": sum(counts.values()),
        }

    async def disconnect_source(self, user_id: str, source_type: str) -> bool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE data_sources SET enabled = FALSE WHERE user_id = %s AND source_type = %s",
                        (user_id, source_type),
                    )
                conn.commit()
            logger.info(f"✅ Disconnected {source_type} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to disconnect {source_type}: {e}")
            return False
```

- [ ] **Step 4: Run the test**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_connectors.py::test_sync_writes_to_source_items -v
```

Expected: PASSED.

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest -x -q
```

Expected: All existing tests pass (≥ 119 from Sprint 1), new connector tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/services/data_ingestion.py
git commit -m "feat: refactor DataIngestionService to use connector framework, write to source_items"
```

---

## Task 7: Backend Stats Endpoint

Add `GET /api/data-sources/stats` so the frontend can poll item counts.

**Files:**
- Modify: `backend/routes/data_sources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_sources_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_stats_endpoint_structure(client):
    """Stats endpoint should return counts for all sources."""
    mock_stats = {
        "google_calendar": 15,
        "gmail": 42,
        "slack": 8,
        "total": 65,
    }
    with patch("routes.data_sources.get_data_ingestion") as mock_di_dep:
        mock_service = AsyncMock()
        mock_service.get_source_stats = AsyncMock(return_value=mock_stats)
        mock_di_dep.return_value = mock_service

        with patch("routes.data_sources.get_current_read_user_id", return_value="user-1"):
            response = client.get("/api/data-sources/stats")

    assert response.status_code == 200
    data = response.json()
    assert "google_calendar" in data
    assert data["total"] == 65
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_data_sources_routes.py::test_stats_endpoint_structure -v
```

Expected: FAIL — endpoint doesn't exist.

- [ ] **Step 3: Add the endpoint to `data_sources.py`**

Add this after the existing `get_connected_sources` route (around line 210):

```python
@router.get("/stats")
async def get_source_stats(
    user_id: str = Depends(get_current_read_user_id),
    ingestion: DataIngestionService = Depends(get_data_ingestion),
) -> Dict[str, Any]:
    """
    Return item counts per connected source for the current user.

    Response:
        {
            "google_calendar": 15,
            "gmail": 42,
            "slack": 8,
            "total": 65
        }
    """
    try:
        return await ingestion.get_source_stats(user_id)
    except Exception as e:
        logger.error(f"Failed to get source stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")
```

- [ ] **Step 4: Run the test**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest ../tests/test_data_sources_routes.py -v
```

Expected: PASSED.

- [ ] **Step 5: Verify endpoint appears in Swagger**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend && python main.py &
sleep 2
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print([p for p in d['paths'] if 'stats' in p])"
kill %1
```

Expected: `['/api/data-sources/stats']`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/data_sources.py
git commit -m "feat: add GET /api/data-sources/stats endpoint for item counts"
```

---

## Task 8: Frontend Integrations UI — Item Counts + Error State

Show item counts and sync error indicators on each integration card.

**Files:**
- Modify: `frontend/lib/api.ts` (add `dataSourcesApi.stats()`)
- Modify: `frontend/app/dashboard/integrations/page.tsx`

- [ ] **Step 1: Check current `api.ts` for dataSourcesApi**

```bash
grep -n "dataSourcesApi\|data-sources" /Users/catiamachado/RelevanceEthicCompanion/frontend/lib/api.ts | head -20
```

Note the existing structure so the addition matches the pattern.

- [ ] **Step 2: Add `stats()` to `dataSourcesApi`**

Open `frontend/lib/api.ts`. Find the `dataSourcesApi` object and add `stats`:

```typescript
stats: async (): Promise<{ google_calendar: number; gmail: number; slack: number; total: number }> => {
  const r = await apiRequest('/api/data-sources/stats')
  return r
},
```

- [ ] **Step 3: Update the `ConnectedSource` interface in `integrations/page.tsx`**

Find and replace the interface:

```typescript
// BEFORE:
interface ConnectedSource {
  source_type: string
  last_sync?: string | null
  enabled: boolean
  status?: string
}

// AFTER:
interface ConnectedSource {
  source_type: string
  last_sync?: string | null
  enabled: boolean
  status?: string
  item_count?: number
  sync_error?: string | null
  sync_error_count?: number
}
```

- [ ] **Step 4: Add `stats` state + fetch in `IntegrationsContent`**

Add state and fetch logic after the existing state declarations:

```typescript
const [stats, setStats] = useState<Record<string, number>>({})

const loadStats = async () => {
  try {
    const s = await dataSourcesApi.stats()
    setStats(s)
  } catch {
    // stats are non-critical — fail silently
  }
}
```

Add `loadStats()` call inside `loadConnected()` after `setConnected(...)`:

```typescript
const loadConnected = async () => {
  try {
    const r = await dataSourcesApi.list()
    setConnected((r.sources ?? []) as ConnectedSource[])
    await loadStats()   // ← add this line
  } catch (e) {
    console.error(e)
  } finally {
    setLoading(false)
  }
}
```

- [ ] **Step 5: Show item count and error in the card**

In the card's info section, after the `<p>` showing last sync / description, add:

```typescript
{/* Item count badge — only when connected and count > 0 */}
{isConn && (stats[type] ?? 0) > 0 && (
  <span className="inline-flex items-center gap-1 mt-1 text-[10px]" style={{ color: '#6b6b6b' }}>
    <span className="font-medium">{(stats[type] ?? 0).toLocaleString()}</span> items synced
  </span>
)}

{/* Sync error indicator */}
{isConn && connected.find(s => s.source_type === type)?.sync_error && (
  <p className="mt-1 text-[10px]" style={{ color: '#B04A3A' }}>
    ⚠ Last sync failed — try syncing again
  </p>
)}
```

- [ ] **Step 6: Manual smoke test**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npm run dev
```

Open http://localhost:3000/dashboard/integrations. Verify:
- Connected sources show "X items synced" badge
- Disconnected sources show no badge
- Page loads without errors in browser console

- [ ] **Step 7: Run frontend type check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api.ts frontend/app/dashboard/integrations/page.tsx
git commit -m "feat: show item counts and sync error state in integrations UI"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
pytest -v --tb=short
```

Expected: ≥ 130 tests passing, 0 failures.

- [ ] **End-to-end smoke test**

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Sign in, go to Integrations
4. Click "Connect" on Google Calendar → complete OAuth → should show "Connected" + item count after sync
5. Click sync button → watch loading spinner → item count updates
6. Go to Chat → ask "What meetings do I have this week?" → should see calendar items cited
7. Run: `curl http://localhost:8000/api/data-sources/stats -H "Authorization: Bearer <token>"` — should return JSON with counts

- [ ] **Commit final tag**

```bash
git tag sprint/2-connector-framework
git push origin master --tags
```

---

## Critical Files Reference

| File | Change type | Why |
|------|-------------|-----|
| `backend/database/migration_sprint2.sql` | New | Add error tracking columns |
| `backend/services/connectors/base.py` | New | BaseConnector ABC + SourceItem dataclass |
| `backend/services/connectors/__init__.py` | New | Connector factory |
| `backend/services/connectors/google_calendar.py` | New | Calendar connector |
| `backend/services/connectors/gmail.py` | New | Gmail connector |
| `backend/services/connectors/slack.py` | New | Slack connector |
| `backend/services/data_ingestion.py` | Rewrite | Use connector factory, write to source_items, track errors |
| `backend/routes/data_sources.py` | Additive | Add /stats endpoint |
| `frontend/lib/api.ts` | Additive | Add stats() |
| `frontend/app/dashboard/integrations/page.tsx` | Additive | Show counts + errors |
