# Sprint B — Connector Framework + Gmail/Slack End-to-End

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Gmail and Slack first-class data sources whose content is searchable through the same RAG path Sprint A built — so every grounded chat answer can cite an email, a Slack thread, or an uploaded document with the same UI and the same `search_documents` tool.

**Architecture:** Existing scaffolding (`BaseConnector`, `GmailConnector`, `SlackConnector`, `DataIngestionService`, `data_sources` + `source_items` tables, calendar-only `Scheduler`) is reused. We add three things:
1. **Unified retrieval substrate** — connector items get chunked + embedded into the **same** Weaviate `DocumentMemory` collection that `search_documents` already queries (with a `source_type` property so the agent can filter or attribute citations correctly). This is the lever that "every connector that feeds chunks gets grounded answers for free."
2. **Lifecycle completeness** — Gmail + Slack added to the periodic scheduler, disconnect cleanup wipes tokens + items + vectors, and a manual backfill endpoint pulls historical content on demand.
3. **Operator visibility** — `/dashboard/settings/integrations` surfaces last-sync time, item count, error state, and reconnect/disconnect buttons.

**Tech Stack:** Python 3.13 + FastAPI + APScheduler + httpx + Weaviate v4 client + Gemini embeddings + psycopg / pytest-asyncio on the backend; Next.js App Router + TypeScript + Tailwind + Radix UI on the frontend. No new infra.

---

## Why this sprint, in one paragraph

Sprint A made the agent cite *uploaded documents*. Connectors already exist (Gmail/Slack adapters, OAuth flow, `source_items` table) but their content never reaches `DocumentMemory` — the only collection `search_documents` queries — so a grounded answer can never cite an email or a Slack message. This sprint closes that gap. After this sprint, "what did the team decide about Q2 roadmap?" returns Slack threads + emails as ranked citation cards in the same UI as PDF chunks.

---

## File Structure

**New files:**
- `backend/services/connector_indexer.py` — chunks `SourceItem` body, embeds each chunk into `DocumentMemory`, marks `source_items.embedding_status='indexed'`. Single responsibility: connector → `DocumentMemory`.
- `backend/migrations/010_document_memory_source_type.sql` — schema migration adding `source_type` (and a few attribution fields) to the `DocumentMemory` Weaviate collection schema; also a `connector_backfill_jobs` table for tracking long-running backfills.
- `backend/routes/connectors.py` — REST surface for backfill kickoff + connector summary (`GET /api/connectors`, `POST /api/connectors/:source/backfill`, `DELETE /api/connectors/:source`). Replaces what's currently scattered in `data_sources.py` for these new flows; `data_sources.py` keeps the OAuth callback path.
- `backend/tests/test_connector_indexer.py` — 4 tests for the chunker/embedder.
- `backend/tests/test_connector_lifecycle.py` — disconnect cleanup + backfill tests.
- `backend/tests/test_scheduler_gmail_slack.py` — verify Gmail and Slack jobs are registered and call into ingestion.
- `frontend/app/dashboard/settings/integrations/page.tsx` — operator UI: connect/disconnect/backfill/last-sync.
- `frontend/components/settings/IntegrationCard.tsx` — one card per connector.

**Modified files:**
- `backend/services/data_ingestion.py` — replace `_maybe_embed` (single-vector store) with a call to `ConnectorIndexer.index(item)` so connector items land chunked in `DocumentMemory`. Add a `disconnect_data_source(user_id, source_type)` method.
- `backend/services/scheduler.py` — register `_sync_all_gmail` and `_sync_all_slack` jobs alongside the existing calendar job (every 30 minutes for Gmail, every 5 minutes for Slack — see Task 5).
- `backend/services/connectors/gmail.py` — extend `fetch_raw_items` to accept an optional `since: datetime` for backfill / incremental syncs.
- `backend/services/connectors/slack.py` — same `since` extension.
- `backend/services/rag_retrieval.py` — extend the formatted result row to surface `source_type` so the frontend can show a "Gmail" / "Slack" badge instead of a generic file icon.
- `backend/services/langchain_tools.py` — `search_documents` tool description teaches the planner that the same tool now searches emails and Slack messages too; nothing else changes (the tool is still `search_documents`).
- `backend/main.py` — register the new `/api/connectors` router.
- `frontend/lib/api.ts` — add `DocumentSource.source_type` and `connectors` API namespace.
- `frontend/components/chat/SourceCards.tsx` — show a small icon based on `source_type` ("file-text" / "mail" / "message-circle").

**Deliberately out of scope** (deferred to later sprints):
- New connectors (Notion, Drive, GitHub) — Sprint C/D.
- Real-time streaming via Slack Events API or Gmail push — current polling cadence is fine until volume forces it.
- Per-channel / per-label opt-in granularity in the UI — connector-level on/off is enough for this sprint.

---

## Task 1: Migration — `source_type` on `DocumentMemory` + `connector_backfill_jobs` table

