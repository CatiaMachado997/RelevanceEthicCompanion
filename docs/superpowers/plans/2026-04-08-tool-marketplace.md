# Tool Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dynamic tool marketplace to Ethic Companion so users can connect external tools (Notion, Slack, GitHub, Google Calendar write, Gmail write) and EC can read from and act on those tools — with every write action gated through the ESL progressive trust model.

**Architecture:** Three new DB tables (`tool_definitions`, `user_tool_connections`, `tool_permissions`) feed a `ToolRegistry` service that dynamically builds LangChain tool instances per user. A new `ESLToolGate` checks trust before any write action, prompting once per action type and remembering the answer. A new `/api/tools` route handles connect/disconnect/OAuth/MCP/permissions. The LangGraph `tool_execution_node` is extended to call the gate before executing writes.

**Tech Stack:** FastAPI, psycopg3 (dict_row), LangGraph, LangChain BaseTool, MCP SSE protocol (mcp Python SDK), Groq, Next.js 14 TypeScript frontend.

---

## File Map

### New backend files
| File | Responsibility |
|---|---|
| `backend/database/migration_tool_marketplace.sql` | Adds `tool_definitions`, `user_tool_connections`, `tool_permissions` tables + seeds catalogue |
| `backend/services/tool_registry.py` | Loads active tools per user from DB; returns LangChain tool instances |
| `backend/esl/tool_gate.py` | Pre-execution trust check; returns APPROVED / PENDING_CONFIRMATION / VETOED |
| `backend/services/connectors/notion.py` | Notion OAuth connector + read/write actions |
| `backend/services/connectors/github.py` | GitHub OAuth connector + read/write actions |
| `backend/services/connectors/slack_write.py` | Extends Slack connector with send_message write action |
| `backend/services/mcp_client.py` | Connects to an MCP server URL; wraps discovered tools as LangChain tools |
| `backend/routes/tool_marketplace.py` | REST API: catalogue, connect, disconnect, OAuth, permissions, MCP |
| `backend/tests/test_tool_registry.py` | Unit tests for dynamic tool loading |
| `backend/tests/test_tool_gate.py` | Unit tests for all trust/veto/high-risk scenarios |
| `backend/tests/test_tool_marketplace_routes.py` | Integration tests for connect/disconnect/permissions routes |

### Modified backend files
| File | Change |
|---|---|
| `backend/services/langchain_tools.py` | `create_langchain_tools()` merges registry tools with built-ins |
| `backend/orchestrator/nodes/tools.py` | `tool_execution_node` calls `ESLToolGate.check()` before write tools; writes audit log |
| `backend/orchestrator/state.py` | Add `pending_tool_confirmation: Optional[dict]` field |
| `backend/main.py` | Register new router |
| `backend/services/connectors/google_calendar.py` | Add `execute_action()` for `create_event`, `update_event` |
| `backend/services/connectors/gmail.py` | Add `execute_action()` for `create_draft`, `send_reply` |
| `backend/routes/chat.py` | Handle `pending_tool_confirmation` SSE event in stream |

### New frontend files
| File | Responsibility |
|---|---|
| `frontend/components/CatalogueCard.tsx` | Single tool card in the integrations catalogue |
| `frontend/components/ToolConfirmation.tsx` | ESL confirmation card shown in chat stream |

### Modified frontend files
| File | Change |
|---|---|
| `frontend/lib/api.ts` | Add `toolMarketplaceApi` |
| `frontend/app/dashboard/integrations/page.tsx` | Add catalogue grid, trust badges, "Show advanced" MCP toggle |
| `frontend/app/dashboard/chat/page.tsx` or chat component | Render `ToolConfirmation` when SSE sends `tool_pending_confirmation` event |

---

## Task 1: DB migration + catalogue seed

**Files:**
- Create: `backend/database/migration_tool_marketplace.sql`

- [ ] **Step 1: Write the migration**

Create `backend/database/migration_tool_marketplace.sql` with this exact content:

```sql
-- Tool Marketplace migration

CREATE TABLE IF NOT EXISTS tool_definitions (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    auth_type     TEXT NOT NULL CHECK (auth_type IN ('oauth', 'apikey', 'mcp')),
    oauth_scopes  TEXT[] DEFAULT '{}',
    actions       JSONB NOT NULL DEFAULT '[]',
    icon_url      TEXT,
    enabled       BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_tool_connections (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id        TEXT NOT NULL REFERENCES tool_definitions(id),
    enabled        BOOLEAN DEFAULT true,
    credentials    JSONB DEFAULT '{}',
    mcp_url        TEXT,
    connected_at   TIMESTAMPTZ DEFAULT now(),
    last_used_at   TIMESTAMPTZ,
    UNIQUE (user_id, tool_id)
);

CREATE TABLE IF NOT EXISTS tool_permissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id      TEXT NOT NULL,
    action_name  TEXT NOT NULL,
    trust_level  TEXT NOT NULL CHECK (trust_level IN ('ask', 'allow', 'deny')),
    granted_at   TIMESTAMPTZ DEFAULT now(),
    expires_at   TIMESTAMPTZ,
    UNIQUE (user_id, tool_id, action_name)
);

-- Seed catalogue
INSERT INTO tool_definitions (id, name, description, auth_type, oauth_scopes, actions, icon_url) VALUES
(
    'google_calendar_write',
    'Google Calendar',
    'Read and create calendar events',
    'oauth',
    ARRAY['https://www.googleapis.com/auth/calendar'],
    '[
        {"name": "create_event", "description": "Create a calendar event", "risk_level": "low"},
        {"name": "update_event", "description": "Update an existing event", "risk_level": "medium"}
    ]'::jsonb,
    '/icons/google-calendar.svg'
),
(
    'gmail_write',
    'Gmail',
    'Read emails and send replies',
    'oauth',
    ARRAY['https://www.googleapis.com/auth/gmail.send'],
    '[
        {"name": "create_draft", "description": "Create an email draft", "risk_level": "low"},
        {"name": "send_reply", "description": "Send an email reply", "risk_level": "high"}
    ]'::jsonb,
    '/icons/gmail.svg'
),
(
    'notion',
    'Notion',
    'Read pages and databases, create notes',
    'oauth',
    ARRAY[''],
    '[
        {"name": "search_pages", "description": "Search Notion pages", "risk_level": "low"},
        {"name": "create_page", "description": "Create a Notion page", "risk_level": "medium"},
        {"name": "append_block", "description": "Append content to a page", "risk_level": "low"}
    ]'::jsonb,
    '/icons/notion.svg'
),
(
    'slack',
    'Slack',
    'Read messages and send replies',
    'oauth',
    ARRAY['channels:read', 'chat:write'],
    '[
        {"name": "read_channel", "description": "Read recent messages from a channel", "risk_level": "low"},
        {"name": "send_message", "description": "Send a message to a channel", "risk_level": "high"}
    ]'::jsonb,
    '/icons/slack.svg'
),
(
    'github',
    'GitHub',
    'Read issues and PRs, create issues',
    'oauth',
    ARRAY['repo', 'read:user'],
    '[
        {"name": "list_issues", "description": "List open issues in a repo", "risk_level": "low"},
        {"name": "create_issue", "description": "Create a GitHub issue", "risk_level": "medium"},
        {"name": "add_comment", "description": "Add a comment to an issue or PR", "risk_level": "medium"}
    ]'::jsonb,
    '/icons/github.svg'
),
(
    'mcp_custom',
    'Custom MCP Server',
    'Connect any Model Context Protocol server',
    'mcp',
    ARRAY[]::TEXT[],
    '[]'::jsonb,
    '/icons/mcp.svg'
)
ON CONFLICT (id) DO NOTHING;
```

