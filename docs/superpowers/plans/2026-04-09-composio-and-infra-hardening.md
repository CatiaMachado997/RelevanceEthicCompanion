# Composio Swap + Infrastructure Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 3 custom OAuth connectors (GitHub, Notion, Slack-write) with Composio's managed integration platform, fix the dark-themed marketplace UI, and harden infrastructure with connection pooling, typed errors, and proper credential encryption.

**Architecture:** `ComposioToolSet(entity_id=user_id)` from `composio-langchain` becomes the single execution layer for all marketplace write-tools. ESL tool gate still runs before every Composio call — zero bypass. Data-ingestion connectors (Gmail sync, GCal sync, Slack sync) are read-only and untouched. A new `POST /api/tools/composio/connect` → Composio OAuth → `GET /api/tools/composio/callback` flow replaces the broken per-connector OAuth routes. `user_tool_connections` keeps tracking connected state (our DB is source-of-truth); Composio holds the actual OAuth tokens on their side.

**Tech Stack:** composio-langchain 0.11.4, cryptography (Fernet, already installed), psycopg[pool] (add pool extra), existing LangGraph / FastAPI / Next.js stack.

---

## Why This Change

| Problem | Root cause | Fix |
|---|---|---|
| Connect buttons crashed | `GoogleCalendarConnector()` needs `redirect_uri`, `NotionConnector.client_id = ""` | Composio handles OAuth — no constructor args |
| Notion/GitHub had no credentials | `NOTION_CLIENT_ID=""`, `GITHUB_CLIENT_ID=""` | Composio uses its own OAuth apps; no per-tool creds in our `.env` |
| Credentials stored plaintext | `_encrypt_credentials()` was a TODO JSON serialise | Fernet encrypt + decrypt in `utils/encryption.py` |
| Dark theme in marketplace | `CatalogueCard` and MCP section use Tailwind dark classes | Match the light theme pattern used by the rest of integrations page |
| No DB connection pool | `get_db_connection()` opens a new connection every call | `psycopg[pool]` ConnectionPool singleton |
| No typed errors | Routes raise raw `Exception`, `HTTPException(500, str(e))` | Hierarchy: `EthicCompanionError → IntegrationError / DBError / AuthError` |

---

## File Map

**Created:**
- `backend/services/composio_tools.py` — Composio toolset factory, action→ESL metadata map, per-user tool loading
- `backend/utils/encryption.py` — Fernet encrypt / decrypt for any stored credentials
- `backend/utils/errors.py` — Typed exception hierarchy + FastAPI handler
- `backend/tests/test_composio_tools.py` — Unit tests for composio_tools.py
- `backend/tests/test_composio_routes.py` — Route tests for Composio connect/callback endpoints

**Modified:**
- `backend/requirements.txt` — add `composio-langchain==0.11.4`, change `psycopg[binary]` → `psycopg[binary,pool]`
- `backend/config.py` — add `COMPOSIO_API_KEY: str = ""`
- `backend/.env.example` — add `COMPOSIO_API_KEY=` placeholder
- `backend/services/tool_registry.py` — replace `_make_action_tool` / `_dispatch_action` path with Composio
- `backend/routes/tool_marketplace.py` — add `POST /composio/connect` + `GET /composio/callback`; remove `GET /{tool_id}/oauth/authorize`
- `backend/utils/db.py` — wrap with `psycopg_pool.ConnectionPool` singleton
- `backend/main.py` — register typed error handler from `utils/errors.py`; open/close DB pool on lifespan
- `frontend/lib/api.ts` — add `connectComposio(toolkit)` method to `toolMarketplaceApi`
- `frontend/components/CatalogueCard.tsx` — replace dark Tailwind classes with inline light-theme styles
- `frontend/app/dashboard/integrations/page.tsx` — fix MCP section dark theme; call `connectComposio` instead of `getAuthUrl`

**Deleted:**
- `backend/services/connectors/github.py` — replaced by Composio
- `backend/services/connectors/notion.py` — replaced by Composio
- `backend/services/connectors/slack_write.py` — replaced by Composio

**Tests updated:**
- `backend/tests/test_tool_marketplace_routes.py` — swap oauth/authorize tests for composio/connect tests
- `backend/tests/test_connectors.py` — remove github / notion / slack_write test classes

---

## Task 1: Install Composio + Update Config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify (or create): `backend/.env.example`

- [ ] **Step 1: Add composio-langchain and pool extra to requirements**

Open `backend/requirements.txt`. Make two edits:

Change line 9:
```
psycopg[binary]>=3.2.0
```
To:
```
psycopg[binary,pool]>=3.2.0
```

Add after `mcp` at the bottom (line 70):
```
# Tool Marketplace — Composio managed integrations
composio-langchain==0.11.4
```

- [ ] **Step 2: Add COMPOSIO_API_KEY to Settings**

In `backend/config.py`, after the existing `NOTION_CLIENT_SECRET: str = ""` line (~line 75), add:

```python
    # Composio — managed tool integrations (replaces per-connector OAuth boilerplate)
    # Get your key free at https://app.composio.dev/settings (API Keys tab)
    COMPOSIO_API_KEY: str = ""
```

- [ ] **Step 3: Add placeholder to .env.example**