**Files:**
- Create: `backend/migrations/010_document_memory_source_type.sql`
- Modify: `backend/utils/weaviate_client.py:55-75` (schema bootstrap loop)
- Test: `backend/tests/test_schema.py` (existing — extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_schema.py`:

```python
def test_connector_backfill_jobs_table_exists():
    from utils.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'connector_backfill_jobs'
                ORDER BY column_name
            """)
            cols = {r["column_name"]: r["data_type"] for r in cur.fetchall()}
    assert "user_id" in cols
    assert "source_type" in cols
    assert cols["status"] == "text"
    assert cols["items_processed"] == "integer"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python3 -m pytest tests/test_schema.py::test_connector_backfill_jobs_table_exists -v
```

Expected: FAIL — table does not exist.

- [ ] **Step 3: Write the SQL migration**

Create `backend/migrations/010_document_memory_source_type.sql`:

```sql
-- Sprint B: connector backfill tracking + DocumentMemory source attribution.
-- The Weaviate property addition is performed at runtime by weaviate_client.py;
-- this migration only handles Postgres state.

CREATE TABLE IF NOT EXISTS public.connector_backfill_jobs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    source_type     TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',  -- pending|running|complete|failed
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    items_processed INTEGER     NOT NULL DEFAULT 0,
    error_message   TEXT,
    UNIQUE (user_id, source_type, started_at)
);

CREATE INDEX IF NOT EXISTS idx_backfill_user_source
    ON public.connector_backfill_jobs (user_id, source_type, started_at DESC);
```

- [ ] **Step 4: Apply the migration**

```bash
cd backend && psql "$DATABASE_URL" -f migrations/010_document_memory_source_type.sql
```

Expected: `CREATE TABLE` and `CREATE INDEX` echoed.

- [ ] **Step 5: Add `source_type` to the Weaviate `DocumentMemory` schema**

Open `backend/utils/weaviate_client.py`. Find the schema bootstrap section (~lines 55-75 — the `for schema in schemas` loop). Locate the `DocumentMemory` schema dict (probably in `schemas/document_memory.json` or inline). Add a new property:

```python
{"name": "source_type", "dataType": ["text"]}
```

Below `chunk_count`. Then add an idempotent runtime fix-up so existing deployments backfill the property without a re-create:

```python
def ensure_document_memory_source_type(self):
    """Add `source_type` to DocumentMemory if missing — idempotent."""
    coll = self.client.collections.get("DocumentMemory")
    config = coll.config.get()
    existing = {p.name for p in config.properties}
    if "source_type" not in existing:
        from weaviate.classes.config import Property, DataType
        coll.config.add_property(Property(name="source_type", data_type=DataType.TEXT))
```

Call `ensure_document_memory_source_type()` from the bootstrap path immediately after the `create_from_dict` block.

- [ ] **Step 6: Run the test to verify it passes**

```bash
python3 -m pytest tests/test_schema.py::test_connector_backfill_jobs_table_exists -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/010_document_memory_source_type.sql \
        backend/utils/weaviate_client.py \
        backend/tests/test_schema.py
git commit -m "feat(connectors): add source_type to DocumentMemory + backfill jobs table"
```

---

## Task 2: `ConnectorIndexer` — chunk + embed connector items into `DocumentMemory`

**Files:**
- Create: `backend/services/connector_indexer.py`
- Test: `backend/tests/test_connector_indexer.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_connector_indexer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.connectors.base import SourceItem


USER_ID = "00000000-0000-0000-0000-000000000000"


def _item(body: str, source_type: str = "gmail", external_id: str = "msg_1") -> SourceItem:
    return SourceItem(
        user_id=USER_ID,
        source_type=source_type,
        source_item_type="email",
        external_id=external_id,
        title="Re: Q2 roadmap",
        body=body,
        item_at="2026-04-20T10:00:00+00:00",
    )


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_short_item_indexes_one_chunk(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer = ConnectorIndexer()
    n = await indexer.index(_item("Short body, fits one chunk."))

    assert n == 1
    assert weav.store_memory.call_count == 1
    args = weav.store_memory.call_args
    assert args[0][0] == "DocumentMemory"
    props = args[0][1]
    assert props["source_type"] == "gmail"
    assert props["chunk_index"] == 0
    assert props["chunk_count"] == 1


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_long_item_splits_into_multiple_chunks(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer

    weav = MagicMock()
    weav.store_memory = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    long_body = ("Sentence about the roadmap. " * 200)
    indexer = ConnectorIndexer()
    n = await indexer.index(_item(long_body))

    assert n > 1
    assert weav.store_memory.call_count == n


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
async def test_returns_zero_when_weaviate_unavailable(mock_weaviate):
    from services.connector_indexer import ConnectorIndexer
    mock_weaviate.return_value = None
    indexer = ConnectorIndexer()
    n = await indexer.index(_item("anything"))
    assert n == 0


@pytest.mark.asyncio
@patch("services.connector_indexer.get_weaviate_client")
@patch("services.connector_indexer.get_embedding_service")
async def test_empty_body_is_skipped(mock_embed, mock_weaviate):
    from services.connector_indexer import ConnectorIndexer
    weav = MagicMock()
    mock_weaviate.return_value = weav
    embed = MagicMock()
    embed.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    indexer = ConnectorIndexer()
    n = await indexer.index(_item(""))
    assert n == 0
    weav.store_memory.assert_not_called()
```

- [ ] **Step 2: Run to verify all four fail**

```bash
python3 -m pytest tests/test_connector_indexer.py -v
```

Expected: 4 failures (`ModuleNotFoundError: services.connector_indexer`).

- [ ] **Step 3: Implement `ConnectorIndexer`**

```python
# backend/services/connector_indexer.py
"""ConnectorIndexer — chunks a SourceItem's body and indexes each chunk into
the same Weaviate DocumentMemory collection that Sprint A's `search_documents`
queries. The collection's hybrid search (alpha=0.7) returns connector content
alongside uploaded documents with no further changes to the retrieval path.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from services.connectors.base import SourceItem
from services.embedding_service import get_embedding_service
from utils.weaviate_client import get_weaviate_client
from utils.db import get_db_connection

logger = logging.getLogger(__name__)

DOCUMENT_COLLECTION = "DocumentMemory"
CHUNK_SIZE = 800   # characters — matches DocumentProcessor's chunker
CHUNK_OVERLAP = 100


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Naive sliding-window chunker. Mirrors document_processor's behavior so
    connector chunks and document chunks rank against one another fairly."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return chunks


class ConnectorIndexer:
    """Connector → DocumentMemory pipeline."""

    async def index(self, item: SourceItem) -> int:
        """Chunk + embed the item. Returns number of chunks indexed (0 on skip/error)."""
        weav = get_weaviate_client()
        if weav is None:
            return 0

        body = (item.body or "").strip()
        if not body:
            return 0

        # Prepend the title so the first chunk anchors on subject/channel.
        full = f"{item.title}\n\n{body}" if item.title else body
        chunks = _chunk_text(full)
        if not chunks:
            return 0

        embed = get_embedding_service()
        now = datetime.now(timezone.utc).isoformat()

        for idx, chunk in enumerate(chunks):
            try:
                vec = await embed.generate_embedding(chunk)
                weav.store_memory(
                    DOCUMENT_COLLECTION,
                    {
                        "user_id": str(item.user_id),
                        "content": chunk,
                        "document_id": f"{item.source_type}:{item.external_id}",
                        "filename": item.title or item.external_id,
                        "chunk_index": idx,
                        "chunk_count": len(chunks),
                        "source_type": item.source_type,
                        "created_at": now,
                    },
                    vec,
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ index chunk {idx} of {item.source_type}:{item.external_id} failed: {e}"
                )
                # Continue with remaining chunks; partial coverage beats none.

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE source_items SET embedding_status = 'indexed'
                           WHERE user_id = %s AND source_type = %s AND external_id = %s""",
                        (item.user_id, item.source_type, item.external_id),
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️ embedding_status update failed: {e}")

        return len(chunks)
```

- [ ] **Step 4: Run tests to verify all pass**

```bash
python3 -m pytest tests/test_connector_indexer.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/services/connector_indexer.py backend/tests/test_connector_indexer.py
git commit -m "feat(connectors): chunk+embed connector items into DocumentMemory"
```

---

## Task 3: Wire `ConnectorIndexer` into `DataIngestionService`

**Files:**
- Modify: `backend/services/data_ingestion.py:190-207` (replace `_maybe_embed`)
- Test: `backend/tests/test_sync_source_items.py` (existing — extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_sync_source_items.py`:

```python
@pytest.mark.asyncio
@patch("services.data_ingestion.ConnectorIndexer")
async def test_sync_routes_items_through_connector_indexer(mock_indexer_cls):
    from services.data_ingestion import DataIngestionService
    from services.connectors.base import SourceItem

    mock_indexer = MagicMock()
    mock_indexer.index = AsyncMock(return_value=3)
    mock_indexer_cls.return_value = mock_indexer

    cm = MagicMock()
    svc = DataIngestionService(cm)
    item = SourceItem(
        user_id="00000000-0000-0000-0000-000000000000",
        source_type="gmail",
        source_item_type="email",
        external_id="msg_xyz",
        title="Test",
        body="A body that should be indexed.",
    )
    await svc._maybe_embed(item, item.user_id)

    mock_indexer.index.assert_awaited_once_with(item)
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_sync_source_items.py::test_sync_routes_items_through_connector_indexer -v
```

Expected: FAIL — `ConnectorIndexer` not patchable from `data_ingestion` module yet.

- [ ] **Step 3: Replace `_maybe_embed`**

In `backend/services/data_ingestion.py`, replace the body of `_maybe_embed` (currently lines ~190-207) with:

```python
    async def _maybe_embed(self, item: SourceItem, user_id: str):
        """Index the item into DocumentMemory via ConnectorIndexer.

        After Sprint B this is the only path connector content takes into
        Weaviate — `store_semantic_memory` is no longer called for source
        items because we want them to be cited by `search_documents` in chat.
        Best-effort: failures log and continue (Weaviate may be offline).
        """
        from services.connector_indexer import ConnectorIndexer
        try:
            indexer = ConnectorIndexer()
            n = await indexer.index(item)
            logger.debug(f"indexed {n} chunk(s) for {item.source_type}:{item.external_id}")
        except Exception as e:
            logger.warning(f"⚠️ ConnectorIndexer failed for {item.external_id}: {e}")
```

Also remove the now-unused `SemanticMemoryEntry` import at the top of the file if no other reference remains.

- [ ] **Step 4: Run the new test + the full sync test file**

```bash
python3 -m pytest tests/test_sync_source_items.py -v
```

Expected: all pass (the new test plus the existing ones, which were testing storage in `source_items` — that path is unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/services/data_ingestion.py backend/tests/test_sync_source_items.py
git commit -m "feat(connectors): route connector items through ConnectorIndexer"
```

---

## Task 4: `since` parameter on Gmail + Slack `fetch_raw_items`

**Files:**
- Modify: `backend/services/connectors/base.py:42-49`
- Modify: `backend/services/connectors/gmail.py:41-49`
- Modify: `backend/services/connectors/slack.py:22-27`
- Modify: `backend/services/gmail_sync.py` (add `query` arg to `fetch_messages`)
- Modify: `backend/services/slack_sync.py` (add `oldest` arg)
- Test: `backend/tests/test_connectors.py` (existing — extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_connectors.py`:

```python
@pytest.mark.asyncio
async def test_gmail_connector_passes_since_to_sync(monkeypatch):
    from services.connectors.gmail import GmailConnector
    from datetime import datetime, timezone

    captured: dict = {}

    class FakeSync:
        def fetch_messages(self, access_token, refresh_token="", query=None):
            captured["query"] = query
            return []

    c = GmailConnector(redirect_uri="http://x")
    c._sync = FakeSync()  # type: ignore[assignment]

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await c.fetch_raw_items(access_token="t", since=since)

    assert captured["query"] == "after:2026/01/01"
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_connectors.py::test_gmail_connector_passes_since_to_sync -v
```

Expected: FAIL — `fetch_raw_items` doesn't accept `since`.

- [ ] **Step 3: Extend the abstract base**

In `backend/services/connectors/base.py`, change:

```python
@abstractmethod
async def fetch_raw_items(
    self,
    access_token: str,
    refresh_token: Optional[str] = None,
    since: Optional["datetime"] = None,
) -> List[Dict[str, Any]]:
    """Fetch raw items from the external API.

    `since` is a soft hint: connectors that support server-side filtering
    use it to narrow the result set; others may ignore it. None means
    "use the connector's default window" (typically last 7 days).
    """
    ...
```

Import `from datetime import datetime` at the top.

- [ ] **Step 4: Implement in `GmailConnector`**

Replace `fetch_raw_items` in `backend/services/connectors/gmail.py`:

```python
async def fetch_raw_items(
    self,
    access_token: str,
    refresh_token: Optional[str] = None,
    since: Optional["datetime"] = None,
) -> List[Dict[str, Any]]:
    query = f"after:{since.strftime('%Y/%m/%d')}" if since else None
    return self._sync.fetch_messages(
        access_token=access_token,
        refresh_token=refresh_token or "",
        query=query,
    )
```

Add `from datetime import datetime` at the top.

- [ ] **Step 5: Implement in `SlackConnector`**

Replace `fetch_raw_items` in `backend/services/connectors/slack.py`:

```python
async def fetch_raw_items(
    self,
    access_token: str,
    refresh_token: Optional[str] = None,
    since: Optional["datetime"] = None,
) -> List[Dict[str, Any]]:
    oldest = str(since.timestamp()) if since else None
    return self._sync.fetch_messages(access_token=access_token, oldest=oldest)
```

Add `from datetime import datetime` at the top.

- [ ] **Step 6: Update `GmailSync.fetch_messages` to accept `query`**

In `backend/services/gmail_sync.py`, locate `fetch_messages` and add a `query: Optional[str] = None` parameter. When set, append it to the existing Gmail API `q` parameter (joined with a space if a default query already exists).

- [ ] **Step 7: Update `SlackSync.fetch_messages` to accept `oldest`**

In `backend/services/slack_sync.py`, locate `fetch_messages` and add an `oldest: Optional[str] = None` parameter. When set, pass it through to `conversations.history` API calls.

- [ ] **Step 8: Run the test + the full connectors test file**

```bash
python3 -m pytest tests/test_connectors.py -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/services/connectors/ backend/services/gmail_sync.py \
        backend/services/slack_sync.py backend/tests/test_connectors.py
git commit -m "feat(connectors): add `since` param for backfill + incremental sync"
```

---

## Task 5: Schedule Gmail + Slack syncs

**Files:**
- Modify: `backend/services/scheduler.py` (around line 50, the existing calendar job registration)
- Test: `backend/tests/test_scheduler_gmail_slack.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scheduler_gmail_slack.py
import pytest
from unittest.mock import MagicMock


def test_scheduler_registers_gmail_and_slack_jobs():
    from services.scheduler import EthicScheduler
    from services.data_ingestion import DataIngestionService

    di = MagicMock(spec=DataIngestionService)
    s = EthicScheduler(di)
    s.start()
    try:
        ids = {j.id for j in s.scheduler.get_jobs()}
        assert "sync_gmail" in ids
        assert "sync_slack" in ids
    finally:
        s.stop()
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_scheduler_gmail_slack.py -v
```

Expected: FAIL — neither job id present.

- [ ] **Step 3: Add the two jobs**

In `backend/services/scheduler.py`, find the `start()` method's calendar registration (around line 50). Below it, add:

```python
self.scheduler.add_job(
    func=self._sync_all_gmail,
    trigger="interval",
    minutes=30,
    id="sync_gmail",
    replace_existing=True,
)
self.scheduler.add_job(
    func=self._sync_all_slack,
    trigger="interval",
    minutes=5,
    id="sync_slack",
    replace_existing=True,
)
```

Then add the two methods (model them on the existing `_sync_all_calendars`):

```python
async def _sync_all_gmail(self):
    await self._sync_all_for_source("gmail")

async def _sync_all_slack(self):
    await self._sync_all_for_source("slack")

async def _sync_all_for_source(self, source_type: str):
    """Generic per-source sync runner — replaces the calendar-specific helper
    once we have three sources."""
    try:
        users = await self._get_users_with_source(source_type)
        synced = failed = 0
        for user_id in users:
            try:
                r = await self.data_ingestion.sync_data_source(user_id, source_type)
                synced += 1 if r.get("success") else 0
                failed += 0 if r.get("success") else 1
            except Exception as e:
                failed += 1
                logger.error(f"❌ {source_type} sync failed for {user_id}: {e}")
        logger.info(
            f"✅ Scheduled {source_type} sync: {synced} ok, {failed} failed"
        )
    except Exception as e:
        logger.error(f"❌ Critical error in {source_type} sync: {e}", exc_info=True)


async def _get_users_with_source(self, source_type: str) -> list:
    from utils.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM data_sources "
                "WHERE source_type = %s AND enabled = TRUE",
                (source_type,),
            )
            return [r["user_id"] for r in cur.fetchall()]
```

Also update the startup log lines so operators can see both jobs registered:

```python
logger.info("   - Gmail sync: Every 30 minutes")
logger.info("   - Slack sync: Every 5 minutes")
```

- [ ] **Step 4: Run the test**

```bash
python3 -m pytest tests/test_scheduler_gmail_slack.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/scheduler.py backend/tests/test_scheduler_gmail_slack.py
git commit -m "feat(scheduler): periodic Gmail (30m) + Slack (5m) syncs"
```

---

## Task 6: Disconnect cleanup — wipe tokens, items, vectors

**Files:**
- Modify: `backend/services/data_ingestion.py` (add `disconnect_data_source`)
- Modify: `backend/utils/weaviate_client.py` (add `delete_by_filter`)
- Test: `backend/tests/test_connector_lifecycle.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_connector_lifecycle.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
@patch("services.data_ingestion.get_weaviate_client")
async def test_disconnect_removes_tokens_items_and_vectors(mock_weav, mock_db):
    from services.data_ingestion import DataIngestionService

    weav = MagicMock()
    weav.delete_by_filter = MagicMock(return_value=42)
    mock_weav.return_value = weav

    cur = MagicMock()
    cur.rowcount = 7
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    mock_db.return_value.__enter__.return_value = conn

    svc = DataIngestionService(MagicMock())
    result = await svc.disconnect_data_source(USER_ID, "gmail")

    assert result["vectors_deleted"] == 42
    # Two DELETE statements: source_items + data_sources
    assert cur.execute.call_count >= 2
    weav.delete_by_filter.assert_called_once_with(
        "DocumentMemory",
        {"user_id": USER_ID, "source_type": "gmail"},
    )
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_connector_lifecycle.py::test_disconnect_removes_tokens_items_and_vectors -v
```

Expected: FAIL — neither method exists.

- [ ] **Step 3: Add `delete_by_filter` to `WeaviateClient`**

In `backend/utils/weaviate_client.py`:

```python
def delete_by_filter(self, collection: str, where: dict[str, str]) -> int:
    """Delete all objects in `collection` matching all key=value pairs in `where`.
    Returns the count deleted. Used by connector disconnect flows."""
    from weaviate.classes.query import Filter
    coll = self.client.collections.get(collection)
    flt = None
    for k, v in where.items():
        clause = Filter.by_property(k).equal(v)
        flt = clause if flt is None else flt & clause
    if flt is None:
        return 0
    res = coll.data.delete_many(where=flt)
    return getattr(res, "successful", 0) or 0
```

- [ ] **Step 4: Add `disconnect_data_source` to `DataIngestionService`**

```python
async def disconnect_data_source(self, user_id: str, source_type: str) -> dict:
    """Wipe everything associated with this connector for this user.

    Deletes (in order):
      1. Weaviate vectors in DocumentMemory for (user_id, source_type)
      2. Postgres source_items rows
      3. Postgres data_sources row (token + state)

    Order matters: if vector deletion fails, we leave the SQL state intact so
    the user can retry; we'd rather have orphan vectors than orphan tokens.
    """
    from utils.weaviate_client import get_weaviate_client
    weav = get_weaviate_client()

    vectors_deleted = 0
    if weav is not None:
        try:
            vectors_deleted = weav.delete_by_filter(
                "DocumentMemory",
                {"user_id": str(user_id), "source_type": source_type},
            )
        except Exception as e:
            logger.warning(f"⚠️ vector delete failed for {source_type}: {e}")
            return {"success": False, "vectors_deleted": 0,
                    "message": f"vector delete failed: {e}"}

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM source_items WHERE user_id = %s AND source_type = %s",
                (user_id, source_type),
            )
            items_deleted = cur.rowcount
            cur.execute(
                "DELETE FROM data_sources WHERE user_id = %s AND source_type = %s",
                (user_id, source_type),
            )
        conn.commit()

    logger.info(
        f"✅ disconnected {source_type} for {user_id}: "
        f"{vectors_deleted} vectors, {items_deleted} items"
    )
    return {
        "success": True,
        "vectors_deleted": vectors_deleted,
        "items_deleted": items_deleted,
    }
```

- [ ] **Step 5: Run the test**

```bash
python3 -m pytest tests/test_connector_lifecycle.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/data_ingestion.py backend/utils/weaviate_client.py \
        backend/tests/test_connector_lifecycle.py
git commit -m "feat(connectors): disconnect wipes tokens, items, and vectors"
```

---

## Task 7: Backfill job — historical sync on demand

**Files:**
- Modify: `backend/services/data_ingestion.py` (add `start_backfill`)
- Test: `backend/tests/test_connector_lifecycle.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_connector_lifecycle.py`:

```python
@pytest.mark.asyncio
@patch("services.data_ingestion.get_db_connection")
async def test_backfill_creates_job_and_runs_sync_with_since(mock_db):
    from services.data_ingestion import DataIngestionService
    from datetime import datetime, timezone

    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    mock_db.return_value.__enter__.return_value = conn

    svc = DataIngestionService(MagicMock())
    svc.sync_data_source = AsyncMock(return_value={"success": True, "items_synced": 25})

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    res = await svc.start_backfill(USER_ID, "gmail", since=since)

    assert res["items_synced"] == 25
    svc.sync_data_source.assert_awaited_once()
    kwargs = svc.sync_data_source.await_args.kwargs
    assert kwargs.get("since") == since
    # An INSERT into connector_backfill_jobs and an UPDATE to set status=complete
    sqls = " ".join(call.args[0] for call in cur.execute.call_args_list)
    assert "INSERT INTO connector_backfill_jobs" in sqls
    assert "UPDATE connector_backfill_jobs" in sqls
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_connector_lifecycle.py::test_backfill_creates_job_and_runs_sync_with_since -v
```

Expected: FAIL — `start_backfill` doesn't exist; `sync_data_source` doesn't accept `since`.

- [ ] **Step 3: Thread `since` through `sync_data_source`**

In `backend/services/data_ingestion.py`, change `sync_data_source`'s signature:

```python
async def sync_data_source(
    self,
    user_id: str,
    source_type: str,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
```

In the body, find the `connector.fetch_raw_items(...)` call (~line 104) and add `since=since`.

- [ ] **Step 4: Add `start_backfill`**

```python
async def start_backfill(
    self,
    user_id: str,
    source_type: str,
    since: datetime,
) -> Dict[str, Any]:
    """Run a one-shot historical sync. Tracks progress in connector_backfill_jobs."""
    started = datetime.now(timezone.utc)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO connector_backfill_jobs
                   (user_id, source_type, status, started_at)
                   VALUES (%s, %s, 'running', %s) RETURNING id""",
                (user_id, source_type, started),
            )
            job_id = cur.fetchone()["id"]
        conn.commit()

    try:
        result = await self.sync_data_source(user_id, source_type, since=since)
        items = result.get("items_synced", 0)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE connector_backfill_jobs
                       SET status = 'complete', finished_at = NOW(),
                           items_processed = %s
                       WHERE id = %s""",
                    (items, job_id),
                )
            conn.commit()
        return {"success": True, "job_id": str(job_id), "items_synced": items}
    except Exception as e:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE connector_backfill_jobs
                       SET status = 'failed', finished_at = NOW(),
                           error_message = %s
                       WHERE id = %s""",
                    (str(e)[:500], job_id),
                )
            conn.commit()
        raise