- [ ] **Step 2: Apply the migration**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
docker compose exec -T db psql -U postgres -d ethic_companion -f /dev/stdin < database/migration_tool_marketplace.sql
```

Expected output ends with `INSERT 0 6` (or `INSERT 0 0` if re-run).

- [ ] **Step 3: Verify tables and seed data**

```bash
docker compose exec -T db psql -U postgres -d ethic_companion -c \
  "SELECT id, name, auth_type FROM tool_definitions ORDER BY id;"
```

Expected: 6 rows (github, gmail_write, google_calendar_write, mcp_custom, notion, slack).

- [ ] **Step 4: Commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion
git add backend/database/migration_tool_marketplace.sql
git commit -m "feat: add tool marketplace DB migration and catalogue seed"
```

---

## Task 2: ToolRegistry service

**Files:**
- Create: `backend/services/tool_registry.py`
- Create: `backend/tests/test_tool_registry.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_tool_registry.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def _make_connection_row(tool_id, mcp_url=None):
    return {
        "tool_id": tool_id,
        "enabled": True,
        "credentials": {"access_token": "tok"},
        "mcp_url": mcp_url,
    }


def _make_definition_row(tool_id, actions=None, auth_type="oauth"):
    return {
        "id": tool_id,
        "name": tool_id.capitalize(),
        "description": "A tool",
        "auth_type": auth_type,
        "actions": actions or [{"name": "read", "description": "Read", "risk_level": "low"}],
    }


@pytest.mark.asyncio
async def test_get_tools_for_user_returns_only_connected():
    """Only tools with active user_tool_connections are returned."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Only github is connected
        cur.fetchall.side_effect = [
            [_make_connection_row("github")],  # user_tool_connections query
            [_make_definition_row("github")],  # tool_definitions query
        ]
        mock_db.return_value = conn

        tools = await registry.get_tools_for_user("user-1")

    assert len(tools) == 1
    assert tools[0].name == "github__list_issues" or "github" in tools[0].name


@pytest.mark.asyncio
async def test_get_tools_for_user_empty_when_none_connected():
    """Returns [] when user has no tool connections."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = []
        mock_db.return_value = conn

        tools = await registry.get_tools_for_user("user-1")

    assert tools == []


@pytest.mark.asyncio
async def test_get_tools_returns_empty_on_db_error():
    """Returns [] gracefully when DB is unavailable."""
    from services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("services.tool_registry.get_db_connection", side_effect=Exception("DB down")):
        tools = await registry.get_tools_for_user("user-1")

    assert tools == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest tests/test_tool_registry.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'ToolRegistry'`

- [ ] **Step 3: Implement ToolRegistry**

Create `backend/services/tool_registry.py`:

```python
"""
ToolRegistry — dynamic tool loader.

Reads user_tool_connections + tool_definitions from DB and returns
ready-to-invoke LangChain BaseTool instances for the orchestrator.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool as lc_tool
from pydantic import BaseModel, Field

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Load and instantiate connected tools for a given user."""

    async def get_tools_for_user(self, user_id: str) -> list[BaseTool]:
        """
        Return a list of LangChain BaseTool instances for all tools the user
        has connected. Returns [] on any DB error — never raises.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Fetch active connections
                    cur.execute(
                        """
                        SELECT utc.tool_id, utc.enabled, utc.credentials, utc.mcp_url
                        FROM user_tool_connections utc
                        WHERE utc.user_id = %s AND utc.enabled = TRUE
                        """,
                        (user_id,),
                    )
                    connections = cur.fetchall()

                    if not connections:
                        return []

                    tool_ids = [c["tool_id"] for c in connections]

                    # 2. Fetch definitions
                    cur.execute(
                        """
                        SELECT id, name, description, auth_type, actions
                        FROM tool_definitions
                        WHERE id = ANY(%s) AND enabled = TRUE
                        """,
                        (tool_ids,),
                    )
                    definitions = {row["id"]: row for row in cur.fetchall()}

            tools: list[BaseTool] = []
            conn_by_id = {c["tool_id"]: c for c in connections}

            for tool_id, defn in definitions.items():
                conn_row = conn_by_id[tool_id]
                credentials = conn_row.get("credentials") or {}
                mcp_url = conn_row.get("mcp_url")

                if defn["auth_type"] == "mcp" and mcp_url:
                    mcp_tools = await _load_mcp_tools(tool_id, mcp_url)
                    tools.extend(mcp_tools)
                else:
                    actions = defn.get("actions") or []
                    for action in actions:
                        t = _make_action_tool(
                            tool_id=tool_id,
                            tool_name=defn["name"],
                            action=action,
                            credentials=credentials,
                        )
                        if t:
                            tools.append(t)

            logger.debug(f"✅ ToolRegistry: {len(tools)} tools for user {user_id}")
            return tools

        except Exception as e:
            logger.warning(f"⚠️  ToolRegistry.get_tools_for_user failed: {e}")
            return []


def _make_action_tool(
    tool_id: str,
    tool_name: str,
    action: dict,
    credentials: dict,
) -> BaseTool | None:
    """
    Build a LangChain BaseTool for a single action on a catalogue tool.
    Returns None for unknown tool_id / action combos (forward-compatible).
    """
    action_name = action.get("name", "")
    description = action.get("description", action_name)
    risk_level = action.get("risk_level", "medium")
    unique_name = f"{tool_id}__{action_name}"

    class _DynamicInput(BaseModel):
        params: dict = Field(default_factory=dict, description="Action parameters as key-value pairs")

    class _DynamicTool(BaseTool):
        name: str = unique_name
        description: str = (
            f"{description}. "
            f"Tool: {tool_name}. Risk: {risk_level}. "
            "Pass parameters as a dict in the 'params' field."
        )
        args_schema: type[BaseModel] = _DynamicInput
        # Store metadata for ESL gate — accessed via tool.metadata
        metadata: dict = {
            "tool_id": tool_id,
            "action_name": action_name,
            "risk_level": risk_level,
            "credentials": credentials,
        }

        def _run(self, params: dict = None) -> str:  # type: ignore[override]
            raise NotImplementedError("Use async _arun")

        async def _arun(self, params: dict = None) -> str:  # type: ignore[override]
            return await _dispatch_action(
                tool_id=tool_id,
                action_name=action_name,
                params=params or {},
                credentials=credentials,
            )

    return _DynamicTool()


async def _dispatch_action(
    tool_id: str,
    action_name: str,
    params: dict,
    credentials: dict,
) -> str:
    """
    Route an action to the correct connector's execute_action().
    Connector modules are imported lazily to keep startup fast.
    """
    try:
        if tool_id in ("google_calendar_write",):
            from services.connectors.google_calendar import GoogleCalendarConnector
            connector = GoogleCalendarConnector()
        elif tool_id == "gmail_write":
            from services.connectors.gmail import GmailConnector
            connector = GmailConnector()
        elif tool_id == "notion":
            from services.connectors.notion import NotionConnector
            connector = NotionConnector()
        elif tool_id == "slack":
            from services.connectors.slack_write import SlackWriteConnector
            connector = SlackWriteConnector()
        elif tool_id == "github":
            from services.connectors.github import GitHubConnector
            connector = GitHubConnector()
        else:
            return f"Unknown tool: {tool_id}"

        return await connector.execute_action(action_name, params, credentials)
    except Exception as e:
        logger.error(f"Action dispatch failed {tool_id}/{action_name}: {e}")
        return f"Error executing {action_name}: {e}"


async def _load_mcp_tools(tool_id: str, mcp_url: str) -> list[BaseTool]:
    """Load tools from an MCP server URL. Returns [] on connection failure."""
    try:
        from services.mcp_client import MCPClient
        client = MCPClient(mcp_url)
        return await client.get_tools()
    except Exception as e:
        logger.warning(f"⚠️  MCP tool load failed for {tool_id} @ {mcp_url}: {e}")
        return []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tool_registry.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add services/tool_registry.py tests/test_tool_registry.py
git commit -m "feat: ToolRegistry — dynamic LangChain tool loader from user_tool_connections"
```

---

## Task 3: ESL Tool Gate