In `backend/.env.example` (create if it doesn't exist — copy from `.env` and blank all secrets), add:
```
# Composio Tool Integration Platform
# Free tier: 20K tool calls/month. Get key: https://app.composio.dev/settings
COMPOSIO_API_KEY=your_composio_api_key_here
```

- [ ] **Step 4: Install in venv**

```bash
cd backend
source venv/bin/activate
pip install composio-langchain==0.11.4
```

Expected output: `Successfully installed composio-core-x.x.x composio-langchain-0.11.4 ...`

- [ ] **Step 5: Verify import**

```bash
python -c "from composio_langchain import ComposioToolSet, Action, App; print('OK', App.GITHUB)"
```

Expected output: `OK App.GITHUB`

- [ ] **Step 6: Commit**

```bash
cd backend
git add requirements.txt config.py .env.example
git commit -m "feat: add composio-langchain + COMPOSIO_API_KEY config"
```

---

## Task 2: Create `services/composio_tools.py`

**Files:**
- Create: `backend/services/composio_tools.py`
- Create: `backend/tests/test_composio_tools.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_composio_tools.py`:

```python
"""Tests for composio_tools.py — mocks Composio SDK, tests ESL metadata tagging."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from services.composio_tools import get_composio_tools_for_user, TOOL_ID_TO_COMPOSIO_APP


@pytest.fixture
def mock_composio_tool() -> MagicMock:
    tool = MagicMock(spec=BaseTool)
    tool.metadata = {}
    return tool


class TestGetComposioToolsForUser:
    def test_returns_empty_list_when_no_tools_connected(self):
        result = asyncio.get_event_loop().run_until_complete(
            get_composio_tools_for_user(user_id="user-123", connected_tool_ids=set())
        )
        assert result == []

    def test_skips_tools_not_in_connected_ids(self):
        with patch("services.composio_tools.ComposioToolSet") as MockToolSet:
            MockToolSet.return_value.get_tools.return_value = [MagicMock(spec=BaseTool, metadata={})]
            result = asyncio.get_event_loop().run_until_complete(
                get_composio_tools_for_user(
                    user_id="user-123",
                    connected_tool_ids={"notion"},  # github NOT included
                )
            )
            calls = MockToolSet.return_value.get_tools.call_args_list
            # Only notion actions should have been requested
            for call in calls:
                actions = call.kwargs.get("actions") or call.args[0] if call.args else []
                for action in actions:
                    assert "GITHUB" not in str(action)

    def test_tags_tool_with_esl_metadata(self, mock_composio_tool):
        """Each returned tool must have tool_id, action_name, risk_level in metadata."""
        with patch("services.composio_tools.ComposioToolSet") as MockToolSet:
            MockToolSet.return_value.get_tools.return_value = [mock_composio_tool]
            result = asyncio.get_event_loop().run_until_complete(
                get_composio_tools_for_user(
                    user_id="user-123",
                    connected_tool_ids={"github"},
                )
            )
        # At least one tool should have been tagged
        tagged = [t for t in result if t.metadata.get("tool_id")]
        assert len(tagged) > 0
        for t in tagged:
            assert "tool_id" in t.metadata
            assert "action_name" in t.metadata
            assert t.metadata["risk_level"] in ("low", "medium", "high")

    def test_graceful_failure_returns_partial_tools(self, mock_composio_tool):
        """If one action fails, remaining tools still load."""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Composio error")
            return [mock_composio_tool]

        with patch("services.composio_tools.ComposioToolSet") as MockToolSet:
            MockToolSet.return_value.get_tools.side_effect = side_effect
            result = asyncio.get_event_loop().run_until_complete(
                get_composio_tools_for_user(
                    user_id="user-123",
                    connected_tool_ids={"github"},
                )
            )
        # Even after first error, some tools returned
        assert isinstance(result, list)

    def test_tool_id_to_composio_app_covers_all_tool_ids(self):
        expected_tool_ids = {"github", "notion", "slack", "gmail_write", "google_calendar_write"}
        assert expected_tool_ids == set(TOOL_ID_TO_COMPOSIO_APP.keys())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_composio_tools.py -v
```

Expected: `ImportError: cannot import name 'get_composio_tools_for_user'`

- [ ] **Step 3: Implement `services/composio_tools.py`**

Create `backend/services/composio_tools.py`:

```python
"""
Composio tool integration — loads per-user tools from Composio's managed platform.

Composio handles OAuth, token storage, and token refresh for all connected apps.
We tag each returned LangChain BaseTool with ESL metadata (tool_id, action_name,
risk_level) so the existing ESLToolGate in orchestrator/nodes/tools.py can gate them
without any changes.

Usage:
    from services.composio_tools import get_composio_tools_for_user

    tools = await get_composio_tools_for_user(
        user_id="uuid",
        connected_tool_ids={"github", "notion"},
    )
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# Maps our internal tool_id (in tool_definitions) to the Composio App enum name.
# Keep in sync with the tool_definitions table seed.
TOOL_ID_TO_COMPOSIO_APP: dict[str, str] = {
    "github": "GITHUB",
    "notion": "NOTION",
    "slack": "SLACK",
    "gmail_write": "GMAIL",
    "google_calendar_write": "GOOGLECALENDAR",
}

# Each entry: (composio_action_enum_name, our_tool_id, our_action_name, risk_level)
# risk_level drives ESL gate: low → auto-approve, medium → ask once, high → always ask
_ACTION_METADATA: list[tuple[str, str, str, str]] = [
    ("GITHUB_LIST_REPOSITORY_ISSUES",             "github",                "list_issues",   "low"),
    ("GITHUB_CREATE_AN_ISSUE",                    "github",                "create_issue",  "medium"),
    ("GITHUB_CREATE_AN_ISSUE_COMMENT",            "github",                "add_comment",   "medium"),
    ("NOTION_SEARCH",                             "notion",                "search_pages",  "low"),
    ("NOTION_CREATE_PAGE",                        "notion",                "create_page",   "medium"),
    ("GMAIL_CREATE_EMAIL_DRAFT",                  "gmail_write",           "create_draft",  "low"),
    ("GMAIL_REPLY_TO_THREAD",                     "gmail_write",           "send_reply",    "high"),
    ("GOOGLECALENDAR_CREATE_EVENT",               "google_calendar_write", "create_event",  "low"),
    ("GOOGLECALENDAR_UPDATE_EVENT",               "google_calendar_write", "update_event",  "medium"),
    ("SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",  "slack",                 "send_message",  "high"),
    ("SLACK_FETCH_CONVERSATION_HISTORY",          "slack",                 "read_channel",  "low"),
]


async def get_composio_tools_for_user(
    user_id: str,
    connected_tool_ids: set[str],
) -> "list[BaseTool]":
    """Return ESL-tagged LangChain BaseTool instances for the user's connected apps.

    Only fetches actions for apps the user has connected (checked against our DB,
    not Composio's API — no extra round-trip). Each tool gets ESL metadata attached
    so ESLToolGate can identify it without modification.

    Args:
        user_id: Your internal user UUID. Used as Composio entity_id for token isolation.
        connected_tool_ids: Set of tool_ids the user has connected (from user_tool_connections).

    Returns:
        List of BaseTool instances, empty list if nothing connected or on error.
    """
    if not connected_tool_ids:
        return []

    if not settings.COMPOSIO_API_KEY:
        logger.warning("COMPOSIO_API_KEY not set — marketplace tools unavailable")
        return []

    from composio_langchain import Action, ComposioToolSet

    toolset = ComposioToolSet(
        api_key=settings.COMPOSIO_API_KEY,
        entity_id=user_id,
    )

    tagged_tools: list[BaseTool] = []

    for action_enum_name, tool_id, action_name, risk_level in _ACTION_METADATA:
        if tool_id not in connected_tool_ids:
            continue
        try:
            action = getattr(Action, action_enum_name)
            # get_tools is synchronous (schema construction, no network I/O)
            tools = await asyncio.to_thread(toolset.get_tools, actions=[action])
            for tool in tools:
                tool.metadata = {
                    "tool_id": tool_id,
                    "action_name": action_name,
                    "risk_level": risk_level,
                }
                tagged_tools.append(tool)
        except AttributeError:
            logger.warning(
                f"Composio action {action_enum_name!r} not found in this SDK version"
                " — update composio-langchain or check the action name"
            )
        except Exception as exc:
            logger.warning(f"Failed to load Composio action {action_enum_name}: {exc}")

    logger.debug(f"Composio: {len(tagged_tools)} tools for user {user_id}")
    return tagged_tools
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_composio_tools.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add services/composio_tools.py tests/test_composio_tools.py
git commit -m "feat: composio_tools — per-user tool loading with ESL metadata tagging"
```

---

## Task 3: Update `services/tool_registry.py`

**Files:**
- Modify: `backend/services/tool_registry.py`

The goal: replace the `_make_action_tool` / `_dispatch_action` path with `get_composio_tools_for_user`. The MCP path (`_load_mcp_tools`) is unchanged.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_tool_registry.py` (create if it doesn't exist, otherwise append):

```python
"""Tests for ToolRegistry using Composio."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.tools import BaseTool

from services.tool_registry import ToolRegistry


@pytest.fixture
def mock_composio_tool():
    t = MagicMock(spec=BaseTool)
    t.metadata = {"tool_id": "github", "action_name": "create_issue", "risk_level": "medium"}
    return t


class TestToolRegistryComposio:
    @pytest.mark.asyncio
    async def test_returns_composio_tools_for_connected_user(self, mock_composio_tool):
        registry = ToolRegistry()
        db_connections = [
            {"tool_id": "github", "enabled": True, "credentials": "{}", "mcp_url": None}
        ]
        with patch("services.tool_registry.get_db_connection") as mock_db, \
             patch("services.tool_registry.get_composio_tools_for_user", new_callable=AsyncMock) as mock_composio:
            # Setup DB mock
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.side_effect = [db_connections, []]  # connections, then definitions (not used)
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.return_value = mock_conn
            mock_composio.return_value = [mock_composio_tool]

            tools = await registry.get_tools_for_user("user-123")

        assert len(tools) == 1
        assert tools[0].metadata["tool_id"] == "github"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_connections(self):
        registry = ToolRegistry()
        with patch("services.tool_registry.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = []
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.return_value = mock_conn

            tools = await registry.get_tools_for_user("user-123")

        assert tools == []

    @pytest.mark.asyncio
    async def test_composio_failure_returns_empty_not_raises(self):
        registry = ToolRegistry()
        db_connections = [
            {"tool_id": "github", "enabled": True, "credentials": "{}", "mcp_url": None}
        ]
        with patch("services.tool_registry.get_db_connection") as mock_db, \
             patch("services.tool_registry.get_composio_tools_for_user", new_callable=AsyncMock) as mock_composio:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = db_connections
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.return_value = mock_conn
            mock_composio.side_effect = RuntimeError("Composio down")

            tools = await registry.get_tools_for_user("user-123")

        assert tools == []
```

- [ ] **Step 2: Run test to confirm failure**

```bash
pytest tests/test_tool_registry.py::TestToolRegistryComposio -v
```

Expected: `ImportError` or `AssertionError` (Composio path not yet wired).

- [ ] **Step 3: Replace `tool_registry.py`**

Replace the entire contents of `backend/services/tool_registry.py` with:

```python
"""
ToolRegistry — dynamic tool loader.

Reads user_tool_connections from DB to determine which apps the user has connected,
then returns ready-to-invoke LangChain BaseTool instances:

  • Composio tools  — for catalogue tools (github, notion, slack, gmail_write, google_calendar_write)
  • MCP tools       — for user-supplied MCP server URLs (auth_type='mcp')
"""
from __future__ import annotations

import logging

from langchain_core.tools import BaseTool

from utils.db import get_db_connection
from services.composio_tools import get_composio_tools_for_user

logger = logging.getLogger(__name__)

# Tool IDs managed by Composio — NOT dispatched via connector classes
_COMPOSIO_TOOL_IDS = frozenset({
    "github", "notion", "slack", "gmail_write", "google_calendar_write"
})


class ToolRegistry:
    """Load and instantiate connected tools for a given user."""

    async def get_tools_for_user(self, user_id: str) -> list[BaseTool]:
        """Return LangChain BaseTool instances for all tools the user has connected.

        Returns [] on any error — never raises, so orchestrator startup is not blocked.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tool_id, enabled, mcp_url
                        FROM user_tool_connections
                        WHERE user_id = %s AND enabled = TRUE
                        """,
                        (user_id,),
                    )
                    connections = cur.fetchall()

            if not connections:
                return []

            composio_tool_ids: set[str] = set()
            mcp_connections: list[dict] = []

            for row in connections:
                tid = row["tool_id"]
                if tid in _COMPOSIO_TOOL_IDS:
                    composio_tool_ids.add(tid)
                elif row.get("mcp_url"):
                    mcp_connections.append(row)

            tools: list[BaseTool] = []

            # ── Composio tools ────────────────────────────────────────────────
            if composio_tool_ids:
                try:
                    composio_tools = await get_composio_tools_for_user(user_id, composio_tool_ids)
                    tools.extend(composio_tools)
                except Exception as exc:
                    logger.warning(f"Composio tools unavailable for user {user_id}: {exc}")

            # ── MCP tools ─────────────────────────────────────────────────────
            for row in mcp_connections:
                try:
                    from services.mcp_client import MCPClient
                    mcp_tools = await MCPClient(row["mcp_url"]).get_tools()
                    tools.extend(mcp_tools)
                except Exception as exc:
                    logger.warning(f"MCP tools unavailable at {row['mcp_url']}: {exc}")

            logger.debug(f"ToolRegistry: {len(tools)} tools loaded for user {user_id}")
            return tools

        except Exception as exc:
            logger.warning(f"ToolRegistry.get_tools_for_user failed: {exc}")
            return []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tool_registry.py::TestToolRegistryComposio -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add services/tool_registry.py tests/test_tool_registry.py
git commit -m "refactor: tool_registry uses Composio instead of _dispatch_action connectors"
```

---

## Task 4: Update `routes/tool_marketplace.py` — Composio Connect Flow

**Files:**
- Modify: `backend/routes/tool_marketplace.py`
- Create: `backend/tests/test_composio_routes.py`

Replace the broken `GET /{tool_id}/oauth/authorize` endpoint with two new endpoints:
- `POST /api/tools/composio/connect` — returns Composio OAuth URL
- `GET /api/tools/composio/callback` — records connection, redirects to frontend

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_composio_routes.py`:

```python
"""Tests for the Composio connect/callback route endpoints."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


class TestComposioConnectEndpoint:
    def test_returns_connect_url_for_valid_toolkit(self, client, auth_headers):
        mock_request = MagicMock()
        mock_request.redirectUrl = "https://backend.composio.dev/oauth/authorize/github"

        with patch("routes.tool_marketplace.ComposioToolSet") as MockToolSet, \
             patch("routes.tool_marketplace.get_current_user_id", return_value="user-123"):
            MockToolSet.return_value.initiate_connection.return_value = mock_request

            resp = client.post(
                "/api/tools/composio/connect",
                json={"toolkit": "github"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["connect_url"] == "https://backend.composio.dev/oauth/authorize/github"

    def test_returns_404_for_unknown_toolkit(self, client, auth_headers):
        with patch("routes.tool_marketplace.get_current_user_id", return_value="user-123"):
            resp = client.post(
                "/api/tools/composio/connect",
                json={"toolkit": "fakeapp"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_missing_composio_api_key_returns_503(self, client, auth_headers):
        with patch("routes.tool_marketplace.settings") as mock_settings, \
             patch("routes.tool_marketplace.get_current_user_id", return_value="user-123"):
            mock_settings.COMPOSIO_API_KEY = ""
            resp = client.post(
                "/api/tools/composio/connect",
                json={"toolkit": "github"},
                headers=auth_headers,
            )
        assert resp.status_code == 503


class TestComposioCallbackEndpoint:
    def test_successful_callback_stores_connection_and_redirects(self, client):
        with patch("routes.tool_marketplace._extract_user_from_state", return_value="user-123"), \
             patch("routes.tool_marketplace._store_connection") as mock_store, \
             patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={
                    "toolkit": "github",
                    "state": "signed-state-token",
                    "status": "success",
                    "connected_account_id": "ca_abc123",
                },
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "connected=github" in resp.headers["location"]
        mock_store.assert_called_once()

    def test_failed_callback_redirects_with_error(self, client):
        with patch("routes.tool_marketplace.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "http://localhost:3000"
            resp = client.get(
                "/api/tools/composio/callback",
                params={"toolkit": "github", "state": "state", "status": "error"},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "error=" in resp.headers["location"]
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_composio_routes.py -v
```

Expected: `ImportError` or connection errors (endpoints don't exist yet).

- [ ] **Step 3: Add Composio connect/callback to `routes/tool_marketplace.py`**

Add the following imports at the top of `backend/routes/tool_marketplace.py` (after existing imports):

```python
from services.composio_tools import TOOL_ID_TO_COMPOSIO_APP
```

Replace the `# ─── OAuth connect flow ───` section (the `authorize_tool` endpoint, lines ~117–127) with these two new endpoints. **Remove** `GET /{tool_id}/oauth/authorize` entirely. Keep `GET /{tool_id}/oauth/callback` — it handles legacy data-source OAuth flows.

Add after the existing imports block, a new schema:

```python
class ComposioConnectRequest(BaseModel):
    toolkit: str  # our tool_id: "github" | "notion" | "slack" | "gmail_write" | "google_calendar_write"
```

Add the two new endpoints **before** the `# ─── Disconnect ───` section:

```python
# ─── Composio connect flow ────────────────────────────────────────────────────

@router.post("/composio/connect")
async def composio_connect(
    body: ComposioConnectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Initiate Composio OAuth for a catalogue tool.

    Returns a Composio-hosted OAuth URL. Frontend redirects the user there.
    Composio handles token exchange and redirects to /api/tools/composio/callback.
    """
    if not settings.COMPOSIO_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Composio integration not configured. Set COMPOSIO_API_KEY in .env.",
        )

    composio_app_name = TOOL_ID_TO_COMPOSIO_APP.get(body.toolkit)
    if not composio_app_name:
        raise HTTPException(status_code=404, detail=f"Unknown toolkit: {body.toolkit}")

    from composio_langchain import ComposioToolSet
    from composio import App

    state = _build_oauth_state(user_id=user_id, tool_id=f"composio_{body.toolkit}")
    callback_url = (
        f"{settings.BACKEND_URL}/api/tools/composio/callback"
        f"?toolkit={quote(body.toolkit, safe='')}&state={quote(state, safe='')}"
    )

    try:
        app_enum = getattr(App, composio_app_name)
        toolset = ComposioToolSet(api_key=settings.COMPOSIO_API_KEY, entity_id=user_id)
        request = toolset.initiate_connection(app=app_enum, redirect_url=callback_url)
        return {"connect_url": request.redirectUrl}
    except Exception as exc:
        logger.error(f"Composio connect failed for {body.toolkit}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Composio error: {exc}")


@router.get("/composio/callback")
async def composio_callback(
    toolkit: str,
    state: str,
    status: Optional[str] = None,
    connected_account_id: Optional[str] = None,
) -> Response:
    """Receive redirect from Composio after user completes OAuth.

    On success: record connection in user_tool_connections, redirect to frontend.
    On failure: redirect to frontend with error param.
    """
    if status != "success":
        _err = f"{toolkit}_composio_failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )
    try:
        user_id = _extract_user_from_state(state, f"composio_{toolkit}")
        # credentials JSON stores the Composio account ID (actual tokens live in Composio's cloud)
        credentials = json.dumps({"composio_account_id": connected_account_id or ""})
        _store_connection(user_id=user_id, tool_id=toolkit, credentials=credentials)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={quote(toolkit, safe='')}",
            status_code=302,
        )
    except Exception as exc:
        logger.error(f"Composio callback failed for {toolkit}: {exc}", exc_info=True)
        _err = f"{toolkit}_composio_failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )
```

Also **remove** the now-unused `authorize_tool` endpoint (`GET /{tool_id}/oauth/authorize`).

- [ ] **Step 4: Run the new tests**

```bash
pytest tests/test_composio_routes.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add routes/tool_marketplace.py tests/test_composio_routes.py
git commit -m "feat: POST /composio/connect + GET /composio/callback replace broken OAuth flow"
```

---

## Task 5: Frontend — Light Theme + Composio Connect Flow

**Files:**
- Modify: `frontend/components/CatalogueCard.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/dashboard/integrations/page.tsx`

- [ ] **Step 1: Fix `CatalogueCard.tsx` — light theme**

Replace the entire contents of `frontend/components/CatalogueCard.tsx` with:

```tsx
'use client'

import { ToolDefinition } from '@/lib/api'

interface Props {
  tool: ToolDefinition
  isConnected: boolean
  onConnect: (toolId: string) => void
  onDisconnect: (toolId: string) => void
}

export function CatalogueCard({ tool, isConnected, onConnect, onDisconnect }: Props) {
  return (
    <div
      className="flex items-center justify-between rounded-2xl p-4 transition-all"
      style={{
        background: isConnected ? 'linear-gradient(135deg, #f0f7f2 0%, #f9fff9 100%)' : '#ffffff',
        border: isConnected ? '1px solid #c8e6d3' : '1px solid #e4dee7',
      }}
    >
      {/* Left: icon + info */}
      <div className="flex items-center gap-3 min-w-0">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: '#f5f2ef', border: '1px solid rgba(0,0,0,0.08)' }}
        >
          {tool.icon_url ? (
            <img src={tool.icon_url} alt={tool.name} className="w-6 h-6 rounded" />
          ) : (
            <span className="text-sm font-semibold" style={{ color: '#695e6e' }}>
              {tool.name[0]}
            </span>
          )}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate" style={{ color: '#1c1520' }}>
            {tool.name}
          </p>
          <p className="text-xs truncate" style={{ color: '#695e6e' }}>
            {tool.description}
          </p>
        </div>
      </div>

      {/* Right: action button */}
      <div className="shrink-0 ml-3">
        {isConnected ? (
          <button
            onClick={() => onDisconnect(tool.id)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
            style={{
              background: 'rgba(176,74,58,0.07)',
              border: '1px solid rgba(176,74,58,0.2)',
              color: '#B04A3A',
            }}
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={() => onConnect(tool.id)}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
            style={{ background: '#4A7C59', color: '#ffffff' }}
          >
            + Connect
          </button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add `connectComposio` to `frontend/lib/api.ts`**

In `frontend/lib/api.ts`, find the `toolMarketplaceApi` object (around line 1092) and replace `getAuthUrl` with `connectComposio`:

Old:
```typescript
  getAuthUrl: async (toolId: string): Promise<string> => {
    const data = await apiRequest<{ auth_url: string }>(`/api/tools/${toolId}/oauth/authorize`)
    return data.auth_url
  },
```

New:
```typescript
  connectComposio: async (toolkit: string): Promise<string> => {
    const data = await apiRequest<{ connect_url: string }>('/api/tools/composio/connect', {
      method: 'POST',
      body: JSON.stringify({ toolkit }),
    })
    return data.connect_url
  },
```

- [ ] **Step 3: Update `handleConnectTool` in `integrations/page.tsx`**

Find `handleConnectTool` (around line 276) and replace it:

Old:
```typescript
  async function handleConnectTool(toolId: string) {
    try {
      const url = await toolMarketplaceApi.getAuthUrl(toolId)
      if (url) window.location.href = url
    } catch (e) {
      console.error('Failed to get auth URL', e)
    }
  }
```

New:
```typescript
  async function handleConnectTool(toolId: string) {
    try {
      const url = await toolMarketplaceApi.connectComposio(toolId)
      if (url) window.location.href = url
    } catch (e) {
      console.error('[Marketplace] Failed to start Composio connect', e)
      const label = catalogue.find((t) => t.id === toolId)?.name ?? toolId
      setErrorFlash(`Could not start ${label} connection. Check that COMPOSIO_API_KEY is configured.`)
      setTimeout(() => setErrorFlash(null), 6000)
    }
  }
```

- [ ] **Step 4: Fix MCP section dark theme in `integrations/page.tsx`**

Find the `{/* Advanced / MCP */}` section (around line 537) and replace it:

Old:
```tsx
      {/* Advanced / MCP */}
      <div className="mt-6 border-t border-gray-800 pt-4">
        <button
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {showAdvanced ? 'Hide advanced options' : 'Show advanced options'}
        </button>
        {showAdvanced && (
          <div className="mt-3 rounded-lg border border-dashed border-gray-700 p-4">
            <p className="text-sm text-gray-400 mb-2">Connect any MCP server</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={mcpUrl}
                onChange={(e) => setMcpUrl(e.target.value)}
                placeholder="https://my-mcp-server.com/sse"
                className="flex-1 rounded bg-gray-800 px-3 py-2 text-sm text-white border border-gray-700 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={handleConnectMcp}
                disabled={mcpConnecting || !mcpUrl.trim()}
                className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {mcpConnecting ? '...' : 'Connect'}
              </button>
            </div>
          </div>
        )}
      </div>
```

New:
```tsx
      {/* Advanced / MCP */}
      <div className="mt-6 pt-4" style={{ borderTop: '1px solid #e4dee7' }}>
        <button
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-xs transition-colors"
          style={{ color: '#9e9e9e' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = '#695e6e')}
          onMouseLeave={(e) => (e.currentTarget.style.color = '#9e9e9e')}
        >
          {showAdvanced ? 'Hide advanced options' : 'Advanced — connect a custom MCP server'}
        </button>
        {showAdvanced && (
          <div
            className="mt-3 rounded-xl p-4"
            style={{ border: '1px dashed #d4cdd8', background: '#faf8fb' }}
          >
            <p className="text-sm font-medium mb-1" style={{ color: '#1c1520' }}>
              Custom MCP Server
            </p>
            <p className="text-xs mb-3" style={{ color: '#695e6e' }}>
              Connect any Model Context Protocol server via its SSE endpoint URL.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={mcpUrl}
                onChange={(e) => setMcpUrl(e.target.value)}
                placeholder="https://my-mcp-server.com/sse"
                className="flex-1 rounded-lg px-3 py-2 text-sm focus:outline-none"
                style={{
                  background: '#ffffff',
                  border: '1px solid #d4cdd8',
                  color: '#1c1520',
                }}
              />
              <button
                onClick={handleConnectMcp}
                disabled={mcpConnecting || !mcpUrl.trim()}
                className="rounded-xl px-4 py-2 text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40"
                style={{ background: '#4A7C59', color: '#ffffff' }}
              >
                {mcpConnecting ? '…' : 'Connect'}
              </button>
            </div>
          </div>
        )}
      </div>
```

- [ ] **Step 5: Verify frontend compiles**

```bash
cd frontend
npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` (or no TypeScript errors on the changed files).

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/components/CatalogueCard.tsx frontend/lib/api.ts \
        frontend/app/dashboard/integrations/page.tsx
git commit -m "feat: marketplace UI — light theme, Composio connect flow, fixed MCP section"
```

---

## Task 6: Delete Dead Connector Files + Update Tests

**Files:**
- Delete: `backend/services/connectors/github.py`
- Delete: `backend/services/connectors/notion.py`
- Delete: `backend/services/connectors/slack_write.py`
- Modify: `backend/tests/test_connectors.py`
- Modify: `backend/tests/test_tool_marketplace_routes.py`

- [ ] **Step 1: Delete the three replaced connector files**

```bash
cd backend
git rm services/connectors/github.py
git rm services/connectors/notion.py
git rm services/connectors/slack_write.py
```

- [ ] **Step 2: Remove test classes for deleted connectors**

In `backend/tests/test_connectors.py`, remove any test class that imports from `github`, `notion`, or `slack_write`:

```python
# Remove any class like:
# from services.connectors.github import GitHubConnector   → DELETE
# from services.connectors.notion import NotionConnector   → DELETE
# from services.connectors.slack_write import SlackWriteConnector → DELETE
# class TestGitHubConnector: ...  → DELETE
# class TestNotionConnector: ...  → DELETE
# class TestSlackWriteConnector: ... → DELETE
```

- [ ] **Step 3: Update `test_tool_marketplace_routes.py` — replace broken authorize test**

In `backend/tests/test_tool_marketplace_routes.py`, find any test calling `GET /api/tools/{tool_id}/oauth/authorize` and replace it with a test for the new `POST /api/tools/composio/connect`:

```python
# Replace the old authorize test:
# def test_get_oauth_authorize_returns_url(...)  → DELETE

# Add:
def test_composio_connect_unknown_toolkit_returns_404(client, auth_headers):
    """Composio connect with an unknown toolkit name returns 404."""
    with patch("routes.tool_marketplace.get_current_user_id", return_value="user-123"), \
         patch("routes.tool_marketplace.settings") as mock_s:
        mock_s.COMPOSIO_API_KEY = "test-key"
        resp = client.post(
            "/api/tools/composio/connect",
            json={"toolkit": "notarealtool"},
            headers=auth_headers,
        )
    assert resp.status_code == 404
```

- [ ] **Step 4: Run full test suite to check nothing is broken**

```bash
cd backend
pytest tests/ -v --ignore=tests/test_composio_routes.py -x 2>&1 | tail -40
```

Expected: No new failures (the 2 pre-existing failures `test_context_manager_v2` and `test_v2_full_pipeline` with `KeyError: 0` are unrelated and pre-date this PR).

- [ ] **Step 5: Commit**

```bash
git add tests/test_connectors.py tests/test_tool_marketplace_routes.py
git commit -m "chore: remove replaced GitHub/Notion/SlackWrite connectors and stale tests"
```

---

## Task 7: Fernet Credential Encryption

**Context:** `cryptography>=46.0.5` is already in `requirements.txt` (verified). The `_encrypt_credentials()` in `routes/tool_marketplace.py` is a TODO stub that just JSON-serialises. Replace it with real Fernet symmetric encryption.

**Files:**
- Create: `backend/utils/encryption.py`
- Modify: `backend/routes/tool_marketplace.py` (swap stub for real functions)
- Modify: `backend/.env.example` (add ENCRYPTION_KEY placeholder)
- Modify: `backend/config.py` (add ENCRYPTION_KEY setting)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_encryption.py`:

```python
"""Tests for Fernet credential encryption."""
import json
import pytest
from unittest.mock import patch

from utils.encryption import encrypt_credentials, decrypt_credentials


class TestEncryption:
    def test_round_trip(self):
        """Encrypted then decrypted data matches original."""
        original = {"access_token": "tok_abc", "refresh_token": "ref_xyz"}
        encrypted = encrypt_credentials(original)
        assert isinstance(encrypted, str)
        assert "access_token" not in encrypted  # must not be plaintext

        recovered = decrypt_credentials(encrypted)
        assert recovered == original

    def test_different_calls_produce_different_ciphertext(self):
        """Fernet adds random IV — same input produces different output each time."""
        data = {"key": "value"}
        c1 = encrypt_credentials(data)
        c2 = encrypt_credentials(data)
        assert c1 != c2  # random IV → different ciphertext

    def test_decrypt_invalid_raises_value_error(self):
        with pytest.raises(ValueError, match="decrypt"):
            decrypt_credentials("not-valid-base64-ciphertext")

    def test_encrypt_returns_string(self):
        result = encrypt_credentials({"x": 1})
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_encryption.py -v
```

Expected: `ImportError: cannot import name 'encrypt_credentials'`

- [ ] **Step 3: Add ENCRYPTION_KEY to config and .env.example**

In `backend/config.py`, add after `SECRET_KEY`:
```python
    # Fernet symmetric encryption key for stored credentials.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""
```

In `backend/.env.example`, add:
```
# Fernet key for credential encryption (generate once, never rotate in production without migration)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=
```

- [ ] **Step 4: Create `utils/encryption.py`**

```python
"""
Fernet symmetric encryption for credential storage.

Credentials stored in user_tool_connections.credentials are encrypted with the
ENCRYPTION_KEY Fernet key. Without the key, stored blobs are unreadable.

Usage:
    from utils.encryption import encrypt_credentials, decrypt_credentials

    stored = encrypt_credentials({"access_token": "tok_abc"})
    recovered = decrypt_credentials(stored)
"""
from __future__ import annotations

import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger(__name__)

# Lazy singleton — Fernet instance created once per process
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            # Dev-mode fallback: generate an ephemeral key (tokens won't survive restarts)
            logger.warning(
                "ENCRYPTION_KEY not set — generating ephemeral key. "
                "Credentials will be lost on restart. Set ENCRYPTION_KEY in .env."
            )
            key = Fernet.generate_key().decode()
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt a credentials dict to a Fernet token string (URL-safe base64).

    The returned string is safe to store in a TEXT / JSONB column.
    """
    plaintext = json.dumps(credentials).encode()
    return _get_fernet().encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt a Fernet token string back to the credentials dict.

    Raises:
        ValueError: If the token is invalid, expired, or was encrypted with a different key.
    """
    try:
        plaintext = _get_fernet().decrypt(encrypted.encode())
        return json.loads(plaintext)
    except (InvalidToken, Exception) as exc:
        raise ValueError(f"Failed to decrypt credentials: {exc}") from exc
```

- [ ] **Step 5: Swap the TODO stub in `routes/tool_marketplace.py`**

Find the `_encrypt_credentials` function (around line 260) and replace it:

Old:
```python
def _encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials before storage.

    TODO: Replace with proper encryption ...
    """
    logger.warning(
        "Credentials stored without encryption — implement encrypt_token() in utils/"
    )
    return json.dumps(credentials)
```

New:
```python
def _encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials with Fernet before storage."""
    from utils.encryption import encrypt_credentials
    return encrypt_credentials(credentials)
```

Also update `_store_connection` callers to decrypt when reading credentials. In `services/tool_registry.py` the only caller that reads credentials is now gone (Composio manages tokens). The `_store_connection` path in `routes/tool_marketplace.py` writes, and no code path reads them back anymore. The Composio flow stores `{"composio_account_id": "ca_xxx"}` — harmless if encrypted.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_encryption.py -v
```

Expected: `4 passed`

- [ ] **Step 7: Generate a real key and add to .env**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output into `backend/.env`:
```
ENCRYPTION_KEY=<paste-key-here>
```

- [ ] **Step 8: Commit**

```bash
git add utils/encryption.py tests/test_encryption.py config.py .env.example routes/tool_marketplace.py
git commit -m "feat: Fernet credential encryption — replace plaintext TODO stub"
```

---

## Task 8: PostgreSQL Connection Pooling

**Context:** Every call to `get_db_connection()` currently opens a fresh TCP connection to Postgres. At any meaningful load this is 40-80ms overhead per request. `psycopg[binary,pool]` is already in requirements (after Task 1). We add a `ConnectionPool` singleton that lives for the lifetime of the FastAPI process.

**Files:**
- Modify: `backend/utils/db.py`
- Modify: `backend/main.py` (open/close pool in lifespan)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_schema.py` (or create `backend/tests/test_db_pool.py`):

```python
"""Test that get_db_connection returns a working pooled connection."""
import pytest
from unittest.mock import patch, MagicMock

from utils.db import get_db_connection


class TestDbPool:
    def test_get_db_connection_yields_connection(self):
        """Context manager must yield something with a cursor() method."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)

        with patch("utils.db._pool", mock_pool):
            with get_db_connection() as conn:
                assert conn is mock_conn
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_db_pool.py -v
```

Expected: `AssertionError` or attribute error (pool not yet wired).

- [ ] **Step 3: Replace `backend/utils/db.py`**

Replace the entire contents of `backend/utils/db.py` with:

```python
"""
PostgreSQL connection management — psycopg3 pool.

A singleton ConnectionPool is created during FastAPI lifespan (main.py calls
`open_pool()` on startup, `close_pool()` on shutdown). All DB access uses
`get_db_connection()` which checks out a connection from the pool rather than
opening a new TCP connection per request.

Usage:
    from utils.db import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def open_pool() -> None:
    """Create the connection pool. Call once in FastAPI lifespan startup."""
    global _pool
    if _pool is not None:
        return  # Already open (e.g. called twice in tests)
    _pool = ConnectionPool(
        conninfo=settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    logger.info("PostgreSQL connection pool opened (min=2, max=10)")


def close_pool() -> None:
    """Close the connection pool. Call once in FastAPI lifespan shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed")


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Check out a connection from the pool; auto-commit or rollback on exit.

    Raises RuntimeError if the pool has not been opened yet.
    Falls back to a direct connection if the pool is None (useful in tests
    that don't call open_pool).
    """
    global _pool
    if _pool is None:
        # Direct connection fallback for tests / scripts that don't use lifespan
        logger.debug("Pool not open — opening direct connection")
        conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    with _pool.connection() as conn:
        yield conn
```

- [ ] **Step 4: Wire pool open/close into `main.py` lifespan**

In `backend/main.py`, find the lifespan context manager (it starts with `@asynccontextmanager` and `async def lifespan`). Add pool open/close calls:

```python
from utils.db import open_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    open_pool()          # ← ADD THIS LINE
    # ... existing startup code (scheduler, weaviate, etc.) ...
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────
    close_pool()         # ← ADD THIS LINE
    # ... existing shutdown code ...
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_db_pool.py -v
```

Expected: `1 passed`

- [ ] **Step 6: Smoke test the server starts cleanly**

```bash
cd backend
python main.py &
sleep 3
curl -s http://localhost:8000/health | python -m json.tool
kill %1
```

Expected: `{"status": "ok"}` (no pool errors in logs).

- [ ] **Step 7: Commit**

```bash
git add utils/db.py main.py tests/test_db_pool.py
git commit -m "perf: psycopg ConnectionPool — replace per-request TCP connections"
```

---

## Task 9: Typed Error Hierarchy

**Context:** Routes currently raise bare `HTTPException(500, str(e))` which leaks stack traces to clients and makes monitoring noisy. A small exception hierarchy lets you `raise IntegrationError("Composio down")` and have FastAPI return a clean 502 — no `str(e)` in routes.

**Files:**
- Create: `backend/utils/errors.py`
- Modify: `backend/main.py` (register exception handler)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_errors.py`:

```python
"""Tests for the typed error hierarchy and FastAPI handler."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from utils.errors import (
    IntegrationError,
    DBError,
    AuthError,
    ESLError,
    register_error_handlers,
)


@pytest.fixture
def app_with_handlers():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/integration-error")
    def raise_integration():
        raise IntegrationError("Composio is down")

    @app.get("/db-error")
    def raise_db():
        raise DBError("Connection refused")

    @app.get("/auth-error")
    def raise_auth():
        raise AuthError("Token expired")

    @app.get("/esl-error")
    def raise_esl():
        raise ESLError("Action vetoed")

    return TestClient(app)


class TestErrorHandlers:
    def test_integration_error_returns_502(self, app_with_handlers):
        resp = app_with_handlers.get("/integration-error")
        assert resp.status_code == 502
        assert resp.json()["error"] == "integration_error"
        assert "Composio is down" in resp.json()["detail"]

    def test_db_error_returns_503(self, app_with_handlers):
        resp = app_with_handlers.get("/db-error")
        assert resp.status_code == 503
        assert resp.json()["error"] == "db_error"

    def test_auth_error_returns_401(self, app_with_handlers):
        resp = app_with_handlers.get("/auth-error")
        assert resp.status_code == 401

    def test_esl_error_returns_403(self, app_with_handlers):
        resp = app_with_handlers.get("/esl-error")
        assert resp.status_code == 403
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_errors.py -v
```

Expected: `ImportError: cannot import name 'IntegrationError'`

- [ ] **Step 3: Create `utils/errors.py`**

```python
"""
Typed exception hierarchy for Ethic Companion.

Raise a typed exception in any route or service; the FastAPI handler (registered
via register_error_handlers) maps it to the correct HTTP status code with a clean
JSON body — no stack traces leak to clients.

Usage:
    from utils.errors import IntegrationError
    raise IntegrationError("Composio returned 503")

    # FastAPI returns:
    # HTTP 502 {"error": "integration_error", "detail": "Composio returned 503"}
"""
from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class EthicCompanionError(Exception):
    """Base class for all typed application errors."""
    http_status: int = 500
    error_code: str = "internal_error"

    def __init__(self, detail: str = "An unexpected error occurred."):
        super().__init__(detail)
        self.detail = detail


class IntegrationError(EthicCompanionError):
    """External service (Composio, GitHub, Notion, etc.) returned an error."""
    http_status = 502
    error_code = "integration_error"


class DBError(EthicCompanionError):
    """Database query or connection failure."""
    http_status = 503
    error_code = "db_error"


class AuthError(EthicCompanionError):
    """Authentication or authorisation failure."""
    http_status = 401
    error_code = "auth_error"


class ESLError(EthicCompanionError):
    """ESL vetoed the requested action."""
    http_status = 403
    error_code = "esl_error"


class ValidationError(EthicCompanionError):
    """Input failed validation (beyond Pydantic — business-rule level)."""
    http_status = 422
    error_code = "validation_error"


def register_error_handlers(app: FastAPI) -> None:
    """Register typed exception handlers on a FastAPI app instance."""

    @app.exception_handler(EthicCompanionError)
    async def handle_ethic_companion_error(
        request: Request, exc: EthicCompanionError
    ) -> JSONResponse:
        # Log at WARNING for client errors (4xx), ERROR for server errors (5xx)
        log_fn = logger.error if exc.http_status >= 500 else logger.warning
        log_fn(
            f"{exc.__class__.__name__} on {request.method} {request.url.path}: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )
```

- [ ] **Step 4: Register in `main.py`**

In `backend/main.py`, after `app = FastAPI(...)`, add:

```python
from utils.errors import register_error_handlers
register_error_handlers(app)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_errors.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit everything**

```bash
git add utils/errors.py tests/test_errors.py main.py
git commit -m "feat: typed error hierarchy — IntegrationError/DBError/AuthError/ESLError + FastAPI handler"
```

---

## Infrastructure Roadmap (Document Only — Not Implemented Here)

These are the next recommended investments, in priority order. Each warrants its own plan.

### 🔴 High Priority (next sprint)

| Item | What | Why |
|---|---|---|
| **Redis caching** | Cache `context_manager.get_user_context()` (5-min TTL), Weaviate semantic queries | Context queries make 4-5 sequential DB calls per chat turn |
| **Per-user token rate limiting** | Redis sliding-window keyed by `user_id + endpoint`, daily token budget cap | Prevent runaway LLM costs from single users |
| **Supabase asymmetric JWT signing** | Switch from `HS256` shared secret to RS256 signing keys | Supabase now flags shared secret as a security vulnerability |
| **Langfuse full wiring** | Add `LangfuseCallbackHandler` to every LangGraph `.invoke()` call | Already configured in `.env`, never actually used — free tracing |

### 🟡 Medium Priority (Q2)

| Item | What | Why |
|---|---|---|
| **Nango for enterprise auth** | Migrate OAuth token storage to Nango (SOC-2 Type II, HIPAA) | Composio's free/paid tiers store tokens on their cloud — not enterprise-compliant |
| **ContextManager decomposition** | Split 742-line file into `ContextQueryService` + `ContextStorageService` | Single largest coupling point; 22 public methods in one class |
| **LangGraph RetryPolicy** | Add `retry=RetryPolicy(max_attempts=3)` to tool_execution node | Transient Composio/network errors currently fail silently |
| **Token refresh for data sources** | Retry once before disabling connector in scheduler | Scheduler disables on first sync failure — may be a temporary network blip |

### 🟢 Long-term (Q3+)

| Item | What | Why |
|---|---|---|
| **Qdrant upgrade** | Replace Weaviate with Qdrant when vectors > 5M | Weaviate requires K8s ops; Qdrant simpler, faster at scale |
| **Vertex AI Agent Engine** | Managed LangGraph runtime on GCP | Removes Cloud Run cold starts, adds managed checkpointing |
| **Cloud Run `min-instances: 1`** | Add to GCP deployment config | Eliminates 5-10s cold starts in production |
| **E2E test suite** | `test_e2e_chat_full_flow.py` with real graph + test DB | Currently no end-to-end test; only mocked unit tests |

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Composio replaces GitHub, Notion, SlackWrite connectors
- ✅ ESL gate untouched — still runs before every tool execution
- ✅ Data-sync connectors (Gmail, GCal, Slack read) untouched
- ✅ MCP path preserved
- ✅ Credential encryption (Fernet, was TODO)
- ✅ Connection pooling (was creating new conn per request)
- ✅ Typed errors (was leaking exceptions as 500s)
- ✅ CatalogueCard dark theme → light theme
- ✅ MCP section dark theme → light theme
- ✅ Connect button calls Composio, not broken old OAuth
- ✅ Composio connect/callback endpoints tested

**Placeholder scan:** No TBD, TODO, or "similar to Task N" patterns present.

**Type consistency:**
- `get_composio_tools_for_user(user_id: str, connected_tool_ids: set[str])` — consistent across Task 2 and Task 3
- `encrypt_credentials(dict) → str` / `decrypt_credentials(str) → dict` — consistent across Task 7
- `open_pool()` / `close_pool()` / `get_db_connection()` — consistent across Task 8 and main.py
- `register_error_handlers(app: FastAPI)` — consistent across Task 9 and main.py