```

- [ ] **Step 5: Run the test**

```bash
python3 -m pytest tests/test_connector_lifecycle.py -v
```

Expected: both lifecycle tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/services/data_ingestion.py backend/tests/test_connector_lifecycle.py
git commit -m "feat(connectors): on-demand backfill with progress tracking"
```

---

## Task 8: `/api/connectors` REST surface

**Files:**
- Create: `backend/routes/connectors.py`
- Modify: `backend/main.py` (register router)
- Test: extend `backend/tests/test_connector_lifecycle.py` with FastAPI TestClient calls.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_connector_lifecycle.py`:

```python
def test_list_connectors_returns_summary_for_each_source(client, auth_headers):
    """GET /api/connectors returns one row per supported source with status."""
    resp = client.get("/api/connectors", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    sources = {row["source_type"] for row in body["connectors"]}
    assert {"gmail", "slack", "google_calendar"}.issubset(sources)
    for row in body["connectors"]:
        assert "connected" in row
        assert "last_sync" in row
        assert "items_count" in row
        assert "error" in row


def test_disconnect_endpoint_calls_service(client, auth_headers, monkeypatch):
    from services import data_ingestion as di_mod
    captured = {}
    async def fake_disconnect(self, user_id, source_type):
        captured["args"] = (user_id, source_type)
        return {"success": True, "vectors_deleted": 0, "items_deleted": 0}
    monkeypatch.setattr(di_mod.DataIngestionService, "disconnect_data_source", fake_disconnect)

    resp = client.delete("/api/connectors/gmail", headers=auth_headers)
    assert resp.status_code == 200
    assert captured["args"][1] == "gmail"
```

(Re-use the existing `client` and `auth_headers` fixtures — see `backend/tests/test_data_sources.py` for the pattern.)

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_connector_lifecycle.py::test_list_connectors_returns_summary_for_each_source -v
```

Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement the router**

```python
# backend/routes/connectors.py
"""Sprint B connector lifecycle: list, backfill, disconnect.

The OAuth callback path lives in routes/data_sources.py; this router covers
the operator surfaces added in Sprint B. The two routers can be merged later
when data_sources.py is refactored — for now the new behavior is isolated.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.dependencies import get_current_user_id
from services.data_ingestion import DataIngestionService
from services.context_manager import ContextManager
from utils.db import get_db_connection

router = APIRouter(prefix="/api/connectors", tags=["connectors"])

SUPPORTED = ["google_calendar", "gmail", "slack"]


class ConnectorRow(BaseModel):
    source_type: str
    connected: bool
    last_sync: Optional[datetime] = None
    items_count: int
    error: Optional[str] = None


class BackfillRequest(BaseModel):
    since_days: int = 90  # default: last 90 days


def _service() -> DataIngestionService:
    return DataIngestionService(ContextManager())


@router.get("")
async def list_connectors(user_id: str = Depends(get_current_user_id)) -> dict:
    rows: list[ConnectorRow] = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for source_type in SUPPORTED:
                cur.execute(
                    """SELECT enabled, last_sync, sync_error_message
                       FROM data_sources
                       WHERE user_id = %s AND source_type = %s""",
                    (user_id, source_type),
                )
                ds = cur.fetchone()
                cur.execute(
                    "SELECT COUNT(*) AS n FROM source_items "
                    "WHERE user_id = %s AND source_type = %s",
                    (user_id, source_type),
                )
                n = cur.fetchone()["n"]
                rows.append(ConnectorRow(
                    source_type=source_type,
                    connected=bool(ds and ds["enabled"]),
                    last_sync=ds["last_sync"] if ds else None,
                    items_count=n,
                    error=ds["sync_error_message"] if ds else None,
                ))
    return {"connectors": [r.model_dump() for r in rows]}


@router.post("/{source_type}/backfill")
async def backfill_connector(
    source_type: str,
    body: BackfillRequest,
    user_id: str = Depends(get_current_user_id),
):
    if source_type not in SUPPORTED:
        raise HTTPException(400, f"unsupported source: {source_type}")
    since = datetime.now(timezone.utc) - timedelta(days=body.since_days)
    return await _service().start_backfill(user_id, source_type, since=since)


@router.delete("/{source_type}")
async def disconnect_connector(
    source_type: str,
    user_id: str = Depends(get_current_user_id),
):
    if source_type not in SUPPORTED:
        raise HTTPException(400, f"unsupported source: {source_type}")
    return await _service().disconnect_data_source(user_id, source_type)
```

- [ ] **Step 4: Register the router in `backend/main.py`**

Find the block of `app.include_router(...)` calls. Add:

```python
from routes import connectors as connectors_routes
app.include_router(connectors_routes.router)
```

- [ ] **Step 5: Run the route tests**

```bash
python3 -m pytest tests/test_connector_lifecycle.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/connectors.py backend/main.py \
        backend/tests/test_connector_lifecycle.py
git commit -m "feat(connectors): /api/connectors list, backfill, disconnect"
```

---

## Task 9: Surface `source_type` in `search_documents` results

**Files:**
- Modify: `backend/services/rag_retrieval.py` (extend formatted row)
- Modify: `backend/services/langchain_tools.py` (tool description)
- Modify: `frontend/lib/api.ts` (extend `DocumentSource`)
- Modify: `frontend/components/chat/SourceCards.tsx` (icon switch)
- Test: `backend/tests/test_rag_retrieval.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_rag_retrieval.py`:

```python
@pytest.mark.asyncio
@patch("services.rag_retrieval.get_weaviate_client")
@patch("services.rag_retrieval.get_embedding_service")
async def test_retrieve_returns_source_type(mock_embed, mock_weav):
    from services.rag_retrieval import RagRetrievalService

    weav = MagicMock()
    weav.hybrid_search = MagicMock(return_value=[
        {"properties": {
            "user_id": USER_ID, "content": "hi",
            "document_id": "gmail:abc", "filename": "Re: Q2",
            "chunk_index": 0, "source_type": "gmail",
        }, "uuid": "u1", "score": 0.9},
    ])
    mock_weav.return_value = weav
    embed = MagicMock()
    embed.generate_query_embedding = AsyncMock(return_value=[0.1] * 768)
    mock_embed.return_value = embed

    res = await RagRetrievalService().retrieve("Q2 plan", USER_ID, k=5)
    assert res[0]["source_type"] == "gmail"
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_rag_retrieval.py::test_retrieve_returns_source_type -v
```

Expected: FAIL — `source_type` missing from formatted row.

- [ ] **Step 3: Add `source_type` to the formatter**

In `backend/services/rag_retrieval.py`, find the result-row dict literal in `retrieve()`. Add:

```python
"source_type": props.get("source_type", "document"),
```

(Default to `"document"` so legacy uploaded docs without the property still render.)

- [ ] **Step 4: Update tool description**

In `backend/services/langchain_tools.py`, find `class SearchDocumentsTool`. Replace the `description` string with:

```python
description: str = (
    "Search the user's indexed knowledge — uploaded documents, recent emails "
    "(Gmail), and Slack messages — for passages relevant to the query. Use "
    "this whenever the user asks a question that could plausibly be answered "
    "by their own files, inbox, or conversations. Returns ranked excerpts "
    "with attribution."
)
```

- [ ] **Step 5: Extend frontend type**

In `frontend/lib/api.ts`, extend `DocumentSource`:

```ts
export interface DocumentSource {
  chunk_uuid?: string
  document_id?: string
  filename?: string
  chunk_index?: number
  snippet?: string
  score?: number
  source_type?: 'document' | 'gmail' | 'slack' | 'google_calendar'
}
```

- [ ] **Step 6: Switch the card icon by `source_type`**

In `frontend/components/chat/SourceCards.tsx`, replace the unconditional `<FileText size={11} />`:

```tsx
import { FileText, Mail, MessageCircle, Calendar } from 'lucide-react'

const SOURCE_ICON: Record<string, React.ComponentType<{ size: number }>> = {
  document: FileText,
  gmail: Mail,
  slack: MessageCircle,
  google_calendar: Calendar,
}

// inside SourceCard:
const Icon = SOURCE_ICON[source.source_type ?? 'document'] ?? FileText
// ...replace the <FileText size={11} /> line with:
<Icon size={11} />
```

Also tweak the `href` so non-document sources don't link to `/dashboard/documents`:

```tsx
const href =
  source.source_type === 'gmail' || source.source_type === 'slack'
    ? '#'
    : source.document_id
      ? `/dashboard/documents?doc=${source.document_id}`
      : '#'
```

- [ ] **Step 7: Run all relevant tests + tsc**

```bash
python3 -m pytest tests/test_rag_retrieval.py -v
cd ../frontend && node node_modules/typescript/bin/tsc --noEmit
```

Expected: backend passes, frontend clean.

- [ ] **Step 8: Commit**

```bash
git add backend/services/rag_retrieval.py backend/services/langchain_tools.py \
        backend/tests/test_rag_retrieval.py \
        frontend/lib/api.ts frontend/components/chat/SourceCards.tsx
git commit -m "feat(rag): attribute citations by source_type (gmail/slack/document)"
```

---

## Task 10: Integrations Settings page

**Files:**
- Create: `frontend/app/dashboard/settings/integrations/page.tsx`
- Create: `frontend/components/settings/IntegrationCard.tsx`
- Modify: `frontend/lib/api.ts` (add `connectors` namespace)

- [ ] **Step 1: Add `connectors` to `frontend/lib/api.ts`**

In the API object literal next to `chat`, `tasks`, `goals`:

```ts
connectors: {
  list: () => apiRequest<{ connectors: Array<{
    source_type: string
    connected: boolean
    last_sync: string | null
    items_count: number
    error: string | null
  }> }>('/api/connectors'),
  backfill: (source: string, since_days: number = 90) =>
    apiRequest<{ success: boolean; job_id: string; items_synced: number }>(
      `/api/connectors/${source}/backfill`,
      { method: 'POST', body: JSON.stringify({ since_days }) },
    ),
  disconnect: (source: string) =>
    apiRequest<{ success: boolean; vectors_deleted: number; items_deleted: number }>(
      `/api/connectors/${source}`,
      { method: 'DELETE' },
    ),
},
```

- [ ] **Step 2: Build the card component**

```tsx
// frontend/components/settings/IntegrationCard.tsx
'use client'

import { useState } from 'react'
import { Mail, MessageCircle, Calendar, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/lib/toast'

const ICONS: Record<string, React.ComponentType<{ size: number }>> = {
  gmail: Mail, slack: MessageCircle, google_calendar: Calendar,
}
const LABELS: Record<string, string> = {
  gmail: 'Gmail', slack: 'Slack', google_calendar: 'Google Calendar',
}

interface Props {
  row: {
    source_type: string
    connected: boolean
    last_sync: string | null
    items_count: number
    error: string | null
  }
  onChange: () => void
}

export function IntegrationCard({ row, onChange }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const Icon = ICONS[row.source_type] ?? Mail
  const label = LABELS[row.source_type] ?? row.source_type

  const handleBackfill = async () => {
    setBusy('backfill')
    try {
      const r = await api.connectors.backfill(row.source_type, 90)
      toast.success('Backfill complete', `${r.items_synced} items indexed`)
      onChange()
    } catch (e) {
      toast.error('Backfill failed', e instanceof Error ? e.message : undefined)
    } finally { setBusy(null) }
  }

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect ${label}? This deletes all indexed content.`)) return
    setBusy('disconnect')
    try {
      const r = await api.connectors.disconnect(row.source_type)
      toast.success('Disconnected', `${r.items_deleted} items removed`)
      onChange()
    } catch (e) {
      toast.error('Disconnect failed', e instanceof Error ? e.message : undefined)
    } finally { setBusy(null) }
  }

  return (
    <div className="rounded-lg border p-4"
         style={{ borderColor: 'var(--ec-card-border)', background: 'var(--ec-card-bg)' }}>
      <div className="flex items-center gap-3">
        <Icon size={20} />
        <div className="flex-1 min-w-0">
          <div className="font-medium">{label}</div>
          <div className="text-xs" style={{ color: 'var(--ec-text-muted)' }}>
            {row.connected
              ? `${row.items_count} items · last sync ${row.last_sync ? new Date(row.last_sync).toLocaleString() : 'never'}`
              : 'Not connected'}
          </div>
          {row.error && (
            <div className="text-xs mt-1" style={{ color: '#c0392b' }}>{row.error}</div>
          )}
        </div>
        {row.connected && (
          <>
            <button onClick={handleBackfill} disabled={busy !== null}
                    className="flex items-center gap-1 px-2 py-1 text-xs rounded border"
                    style={{ borderColor: 'var(--ec-card-border)' }}>
              <RefreshCw size={12} /> {busy === 'backfill' ? 'Working…' : 'Backfill 90d'}
            </button>
            <button onClick={handleDisconnect} disabled={busy !== null}
                    className="flex items-center gap-1 px-2 py-1 text-xs rounded border"
                    style={{ borderColor: 'var(--ec-card-border)', color: '#c0392b' }}>
              <Trash2 size={12} /> Disconnect
            </button>
          </>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Build the page**

```tsx
// frontend/app/dashboard/settings/integrations/page.tsx
'use client'

import { useEffect, useState, useCallback } from 'react'
import { api } from '@/lib/api'
import { IntegrationCard } from '@/components/settings/IntegrationCard'

type Row = {
  source_type: string
  connected: boolean
  last_sync: string | null
  items_count: number
  error: string | null
}

export default function IntegrationsPage() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.connectors.list()
      setRows(r.connectors)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-1">Integrations</h1>
      <p className="text-sm mb-6" style={{ color: 'var(--ec-text-muted)' }}>
        Connect your accounts so chat can cite your emails, Slack messages, and calendar.
        Everything stays in your workspace; ESL gates every action that uses this data.
      </p>
      {loading ? (
        <div className="text-sm" style={{ color: 'var(--ec-text-muted)' }}>Loading…</div>
      ) : (
        <div className="space-y-3">
          {rows.map(r => (
            <IntegrationCard key={r.source_type} row={r} onChange={load} />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run frontend typecheck**

```bash
cd frontend && node node_modules/typescript/bin/tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/dashboard/settings/integrations/ \
        frontend/components/settings/IntegrationCard.tsx \
        frontend/lib/api.ts
git commit -m "feat(settings): integrations page with backfill + disconnect"
```

---

## Task 11: End-to-end smoke test (manual)

This task is a runbook; no commit unless gaps are found.

- [ ] **Step 1: Apply migration in staging DB**

```bash
psql "$DATABASE_URL" -f backend/migrations/010_document_memory_source_type.sql
```

- [ ] **Step 2: Restart backend; confirm scheduler logs**

In server logs look for:

```
✅ Calendar sync: Every 15 minutes
✅ Gmail sync: Every 30 minutes
✅ Slack sync: Every 5 minutes
```

- [ ] **Step 3: Connect Gmail via Settings → Integrations**

Visit `/dashboard/settings/integrations`, click Connect on Gmail (this still flows through the existing OAuth route). After redirect, the card should show "N items · last sync seconds-ago".

- [ ] **Step 4: Trigger backfill 90d**

Click "Backfill 90d". Toast appears with item count after a few seconds. Card refreshes.

- [ ] **Step 5: Ask a grounded question in chat**

In chat, type a question whose answer is in a recent email:

```
What did the team decide about the Q2 roadmap?
```

Expected behavior:
- Tool indicator shows `search_documents` firing.
- Response includes a `<SourceCards>` block.
- At least one card has the Mail icon (Gmail) and the email subject as filename.

- [ ] **Step 6: Verify `/ask` works on Slack content**

Type `/ask what was the deploy outcome friday?` (assuming relevant Slack context exists). Verify a Slack-icon card renders.

- [ ] **Step 7: Disconnect Gmail**

Click Disconnect. Confirm. Re-ask the same question — no Gmail cards should appear (vectors gone).

- [ ] **Step 8: If any gap found**

Open a follow-up issue / spawn a fix task. Otherwise mark sprint done.

---

## Task 12: Run full backend test suite + frontend typecheck

- [ ] **Step 1: Backend**

```bash
cd backend && python3 -m pytest -q
```

Expected: all tests pass (Sprint A's 333 plus the ~12 new tests added in this sprint).

- [ ] **Step 2: Frontend typecheck**

```bash
cd frontend && node node_modules/typescript/bin/tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Frontend tests**

```bash
cd frontend && npm run test
```

Expected: all tests pass.

- [ ] **Step 4: Final commit (if anything was touched up)**

```bash
git status
# if clean: nothing to commit
```

---

## Self-Review Checklist (resolved)

- **Spec coverage:** Every deliverable from the master roadmap's Sprint B (Connector interface, Gmail+Slack adapters, scheduler entry, OAuth lifecycle including disconnect cleanup, backfill job) maps to a task above. The "queryable through Sprint A's RAG path" outcome is delivered by Tasks 2 + 3 + 9.
- **Placeholder scan:** No "TBD", "implement later", or hand-wavy "add validation" — every code step has the actual code.
- **Type consistency:** `SourceItem`, `ConnectorRow`, `DocumentSource.source_type`, `disconnect_data_source`, and `start_backfill` signatures match across tasks. The `since` parameter has the same type (`Optional[datetime]`) and semantics ("None means default window") in every task that touches it. The `BaseConnector.fetch_raw_items` change in Task 4 is reflected in the call site change in Task 7.
- **No dangling references:** All file paths exist or are explicitly created. All Postgres tables (`source_items`, `data_sources`, `connector_backfill_jobs`) are either pre-existing in `backend/database/schema.sql` or created in Task 1.

---

## Execution

Plan complete and saved to `docs/plans/2026-04-25-sprint-b-connector-framework.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best when you want oversight after each step.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. Best when you want me to keep going until something needs your input.

**Which approach?**