**Files:**
- Create: `backend/esl/tool_gate.py`
- Create: `backend/tests/test_tool_gate.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_tool_gate.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def _permission_row(trust_level: str):
    return {"trust_level": trust_level}


@pytest.mark.asyncio
async def test_ask_trust_returns_pending():
    """trust_level='ask' → PENDING_CONFIRMATION with preview."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None  # no record → ask by default
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1", tool_id="github", action_name="create_issue",
            risk_level="medium", preview="Create issue: Fix login bug"
        )

    assert result.status == GateResult.PENDING_CONFIRMATION
    assert "Fix login bug" in result.preview


@pytest.mark.asyncio
async def test_allow_trust_returns_approved():
    """trust_level='allow' and risk!='high' → APPROVED."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("allow")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1", tool_id="github", action_name="create_issue",
            risk_level="medium", preview="Create issue"
        )

    assert result.status == GateResult.APPROVED


@pytest.mark.asyncio
async def test_deny_trust_returns_vetoed():
    """trust_level='deny' → VETOED regardless of risk level."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("deny")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1", tool_id="github", action_name="create_issue",
            risk_level="medium", preview="Create issue"
        )

    assert result.status == GateResult.VETOED


@pytest.mark.asyncio
async def test_high_risk_always_pending_even_when_allowed():
    """risk_level='high' → PENDING_CONFIRMATION even when trust is 'allow'."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("allow")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1", tool_id="gmail_write", action_name="send_reply",
            risk_level="high", preview="Send email to alice@example.com"
        )

    assert result.status == GateResult.PENDING_CONFIRMATION


@pytest.mark.asyncio
async def test_low_risk_no_record_auto_approved():
    """risk_level='low' with no permission record → APPROVED (auto-approve low risk)."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None  # no record
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1", tool_id="notion", action_name="create_page",
            risk_level="low", preview="Create page: Meeting notes"
        )

    assert result.status == GateResult.APPROVED
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tool_gate.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'ESLToolGate'`

- [ ] **Step 3: Implement ESLToolGate**

Create `backend/esl/tool_gate.py`:

```python
"""
ESL Tool Gate — pre-execution trust check for marketplace write actions.

Rules:
  risk=low, no record  → APPROVED (auto-approve)
  risk=low|medium, record=allow → APPROVED
  risk=high, any record → PENDING_CONFIRMATION (always confirm)
  record=ask or no record (medium) → PENDING_CONFIRMATION
  record=deny → VETOED
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


class GateResult(str, Enum):
    APPROVED = "APPROVED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    VETOED = "VETOED"


@dataclass
class GateDecision:
    status: GateResult
    preview: str = ""
    reason: str = ""


class ESLToolGate:
    """Check tool_permissions before executing a write action."""

    async def check(
        self,
        user_id: str,
        tool_id: str,
        action_name: str,
        risk_level: str,
        preview: str,
    ) -> GateDecision:
        """
        Returns a GateDecision. Never raises — returns PENDING_CONFIRMATION
        on any unexpected error so the user always stays in the loop.
        """
        try:
            trust = await self._get_trust(user_id, tool_id, action_name)

            # High-risk: always confirm regardless of stored trust
            if risk_level == "high":
                return GateDecision(
                    status=GateResult.PENDING_CONFIRMATION,
                    preview=preview,
                    reason="High-risk action always requires confirmation.",
                )

            # Explicit deny
            if trust == "deny":
                return GateDecision(
                    status=GateResult.VETOED,
                    reason=f"User has denied {tool_id}/{action_name}.",
                )

            # Low risk with no record or allow → auto-approve
            if risk_level == "low" and trust in ("allow", None):
                return GateDecision(status=GateResult.APPROVED)

            # Explicit allow (medium risk)
            if trust == "allow":
                return GateDecision(status=GateResult.APPROVED)

            # Default: ask (no record for medium, or record=ask)
            return GateDecision(
                status=GateResult.PENDING_CONFIRMATION,
                preview=preview,
                reason="First-time action — confirmation required.",
            )

        except Exception as e:
            logger.error(f"ESLToolGate.check error: {e}")
            return GateDecision(
                status=GateResult.PENDING_CONFIRMATION,
                preview=preview,
                reason="Gate check failed — defaulting to confirmation.",
            )

    async def _get_trust(
        self, user_id: str, tool_id: str, action_name: str
    ) -> str | None:
        """Return trust_level string or None if no record exists."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT trust_level FROM tool_permissions
                    WHERE user_id = %s AND tool_id = %s AND action_name = %s
                      AND (expires_at IS NULL OR expires_at > now())
                    """,
                    (user_id, tool_id, action_name),
                )
                row = cur.fetchone()
        return row["trust_level"] if row else None

    async def set_trust(
        self,
        user_id: str,
        tool_id: str,
        action_name: str,
        trust_level: str,
    ) -> None:
        """Upsert trust_level for a user/tool/action triple."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tool_permissions (user_id, tool_id, action_name, trust_level)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, tool_id, action_name)
                    DO UPDATE SET trust_level = EXCLUDED.trust_level, granted_at = now()
                    """,
                    (user_id, tool_id, action_name, trust_level),
                )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tool_gate.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add esl/tool_gate.py tests/test_tool_gate.py
git commit -m "feat: ESLToolGate — progressive trust check for marketplace write actions"
```

---

## Task 4: Marketplace routes

**Files:**
- Create: `backend/routes/tool_marketplace.py`
- Create: `backend/tests/test_tool_marketplace_routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_tool_marketplace_routes.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_get_catalogue_returns_tools(client):
    """GET /api/tools returns all enabled tool definitions."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = [
            {"id": "github", "name": "GitHub", "description": "Issues and PRs",
             "auth_type": "oauth", "actions": [], "icon_url": None, "enabled": True}
        ]
        mock_db.return_value = conn

        resp = client.get("/api/tools")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["id"] == "github"


def test_get_connected_returns_user_tools(client):
    """GET /api/tools/connected returns user's active connections."""
    with patch("routes.tool_marketplace.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = [
            {"tool_id": "github", "enabled": True, "connected_at": "2026-04-08T00:00:00+00:00",
             "last_used_at": None, "mcp_url": None,
             "name": "GitHub", "description": "Issues", "auth_type": "oauth",
             "actions": [], "icon_url": None}
        ]
        mock_db.return_value = conn

        resp = client.get("/api/tools/connected")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["tool_id"] == "github"


def test_set_permission_upserts_trust(client):
    """POST /api/tools/{tool_id}/permissions upserts trust_level."""
    with patch("routes.tool_marketplace.ESLToolGate") as MockGate:
        mock_gate = MagicMock()
        mock_gate.set_trust = AsyncMock()
        MockGate.return_value = mock_gate

        resp = client.post(
            "/api/tools/github/permissions",
            json={"action_name": "create_issue", "trust_level": "allow"}
        )

    assert resp.status_code == 200
    mock_gate.set_trust.assert_called_once()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_tool_marketplace_routes.py -v 2>&1 | head -20
```

Expected: `ImportError` or 404s.

- [ ] **Step 3: Implement marketplace routes**

Create `backend/routes/tool_marketplace.py`:

```python
"""Tool Marketplace API routes."""
from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from utils.db import get_db_connection
from utils.oauth_state import create_signed_state, validate_signed_state
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.tool_gate import ESLToolGate
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tool-marketplace"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PermissionRequest(BaseModel):
    action_name: str
    trust_level: str  # 'ask' | 'allow' | 'deny'


class MCPConnectRequest(BaseModel):
    mcp_url: str
    name: Optional[str] = "Custom MCP"


# ─── Catalogue ────────────────────────────────────────────────────────────────

@router.get("")
async def get_catalogue(
    user_id: str = Depends(get_current_read_user_id),
):
    """Return all enabled tool definitions (the marketplace catalogue)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, auth_type, actions, icon_url, enabled "
                "FROM tool_definitions WHERE enabled = TRUE ORDER BY name"
            )
            rows = cur.fetchall()
    return rows


@router.get("/connected")
async def get_connected_tools(
    user_id: str = Depends(get_current_read_user_id),
):
    """Return tools the user has connected with their status."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT utc.tool_id, utc.enabled, utc.connected_at, utc.last_used_at, utc.mcp_url,
                       td.name, td.description, td.auth_type, td.actions, td.icon_url
                FROM user_tool_connections utc
                JOIN tool_definitions td ON td.id = utc.tool_id
                WHERE utc.user_id = %s
                ORDER BY utc.connected_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return rows


# ─── OAuth connect flow ───────────────────────────────────────────────────────

@router.get("/oauth/{tool_id}/authorize")
async def authorize_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Generate OAuth authorization URL for a catalogue tool."""
    connector = _get_connector(tool_id)
    oauth_state = create_signed_state(user_id=user_id, source_type=tool_id)
    auth_url = connector.get_authorization_url(user_id=user_id, state=oauth_state)
    return {"auth_url": auth_url}


@router.get("/oauth/{tool_id}/callback")
async def oauth_callback(
    tool_id: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Handle OAuth callback — exchange code and store tokens."""
    if error or not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={tool_id}_{error or 'denied'}",
            status_code=302,
        )
    try:
        user_id = validate_signed_state(state=state, expected_source_type=tool_id)
        connector = _get_connector(tool_id)
        tokens = connector.exchange_code_for_tokens(code)
        _store_connection(user_id=user_id, tool_id=tool_id, credentials=tokens)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={tool_id}",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"OAuth callback failed for {tool_id}: {e}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={tool_id}_failed",
            status_code=302,
        )


# ─── Disconnect ───────────────────────────────────────────────────────────────

@router.delete("/{tool_id}")
async def disconnect_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Remove a tool connection and its permissions."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_tool_connections WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id),
            )
            cur.execute(
                "DELETE FROM tool_permissions WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id),
            )
    return {"success": True}


# ─── Permissions (trust management) ──────────────────────────────────────────

@router.post("/{tool_id}/permissions")
async def set_permission(
    tool_id: str,
    body: PermissionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Set trust level for a specific action on a tool."""
    if body.trust_level not in ("ask", "allow", "deny"):
        raise HTTPException(status_code=422, detail="trust_level must be ask|allow|deny")
    gate = ESLToolGate()
    await gate.set_trust(
        user_id=user_id,
        tool_id=tool_id,
        action_name=body.action_name,
        trust_level=body.trust_level,
    )
    return {"success": True}


@router.delete("/{tool_id}/permissions/{action_name}")
async def revoke_permission(
    tool_id: str,
    action_name: str,
    user_id: str = Depends(get_current_user_id),
):
    """Revoke stored trust for a specific action (resets to 'ask')."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tool_permissions WHERE user_id=%s AND tool_id=%s AND action_name=%s",
                (user_id, tool_id, action_name),
            )
    return {"success": True}


# ─── MCP ─────────────────────────────────────────────────────────────────────

@router.post("/mcp")
async def connect_mcp(
    body: MCPConnectRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Register an MCP server URL as a custom tool connection."""
    _store_connection(
        user_id=user_id,
        tool_id="mcp_custom",
        credentials={},
        mcp_url=body.mcp_url,
    )
    return {"success": True, "mcp_url": body.mcp_url}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _store_connection(
    user_id: str,
    tool_id: str,
    credentials: dict,
    mcp_url: str | None = None,
) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_tool_connections (user_id, tool_id, enabled, credentials, mcp_url)
                VALUES (%s, %s, TRUE, %s, %s)
                ON CONFLICT (user_id, tool_id)
                DO UPDATE SET enabled=TRUE, credentials=EXCLUDED.credentials,
                              mcp_url=EXCLUDED.mcp_url
                """,
                (user_id, tool_id, credentials, mcp_url),
            )


def _get_connector(tool_id: str):
    """Return the connector instance for a catalogue tool."""
    if tool_id == "notion":
        from services.connectors.notion import NotionConnector
        return NotionConnector()
    if tool_id == "github":
        from services.connectors.github import GitHubConnector
        return GitHubConnector()
    if tool_id == "slack":
        from services.connectors.slack_write import SlackWriteConnector
        return SlackWriteConnector()
    if tool_id == "google_calendar_write":
        from services.connectors.google_calendar import GoogleCalendarConnector
        return GoogleCalendarConnector()
    if tool_id == "gmail_write":
        from services.connectors.gmail import GmailConnector
        return GmailConnector()
    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_id}")
```

- [ ] **Step 4: Register router in main.py**

In `backend/main.py`, add after the last `app.include_router` line:

```python
from routes import tool_marketplace
app.include_router(tool_marketplace.router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_tool_marketplace_routes.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add routes/tool_marketplace.py tests/test_tool_marketplace_routes.py main.py
git commit -m "feat: tool marketplace routes — catalogue, connect, OAuth, permissions, MCP"
```

---

## Task 5: GitHub + Notion connectors

**Files:**
- Create: `backend/services/connectors/github.py`
- Create: `backend/services/connectors/notion.py`

- [ ] **Step 1: Implement GitHubConnector**

Create `backend/services/connectors/github.py`:

```python
"""GitHub connector — OAuth + read/write actions."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


class GitHubConnector(BaseConnector):
    source_type = "github"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        params = (
            f"client_id={settings.GITHUB_CLIENT_ID}"
            f"&scope=repo,read:user"
            f"&state={state or ''}"
        )
        return f"{GITHUB_AUTH_URL}?{params}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        resp = httpx.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,  # GitHub tokens don't expire by default
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch assigned open issues."""
        async with httpx.AsyncClient(headers=_gh_headers(access_token)) as client:
            resp = await client.get(
                f"{GITHUB_API}/issues",
                params={"filter": "assigned", "state": "open", "per_page": 30},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type="github",
            source_item_type="issue",
            external_id=str(raw.get("id", "")),
            title=raw.get("title", ""),
            body=raw.get("body", ""),
            item_at=raw.get("created_at"),
            metadata={
                "url": raw.get("html_url", ""),
                "repo": raw.get("repository_url", "").split("/")[-1],
                "number": raw.get("number"),
                "state": raw.get("state", "open"),
            },
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        """Execute a write action."""
        token = credentials.get("access_token", "")
        if action_name == "list_issues":
            return await self._list_issues(token, params)
        if action_name == "create_issue":
            return await self._create_issue(token, params)
        if action_name == "add_comment":
            return await self._add_comment(token, params)
        return f"Unknown action: {action_name}"

    async def _list_issues(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        if not repo:
            return "Error: 'repo' parameter required (e.g. 'owner/repo')"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/issues",
                params={"state": "open", "per_page": 10},
                timeout=10,
            )
            resp.raise_for_status()
            issues = resp.json()
        if not issues:
            return f"No open issues in {repo}."
        lines = [f"#{i['number']}: {i['title']} ({i['html_url']})" for i in issues[:10]]
        return f"Open issues in {repo}:\n" + "\n".join(lines)

    async def _create_issue(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        title = params.get("title", "")
        body = params.get("body", "")
        labels = params.get("labels", [])
        if not repo or not title:
            return "Error: 'repo' and 'title' parameters required"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo}/issues",
                json={"title": title, "body": body, "labels": labels},
                timeout=10,
            )
            resp.raise_for_status()
            issue = resp.json()
        return f"✓ Issue #{issue['number']} created: {issue['html_url']}"

    async def _add_comment(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        issue_number = params.get("issue_number")
        comment = params.get("comment", "")
        if not repo or not issue_number or not comment:
            return "Error: 'repo', 'issue_number', and 'comment' are required"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{issue_number}/comments",
                json={"body": comment},
                timeout=10,
            )
            resp.raise_for_status()
        return f"✓ Comment added to issue #{issue_number}"


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
```

- [ ] **Step 2: Implement NotionConnector**

Create `backend/services/connectors/notion.py`:

```python
"""Notion connector — OAuth + read/write actions."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionConnector(BaseConnector):
    source_type = "notion"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        params = (
            f"client_id={settings.NOTION_CLIENT_ID}"
            f"&response_type=code"
            f"&owner=user"
            f"&redirect_uri={settings.BACKEND_URL}/api/tools/oauth/notion/callback"
            f"&state={state or ''}"
        )
        return f"{NOTION_AUTH_URL}?{params}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        import base64
        creds = base64.b64encode(
            f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()
        ).decode()
        resp = httpx.post(
            NOTION_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.BACKEND_URL}/api/tools/oauth/notion/callback",
            },
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,
            "workspace_id": data.get("workspace_id"),
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search recent pages."""
        async with httpx.AsyncClient(headers=_notion_headers(access_token)) as client:
            resp = await client.post(
                f"{NOTION_API}/search",
                json={"sort": {"direction": "descending", "timestamp": "last_edited_time"}, "page_size": 20},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        title = ""
        props = raw.get("properties", {})
        for key in ("title", "Name", "Title"):
            if key in props:
                rich = props[key].get("title", [])
                title = "".join(t.get("plain_text", "") for t in rich)
                break
        return SourceItem(
            user_id=user_id,
            source_type="notion",
            source_item_type="page",
            external_id=raw.get("id", ""),
            title=title or "(untitled)",
            body="",
            item_at=raw.get("last_edited_time"),
            metadata={"url": raw.get("url", "")},
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        token = credentials.get("access_token", "")
        if action_name == "search_pages":
            return await self._search_pages(token, params)
        if action_name == "create_page":
            return await self._create_page(token, params)
        if action_name == "append_block":
            return await self._append_block(token, params)
        return f"Unknown action: {action_name}"

    async def _search_pages(self, token: str, params: dict) -> str:
        query = params.get("query", "")
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.post(
                f"{NOTION_API}/search",
                json={"query": query, "page_size": 5},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        if not results:
            return f"No Notion pages found for '{query}'."
        lines = []
        for r in results:
            props = r.get("properties", {})
            title = ""
            for key in ("title", "Name", "Title"):
                if key in props:
                    rich = props[key].get("title", [])
                    title = "".join(t.get("plain_text", "") for t in rich)
                    break
            lines.append(f"- {title or '(untitled)'}: {r.get('url', '')}")
        return "Notion pages:\n" + "\n".join(lines)

    async def _create_page(self, token: str, params: dict) -> str:
        parent_id = params.get("parent_id", "")
        title = params.get("title", "New page")
        content = params.get("content", "")
        if not parent_id:
            return "Error: 'parent_id' is required (Notion page or database ID)"
        body: dict = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
        }
        if content:
            body["children"] = [
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": content}}]}}
            ]
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.post(f"{NOTION_API}/pages", json=body, timeout=10)
            resp.raise_for_status()
            page = resp.json()
        return f"✓ Notion page created: {page.get('url', '')}"

    async def _append_block(self, token: str, params: dict) -> str:
        page_id = params.get("page_id", "")
        content = params.get("content", "")
        if not page_id or not content:
            return "Error: 'page_id' and 'content' are required"
        block = {
            "children": [
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": content}}]}}
            ]
        }
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.patch(
                f"{NOTION_API}/blocks/{page_id}/children", json=block, timeout=10
            )
            resp.raise_for_status()
        return f"✓ Block appended to Notion page {page_id}"


def _notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
```

- [ ] **Step 3: Add missing settings to config**

In `backend/config.py`, add these optional settings to the `Settings` class (so the app doesn't crash if they're not set):

```python
# Tool marketplace OAuth credentials
GITHUB_CLIENT_ID: str = ""
GITHUB_CLIENT_SECRET: str = ""
NOTION_CLIENT_ID: str = ""
NOTION_CLIENT_SECRET: str = ""
SLACK_CLIENT_ID: str = ""
SLACK_CLIENT_SECRET: str = ""
BACKEND_URL: str = "http://localhost:8000"
```

- [ ] **Step 4: Run existing connector tests to confirm nothing broke**

```bash
pytest tests/test_connectors.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add services/connectors/github.py services/connectors/notion.py config.py
git commit -m "feat: GitHub and Notion connectors with read/write execute_action"
```

---

## Task 6: Slack write + MCP client

**Files:**
- Create: `backend/services/connectors/slack_write.py`
- Create: `backend/services/mcp_client.py`

- [ ] **Step 1: Implement SlackWriteConnector**

Create `backend/services/connectors/slack_write.py`:

```python
"""Slack connector with write actions (extends existing read connector)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API = "https://slack.com/api"


class SlackWriteConnector(BaseConnector):
    source_type = "slack"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        scopes = "channels:read,chat:write,channels:history"
        return (
            f"{SLACK_AUTH_URL}"
            f"?client_id={settings.SLACK_CLIENT_ID}"
            f"&scope={scopes}"
            f"&state={state or ''}"
        )

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        resp = httpx.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,
            "team_id": data.get("team", {}).get("id"),
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch recent messages from joined channels."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SLACK_API}/conversations.list",
                headers=_slack_headers(access_token),
                params={"types": "public_channel,private_channel", "limit": 10},
                timeout=10,
            )
            resp.raise_for_status()
            channels = resp.json().get("channels", [])[:3]

        messages = []
        for ch in channels:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{SLACK_API}/conversations.history",
                    headers=_slack_headers(access_token),
                    params={"channel": ch["id"], "limit": 5},
                    timeout=10,
                )
                if resp.is_success:
                    for m in resp.json().get("messages", []):
                        m["_channel_name"] = ch.get("name", "")
                        messages.append(m)
        return messages

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type="slack",
            source_item_type="message",
            external_id=raw.get("ts", ""),
            title=raw.get("text", "")[:120],
            body=raw.get("text", ""),
            item_at=None,
            metadata={"channel": raw.get("_channel_name", ""), "ts": raw.get("ts", "")},
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        token = credentials.get("access_token", "")
        if action_name == "read_channel":
            return await self._read_channel(token, params)
        if action_name == "send_message":
            return await self._send_message(token, params)
        return f"Unknown action: {action_name}"

    async def _read_channel(self, token: str, params: dict) -> str:
        channel = params.get("channel", "")
        if not channel:
            return "Error: 'channel' parameter required (e.g. 'general')"
        limit = min(int(params.get("limit", 10)), 20)
        async with httpx.AsyncClient(headers=_slack_headers(token)) as client:
            resp = await client.get(
                f"{SLACK_API}/conversations.history",
                params={"channel": channel, "limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            messages = resp.json().get("messages", [])
        if not messages:
            return f"No recent messages in #{channel}."
        lines = [f"- {m.get('text', '')[:100]}" for m in messages]
        return f"Recent messages in #{channel}:\n" + "\n".join(lines)

    async def _send_message(self, token: str, params: dict) -> str:
        channel = params.get("channel", "")
        text = params.get("text", "")
        if not channel or not text:
            return "Error: 'channel' and 'text' are required"
        async with httpx.AsyncClient(headers=_slack_headers(token)) as client:
            resp = await client.post(
                f"{SLACK_API}/chat.postMessage",
                json={"channel": channel, "text": text},
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
        if not result.get("ok"):
            return f"Slack error: {result.get('error', 'unknown')}"
        return f"✓ Message sent to #{channel}"


def _slack_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

- [ ] **Step 2: Implement MCPClient**

Create `backend/services/mcp_client.py`:

```python
"""
MCP Client — connects to an MCP server and wraps discovered tools as LangChain tools.

Uses the mcp Python SDK (pip install mcp).
Falls back gracefully if the server is unreachable.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPClient:
    """Discover and wrap tools from an MCP server URL."""

    def __init__(self, server_url: str):
        self.server_url = server_url

    async def get_tools(self) -> list[BaseTool]:
        """
        Connect to the MCP server, list tools, and return LangChain wrappers.
        Returns [] if the server is unreachable or returns no tools.
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(self.server_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_response = await session.list_tools()
                    mcp_tools = tools_response.tools

            lc_tools = [
                _wrap_mcp_tool(t, session_url=self.server_url)
                for t in mcp_tools
            ]
            logger.info(f"✅ MCP: loaded {len(lc_tools)} tools from {self.server_url}")
            return lc_tools

        except ImportError:
            logger.warning("mcp package not installed — pip install mcp")
            return []
        except Exception as e:
            logger.warning(f"⚠️  MCP server unreachable at {self.server_url}: {e}")
            return []


def _wrap_mcp_tool(mcp_tool: Any, session_url: str) -> BaseTool:
    """Wrap a single MCP tool as a LangChain BaseTool."""
    tool_name = f"mcp__{mcp_tool.name}"
    tool_description = getattr(mcp_tool, "description", mcp_tool.name)

    class _MCPInput(BaseModel):
        params: dict = Field(default_factory=dict, description="Parameters for the MCP tool")

    class _MCPTool(BaseTool):
        name: str = tool_name
        description: str = tool_description
        args_schema: type[BaseModel] = _MCPInput
        metadata: dict = {
            "tool_id": "mcp_custom",
            "action_name": mcp_tool.name,
            "risk_level": "medium",  # MCP tools default to medium
        }

        def _run(self, params: dict = None) -> str:  # type: ignore[override]
            raise NotImplementedError("Use _arun")

        async def _arun(self, params: dict = None) -> str:  # type: ignore[override]
            try:
                from mcp import ClientSession
                from mcp.client.sse import sse_client

                async with sse_client(session_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(mcp_tool.name, params or {})
                return str(result.content)
            except Exception as e:
                return f"MCP tool error: {e}"

    return _MCPTool()
```

- [ ] **Step 3: Add mcp to requirements**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
echo "mcp" >> requirements.txt
source venv/bin/activate && pip install mcp --quiet
```

- [ ] **Step 4: Confirm backend still starts**

```bash
python -c "from services.mcp_client import MCPClient; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add services/connectors/slack_write.py services/mcp_client.py requirements.txt
git commit -m "feat: Slack write connector and MCP client wrapper"
```

---

## Task 7: Wire ToolRegistry + ESLToolGate into orchestrator

**Files:**
- Modify: `backend/services/langchain_tools.py`
- Modify: `backend/orchestrator/nodes/tools.py`
- Modify: `backend/orchestrator/state.py`

- [ ] **Step 1: Add `pending_tool_confirmation` to AgentState**

In `backend/orchestrator/state.py`, add after `token_warning: Optional[dict]`:

```python
    # Tool marketplace — mid-turn confirmation state
    pending_tool_confirmation: Optional[dict]  # {tool_id, action_name, preview, params}
```

Also add `pending_tool_confirmation` to `base_state()` in `backend/tests/test_langgraph_orchestrator.py`:

```python
def base_state() -> dict:
    return {
        "user_id": "u1", "message": "", "conversation_id": None, "model": "llama",
        "user_context": {}, "conversation_history": [], "intent": "",
        "tool_calls": [], "tool_results": [], "esl_decision": None,
        "proposed_content": "", "response_text": "", "response_events": [],
        "token_count": 0, "token_warning": None,
        "source_context": [],
        "pending_tool_confirmation": None,
    }
```

- [ ] **Step 2: Merge registry tools into `create_langchain_tools`**

In `backend/services/langchain_tools.py`, update `create_langchain_tools` to merge registry tools. Find the current function and replace with:

```python
def create_langchain_tools(
    context_manager,
    user_id: str,
    tavily_client=None,
    relevance_engine=None,
    active_sources: list | None = None,
) -> list:
    """Return all LangChain tools for this user — built-ins + marketplace tools."""
    import asyncio
    from services.tool_registry import ToolRegistry

    filter_sources = set(active_sources) if active_sources else set()

    candidates = [
        MemoryQueryTool(context_manager=context_manager, user_id=user_id),
        CalendarQueryTool(context_manager=context_manager, user_id=user_id),
        UserGoalsTool(context_manager=context_manager, user_id=user_id),
        NoteCreateTool(context_manager=context_manager, user_id=user_id),
    ]

    if tavily_client:
        candidates.append(WebSearchTool(
            tavily_client=tavily_client,
            relevance_engine=relevance_engine,
            user_id=user_id,
        ))

    # Load marketplace tools (async → run in current event loop if available)
    try:
        registry = ToolRegistry()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, registry.get_tools_for_user(user_id))
                marketplace_tools = future.result(timeout=5)
        else:
            marketplace_tools = loop.run_until_complete(registry.get_tools_for_user(user_id))
        candidates.extend(marketplace_tools)
    except Exception as e:
        logger.warning(f"⚠️  Could not load marketplace tools: {e}")

    if not filter_sources:
        return candidates

    return [
        t for t in candidates
        if _TOOL_SOURCE_MAP.get(t.name) is None
        or _TOOL_SOURCE_MAP.get(t.name) in filter_sources
    ]
```

- [ ] **Step 3: Add ESL gate to `tool_execution_node`**

In `backend/orchestrator/nodes/tools.py`, update `tool_execution_node`. Replace the inner loop that executes tools (lines 183–197) with:

```python
    results = []
    events = []
    pending_confirmation = None

    for tc in state.get("tool_calls", []):
        tool_name = tc.get("name", "")
        tool_input = tc.get("args", {})
        events.append({"event": "tool_use", "tool": tool_name})

        if tool_name not in tool_map:
            results.append({"tool": tool_name, "result": "Tool not found"})
            continue

        t = tool_map[tool_name]
        meta = getattr(t, "metadata", {}) or {}
        tool_id = meta.get("tool_id")
        action_name = meta.get("action_name")
        risk_level = meta.get("risk_level", "medium")

        # Only gate marketplace tools (they have tool_id in metadata)
        if tool_id and action_name:
            from esl.tool_gate import ESLToolGate, GateResult
            gate = ESLToolGate()
            preview = f"{tool_name}: {tool_input}"
            decision = await gate.check(
                user_id=user_id,
                tool_id=tool_id,
                action_name=action_name,
                risk_level=risk_level,
                preview=preview,
            )
            if decision.status == GateResult.VETOED:
                results.append({"tool": tool_name, "result": "Action not permitted by user settings."})
                events.append({"event": "tool_vetoed", "tool": tool_name})
                continue
            if decision.status == GateResult.PENDING_CONFIRMATION:
                pending_confirmation = {
                    "tool_id": tool_id,
                    "action_name": action_name,
                    "tool_name": tool_name,
                    "preview": decision.preview,
                    "params": tool_input,
                    "risk_level": risk_level,
                }
                events.append({"event": "tool_pending_confirmation", "tool": tool_name, "preview": decision.preview})
                results.append({"tool": tool_name, "result": f"Awaiting confirmation: {decision.preview}"})
                continue

        try:
            result = await t.ainvoke(tool_input)
            results.append({"tool": tool_name, "result": str(result)})
            events.append({"event": "tool_result", "tool": tool_name})
        except Exception as e:
            results.append({"tool": tool_name, "result": f"Error: {e}"})
```

Also update the return dict at the end of `tool_execution_node` to include `pending_tool_confirmation`:

```python
    return {
        "tool_results": results,
        "proposed_content": proposed,
        "response_events": events,
        "citations": _build_citations(results),
        "token_count": state.get("token_count", 0) + tokens_used,
        "token_warning": warning,
        "pending_tool_confirmation": pending_confirmation,
    }
```

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest -v 2>&1 | tail -20
```

Expected: all previously passing tests still pass.

- [ ] **Step 5: Commit**

```bash
git add services/langchain_tools.py orchestrator/nodes/tools.py orchestrator/state.py \
        tests/test_langgraph_orchestrator.py
git commit -m "feat: wire ToolRegistry and ESLToolGate into LangGraph tool_execution_node"
```

---

## Task 8: Frontend — catalogue UI + ToolConfirmation

**Files:**
- Create: `frontend/components/CatalogueCard.tsx`
- Create: `frontend/components/ToolConfirmation.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/dashboard/integrations/page.tsx`

- [ ] **Step 1: Add `toolMarketplaceApi` to api.ts**

In `frontend/lib/api.ts`, add these types and API object:

```typescript
export interface ToolDefinition {
  id: string
  name: string
  description: string
  auth_type: 'oauth' | 'apikey' | 'mcp'
  actions: Array<{ name: string; description: string; risk_level: 'low' | 'medium' | 'high' }>
  icon_url: string | null
  enabled: boolean
}

export interface ConnectedTool {
  tool_id: string
  enabled: boolean
  connected_at: string
  last_used_at: string | null
  mcp_url: string | null
  name: string
  description: string
  auth_type: string
  actions: ToolDefinition['actions']
  icon_url: string | null
}

export const toolMarketplaceApi = {
  getCatalogue: async (): Promise<ToolDefinition[]> => {
    const res = await fetch('/api/tools', { credentials: 'include' })
    if (!res.ok) throw new Error('Failed to fetch catalogue')
    return res.json()
  },

  getConnected: async (): Promise<ConnectedTool[]> => {
    const res = await fetch('/api/tools/connected', { credentials: 'include' })
    if (!res.ok) throw new Error('Failed to fetch connected tools')
    return res.json()
  },

  getAuthUrl: async (toolId: string): Promise<string> => {
    const res = await fetch(`/api/tools/oauth/${toolId}/authorize`, { credentials: 'include' })
    if (!res.ok) throw new Error('Failed to get auth URL')
    const data = await res.json()
    return data.auth_url
  },

  disconnect: async (toolId: string): Promise<void> => {
    const res = await fetch(`/api/tools/${toolId}`, { method: 'DELETE', credentials: 'include' })
    if (!res.ok) throw new Error('Failed to disconnect tool')
  },

  setPermission: async (toolId: string, actionName: string, trustLevel: 'ask' | 'allow' | 'deny'): Promise<void> => {
    const res = await fetch(`/api/tools/${toolId}/permissions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ action_name: actionName, trust_level: trustLevel }),
    })
    if (!res.ok) throw new Error('Failed to set permission')
  },

  connectMcp: async (mcpUrl: string): Promise<void> => {
    const res = await fetch('/api/tools/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ mcp_url: mcpUrl }),
    })
    if (!res.ok) throw new Error('Failed to connect MCP server')
  },
}
```

- [ ] **Step 2: Create CatalogueCard component**

Create `frontend/components/CatalogueCard.tsx`:

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
    <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900 px-4 py-3">
      <div className="flex items-center gap-3">
        {tool.icon_url ? (
          <img src={tool.icon_url} alt={tool.name} className="h-8 w-8 rounded" />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded bg-gray-700 text-sm">
            {tool.name[0]}
          </div>
        )}
        <div>
          <p className="text-sm font-medium text-white">{tool.name}</p>
          <p className="text-xs text-gray-400">{tool.description}</p>
        </div>
      </div>
      {isConnected ? (
        <button
          onClick={() => onDisconnect(tool.id)}
          className="rounded px-3 py-1 text-xs text-red-400 hover:bg-red-900/30 border border-red-800"
        >
          Disconnect
        </button>
      ) : (
        <button
          onClick={() => onConnect(tool.id)}
          className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500"
        >
          + Connect
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create ToolConfirmation component**

Create `frontend/components/ToolConfirmation.tsx`:

```tsx
'use client'

interface Props {
  toolName: string
  actionName: string
  preview: string
  onAllowOnce: () => void
  onAlwaysAllow: () => void
  onDeny: () => void
}

export function ToolConfirmation({ toolName, actionName, preview, onAllowOnce, onAlwaysAllow, onDeny }: Props) {
  return (
    <div className="rounded-lg border border-amber-700 bg-gray-900 p-4 my-2">
      <p className="text-xs font-semibold text-amber-400 mb-2">
        ⚡ {toolName} wants to: {actionName}
      </p>
      <p className="text-sm text-gray-300 mb-3 whitespace-pre-wrap">{preview}</p>
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={onAllowOnce}
          className="rounded bg-green-700 px-3 py-1 text-xs text-white hover:bg-green-600"
        >
          ✓ Allow once
        </button>
        <button
          onClick={onAlwaysAllow}
          className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500"
        >
          ✓ Always allow
        </button>
        <button
          onClick={onDeny}
          className="rounded bg-red-800 px-3 py-1 text-xs text-white hover:bg-red-700"
        >
          ✗ Don't do this
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Update integrations page**

In `frontend/app/dashboard/integrations/page.tsx`, add the catalogue section below the existing connected sources section. At the top of the file, add the new imports:

```tsx
import { toolMarketplaceApi, ToolDefinition, ConnectedTool } from '@/lib/api'
import { CatalogueCard } from '@/components/CatalogueCard'
```

Add state variables inside the component:

```tsx
const [catalogue, setCatalogue] = useState<ToolDefinition[]>([])
const [connectedTools, setConnectedTools] = useState<ConnectedTool[]>([])
const [showAdvanced, setShowAdvanced] = useState(false)
const [mcpUrl, setMcpUrl] = useState('')
const [mcpConnecting, setMcpConnecting] = useState(false)
```

Add a `loadMarketplace` function and call it in `useEffect`:

```tsx
async function loadMarketplace() {
  try {
    const [cat, conn] = await Promise.all([
      toolMarketplaceApi.getCatalogue(),
      toolMarketplaceApi.getConnected(),
    ])
    if (mountedRef.current) {
      setCatalogue(cat)
      setConnectedTools(conn)
    }
  } catch (e) {
    // catalogue load failure is non-fatal
  }
}
```

Add these handler functions:

```tsx
async function handleConnectTool(toolId: string) {
  try {
    const url = await toolMarketplaceApi.getAuthUrl(toolId)
    window.location.href = url
  } catch (e) {
    console.error('Failed to get auth URL', e)
  }
}

async function handleDisconnectTool(toolId: string) {
  try {
    await toolMarketplaceApi.disconnect(toolId)
    await loadMarketplace()
  } catch (e) {
    console.error('Failed to disconnect tool', e)
  }
}

async function handleConnectMcp() {
  if (!mcpUrl.trim()) return
  setMcpConnecting(true)
  try {
    await toolMarketplaceApi.connectMcp(mcpUrl.trim())
    setMcpUrl('')
    await loadMarketplace()
  } catch (e) {
    console.error('Failed to connect MCP', e)
  } finally {
    setMcpConnecting(false)
  }
}
```

Add this JSX below the existing connected sources cards, before the closing `</div>` of the main container:

```tsx
{/* Catalogue section */}
{catalogue.length > 0 && (
  <div className="mt-6">
    <h3 className="text-xs font-semibold uppercase text-gray-500 mb-3">Available</h3>
    <div className="flex flex-col gap-2">
      {catalogue.map((tool) => (
        <CatalogueCard
          key={tool.id}
          tool={tool}
          isConnected={connectedTools.some((c) => c.tool_id === tool.id && c.enabled)}
          onConnect={handleConnectTool}
          onDisconnect={handleDisconnectTool}
        />
      ))}
    </div>
  </div>
)}

{/* Advanced / MCP section */}
<div className="mt-6 border-t border-gray-800 pt-4">
  <button
    onClick={() => setShowAdvanced((v) => !v)}
    className="text-xs text-gray-500 hover:text-gray-300"
  >
    {showAdvanced ? '▾' : '▸'} Show advanced options
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

- [ ] **Step 5: TypeScript check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1 | grep -v "__tests__" | head -20
```

Expected: no errors in production files.

- [ ] **Step 6: Commit**

```bash
git add components/CatalogueCard.tsx components/ToolConfirmation.tsx \
        lib/api.ts app/dashboard/integrations/page.tsx
git commit -m "feat: tool marketplace UI — catalogue grid, CatalogueCard, ToolConfirmation, MCP section"
```

---

## Task 9 (was missing): GCal/Gmail write actions + ESL audit logging + chat ToolConfirmation

**Files:**
- Modify: `backend/services/connectors/google_calendar.py`
- Modify: `backend/services/connectors/gmail.py`
- Modify: `backend/orchestrator/nodes/tools.py` (add audit log write)
- Modify: chat frontend component (render ToolConfirmation on pending event)

- [ ] **Step 1: Add `execute_action` to GoogleCalendarConnector**

In `backend/services/connectors/google_calendar.py`, add this method to the `GoogleCalendarConnector` class:

```python
    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        """Execute a write action on Google Calendar."""
        import httpx
        token = credentials.get("access_token", "")
        base = "https://www.googleapis.com/calendar/v3"

        if action_name == "create_event":
            summary = params.get("summary", "New event")
            start = params.get("start")  # ISO datetime string
            end = params.get("end")      # ISO datetime string
            if not start or not end:
                return "Error: 'start' and 'end' (ISO datetime) are required"
            body = {
                "summary": summary,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            }
            if params.get("description"):
                body["description"] = params["description"]
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base}/calendars/primary/events",
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                resp.raise_for_status()
                event = resp.json()
            return f"✓ Event created: {event.get('htmlLink', event.get('id', ''))}"

        if action_name == "update_event":
            event_id = params.get("event_id", "")
            if not event_id:
                return "Error: 'event_id' is required"
            patch_body = {k: v for k, v in params.items() if k != "event_id"}
            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"{base}/calendars/primary/events/{event_id}",
                    json=patch_body,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                resp.raise_for_status()
            return f"✓ Event {event_id} updated"

        return f"Unknown action: {action_name}"
```

- [ ] **Step 2: Add `execute_action` to GmailConnector**

In `backend/services/connectors/gmail.py`, add this method to the `GmailConnector` class:

```python
    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        """Execute a write action on Gmail."""
        import httpx, base64
        from email.mime.text import MIMEText
        token = credentials.get("access_token", "")

        if action_name == "create_draft":
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")
            if not to or not subject:
                return "Error: 'to' and 'subject' are required"
            msg = MIMEText(body)
            msg["to"] = to
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
                    json={"message": {"raw": raw}},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                resp.raise_for_status()
            return f"✓ Draft created to {to}: {subject}"

        if action_name == "send_reply":
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")
            thread_id = params.get("thread_id")
            if not to or not body:
                return "Error: 'to' and 'body' are required"
            msg = MIMEText(body)
            msg["to"] = to
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            payload: dict = {"raw": raw}
            if thread_id:
                payload["threadId"] = thread_id
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                resp.raise_for_status()
            return f"✓ Email sent to {to}"

        return f"Unknown action: {action_name}"
```

- [ ] **Step 3: Add ESL audit logging to `tool_execution_node`**

In `backend/orchestrator/nodes/tools.py`, inside the `tool_execution_node` function, after the gate check resolves `GateResult.APPROVED` and the tool executes successfully, add an audit log write. Add this import at the top of the function:

```python
    from esl.audit import ESLAuditLogger
    from esl.models import ProposedAction, ESLDecision, ESLDecisionStatus, ActionType, UrgencyLevel
    from datetime import datetime
```

Then inside the gate check block, after `decision.status == GateResult.APPROVED` path (before `t.ainvoke`), add a helper that logs after execution:

```python
        # Audit approved marketplace actions
        async def _audit_tool_action(tool_id: str, action_name: str, status: str, reason: str):
            try:
                audit_logger = ESLAuditLogger()
                proposed = ProposedAction(
                    action_type=ActionType.TOOL_EXECUTION,
                    content_type=f"{tool_id}/{action_name}",
                    urgency=UrgencyLevel.MEDIUM,
                    metadata={"tool_id": tool_id, "action_name": action_name},
                )
                decision_obj = ESLDecision(
                    status=ESLDecisionStatus(status),
                    reason=reason,
                    confidence=1.0,
                )
                await audit_logger.log_decision(
                    user_id=user_id,
                    proposed_action=proposed,
                    decision=decision_obj,
                    context_snapshot={"tool_id": tool_id, "action_name": action_name},
                )
            except Exception:
                pass  # audit failure must never break execution
```

After a successful tool execution (inside the `try` block after `t.ainvoke`), call:
```python
                if tool_id and action_name:
                    await _audit_tool_action(tool_id, action_name, "APPROVED", "Marketplace tool executed")
```

After a VETOED gate result, call:
```python
                await _audit_tool_action(tool_id, action_name, "VETOED", "User denied this action")
```

**Note:** Check `esl/models.py` for the exact `ActionType` and `UrgencyLevel` enum values before using them — if `TOOL_EXECUTION` doesn't exist, use `ActionType.PUSH_NOTIFICATION` as a fallback and document it as a TODO for a follow-up enum addition.

- [ ] **Step 4: Render ToolConfirmation in chat**

Find the chat message component (check `frontend/app/dashboard/chat/` or `frontend/components/ChatMessage.tsx`). In the SSE event handler, add handling for `tool_pending_confirmation` events. After finding the correct file, add:

```tsx
import { ToolConfirmation } from '@/components/ToolConfirmation'
import { toolMarketplaceApi } from '@/lib/api'
```

Where chat messages are rendered, add:

```tsx
{message.pendingConfirmation && (
  <ToolConfirmation
    toolName={message.pendingConfirmation.tool_name}
    actionName={message.pendingConfirmation.action_name}
    preview={message.pendingConfirmation.preview}
    onAllowOnce={async () => {
      // Re-send message with explicit confirmation — simplest approach
      await sendMessage(currentMessage)
    }}
    onAlwaysAllow={async () => {
      await toolMarketplaceApi.setPermission(
        message.pendingConfirmation.tool_id,
        message.pendingConfirmation.action_name,
        'allow'
      )
      await sendMessage(currentMessage)
    }}
    onDeny={async () => {
      await toolMarketplaceApi.setPermission(
        message.pendingConfirmation.tool_id,
        message.pendingConfirmation.action_name,
        'deny'
      )
    }}
  />
)}
```

In the SSE stream parser, when you see `{"event": "tool_pending_confirmation", ...}`, attach it to the current assistant message as `pendingConfirmation`.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/connectors/google_calendar.py services/connectors/gmail.py \
        orchestrator/nodes/tools.py
git commit -m "feat: GCal/Gmail execute_action, ESL audit logging for tool actions, chat ToolConfirmation"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest -v 2>&1 | tail -30
```

Expected: all new tests pass (test_tool_registry, test_tool_gate, test_tool_marketplace_routes), no regressions.

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1 | grep -v "__tests__"
```

Expected: no output.

- [ ] **Step 3: Smoke test — catalogue visible**

1. Start backend: `cd backend && source venv/bin/activate && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:3000/dashboard/integrations
4. Verify the catalogue section shows Notion, Slack, GitHub, Google Calendar, Gmail cards
5. Verify "Show advanced options" toggle reveals the MCP input form

- [ ] **Step 4: Smoke test — ESL gate in chat**

1. In Postgres, insert a connected tool for the dev user:
```sql
INSERT INTO user_tool_connections (user_id, tool_id, enabled, credentials)
VALUES ('00000000-0000-0000-0000-000000000000', 'github', true, '{"access_token": "test_tok"}')
ON CONFLICT DO NOTHING;
```
2. Open http://localhost:3000/dashboard/chat
3. Ask: "Create a GitHub issue for the login bug in owner/repo"
4. Verify EC responds with a confirmation prompt (not an immediate action)

- [ ] **Step 5: Final commit**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion
git add -p
git commit -m "feat: tool marketplace — catalogue, ESL progressive trust, MCP escape hatch"
```
