# Tool Marketplace — Design Spec

**Date:** 2026-04-08
**Status:** Approved for implementation planning

---

## Overview

Add a dynamic tool marketplace to Ethic Companion so users can connect external tools (Notion, Slack, GitHub, and more) and EC can both read from and write to those tools — with every write action gated through the Ethical Safeguard Layer (ESL).

---

## Goals

1. Users can browse and connect tools from a curated catalogue on the integrations page.
2. Connected tools are available to the LangGraph orchestrator dynamically — no code change needed to add a new tool.
3. Write actions (create issue, send draft, create event) are gated by a progressive trust model: EC asks once, remembers the answer, executes automatically when trusted.
4. High-risk actions (send email, delete, post publicly) always confirm regardless of stored trust.
5. Power users can connect any MCP server as an escape hatch, hidden under "Show advanced options".

---

## Non-goals (v1)

- Webhook/push integrations (tools that push events to EC) — read/write only for now.
- Per-workspace or team-level tool sharing — individual users only.
- Linear, Todoist, Airtable — deferred to v2 catalogue expansion.

---

## Architecture

### Three layers

```
User (integrations page)
  → Tool Registry (DB: tool_definitions, user_tool_connections, tool_permissions)
  → ESL Tool Gate (checks trust, previews, gates writes)
  → LangGraph execution (tool_execution_node calls approved action)
```

### V1 catalogue

| Tool | Auth | Read | Write |
|---|---|---|---|
| Google Calendar | OAuth (existing) | ✅ existing | Create event, update event |
| Gmail | OAuth (existing) | ✅ existing | Draft reply, send reply |
| Notion | OAuth | Pages, databases | Create page, append block |
| Slack | OAuth (connector exists) | Messages, channels | Send message, reply to thread |
| GitHub | OAuth | Issues, PRs | Create issue, add comment |

### MCP escape hatch

Users can register any MCP server URL under "Show advanced options" on the integrations page. `mcp_client.py` connects to the server via SSE, calls `tools/list` to discover available tools, and wraps each as a LangChain tool. Credentials for MCP servers are stored in `user_tool_connections.credentials` JSONB, encrypted with the same key used for OAuth tokens. If the MCP server is unreachable at tool-load time, the connection is marked `enabled=false` with an error message — it does not crash the orchestrator. The ESL gate applies equally to MCP tools — no bypass.

---

## Database Schema

### `tool_definitions` (the catalogue)

```sql
CREATE TABLE tool_definitions (
    id            TEXT PRIMARY KEY,           -- 'google_calendar', 'notion', 'github'…
    name          TEXT NOT NULL,
    description   TEXT,
    auth_type     TEXT NOT NULL,              -- 'oauth' | 'apikey' | 'mcp'
    oauth_scopes  TEXT[],
    actions       JSONB NOT NULL,             -- array of {name, description, risk_level}
    icon_url      TEXT,
    enabled       BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

`actions` example:
```json
[
  {"name": "create_issue", "description": "Create a GitHub issue", "risk_level": "medium"},
  {"name": "delete_issue", "description": "Delete a GitHub issue", "risk_level": "high"}
]
```

Risk levels:
- `low` — auto-executes on first use (no prompt); user can revoke in settings.
- `medium` — prompts on first use; auto-executes after "Always allow".
- `high` — always shows confirmation preview, even when trust is `allow`. Cannot be bypassed.

### `user_tool_connections`

```sql
CREATE TABLE user_tool_connections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id           TEXT NOT NULL REFERENCES tool_definitions(id),
    enabled           BOOLEAN DEFAULT true,
    credentials       JSONB,                  -- encrypted OAuth tokens or API key
    mcp_url           TEXT,                   -- MCP servers only
    connected_at      TIMESTAMPTZ DEFAULT now(),
    last_used_at      TIMESTAMPTZ,
    UNIQUE (user_id, tool_id)
);
```

### `tool_permissions` (trust memory)

```sql
CREATE TABLE tool_permissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id      TEXT NOT NULL,
    action_name  TEXT NOT NULL,
    trust_level  TEXT NOT NULL,              -- 'ask' | 'allow' | 'deny'
    granted_at   TIMESTAMPTZ DEFAULT now(),
    expires_at   TIMESTAMPTZ,               -- NULL = permanent
    UNIQUE (user_id, tool_id, action_name)
);
```

---

## ESL Trust Model

### Progressive trust flow

1. **First time** (trust record is `ask` or absent) — EC previews the action and presents three options:
   - **Allow once** — executes now, trust record remains `ask` (will prompt again next time)
   - **Always allow** — executes now, upserts trust record to `allow` (future calls skip prompt)
   - **Don't do this** — vetoes, upserts trust record to `deny` (future calls silently vetoed)

2. **Trusted (`allow`)** — action executes automatically; EC confirms in chat ("✓ GitHub issue #47 created").

3. **Denied (`deny`)** — action is vetoed silently; EC tells the user it won't do that.

4. **High-risk override** — actions with `risk_level = 'high'` always show a confirmation preview regardless of stored trust level. This is enforced in `esl/tool_gate.py` and cannot be overridden by the user.

### ESL audit

Every write action (approved, auto-approved, or vetoed) is logged to the existing `esl_audit_log` table using the existing `proposed_action`, `decision_status` (APPROVED/VETOED), and `decision_reason` columns. The `tool_id` and `action_name` are stored in `decision_reason` as a JSON string. This keeps audit records immutable and separate from the user-configurable `tool_permissions` trust records.

---

## Backend Components

### New files

| File | Purpose |
|---|---|
| `backend/services/tool_registry.py` | Loads tool definitions from DB; `get_tools_for_user(user_id)` returns active LangChain tool instances |
| `backend/services/mcp_client.py` | Connects to an MCP server URL; discovers and wraps tools as LangChain tools |
| `backend/services/connectors/notion.py` | Notion OAuth connector + read/write actions |
| `backend/services/connectors/github.py` | GitHub OAuth connector + read/write actions |
| `backend/services/connectors/slack_write.py` | Extends existing Slack connector with write actions |
| `backend/esl/tool_gate.py` | Pre-execution ESL check: reads `tool_permissions`, returns `APPROVED | PENDING_CONFIRMATION | VETOED` |
| `backend/routes/tool_marketplace.py` | REST endpoints for connect, disconnect, permissions, MCP registration. OAuth flow uses existing `create_signed_state()` / `validate_signed_state()` utilities from `data_sources.py`. Token storage uses the same encryption helper already used for `data_sources.oauth_token_encrypted`. |
| `backend/database/migrations/003_tool_marketplace.sql` | Adds the three new tables |
| `backend/tests/test_tool_registry.py` | Unit tests for dynamic tool loading |
| `backend/tests/test_tool_gate.py` | Unit tests for all trust/veto scenarios |
| `backend/tests/test_tool_marketplace_routes.py` | Integration tests for connect/disconnect/permissions routes |

### Modified files

| File | Change |
|---|---|
| `backend/services/langchain_tools.py` | `create_langchain_tools()` calls `tool_registry.get_tools_for_user()` and merges with built-in tools |
| `backend/orchestrator/nodes/tools.py` | `tool_execution_node` calls `tool_gate.check()` before executing any write tool |
| `backend/orchestrator/state.py` | Add `pending_tool_confirmation: Optional[dict]` for mid-turn confirmation state |

---

## Frontend Components

### Modified files

| File | Change |
|---|---|
| `frontend/app/dashboard/integrations/page.tsx` | Add catalogue grid, trust badges per connected tool, "Show advanced" toggle, MCP URL form |
| `frontend/lib/api.ts` | Add `toolMarketplaceApi` with connect/disconnect/permissions/mcp endpoints |
| `frontend/app/dashboard/settings/page.tsx` | Add "Permissions" section per connected tool (revoke individual action trust) |

### New components

| File | Purpose |
|---|---|
| `frontend/components/ToolConfirmation.tsx` | ESL confirmation card shown in chat stream — previews action, three trust buttons |
| `frontend/components/CatalogueCard.tsx` | Single tool card in the integrations catalogue (icon, name, description, Connect button) |

---

## API Endpoints

```
GET    /api/tools                          # List all tool definitions (catalogue)
GET    /api/tools/connected                # User's connected tools with status
POST   /api/tools/{tool_id}/connect        # Initiate OAuth or save API key
DELETE /api/tools/{tool_id}/disconnect     # Remove connection + credentials
GET    /api/tools/{tool_id}/oauth/authorize  # OAuth redirect URL
GET    /api/tools/{tool_id}/oauth/callback   # OAuth callback (same pattern as data_sources)
POST   /api/tools/{tool_id}/permissions    # Set trust level for an action
DELETE /api/tools/{tool_id}/permissions/{action}  # Revoke trust for an action
POST   /api/tools/mcp                      # Register MCP server URL
DELETE /api/tools/mcp/{connection_id}      # Remove MCP server
```

---

## UI Flow

### Integrations page layout

```
[Connected]
  📅 Google Calendar  ●Synced   Trusted: create_event   [Manage]
  ✉️  Gmail           ●Synced   Trusted: —              [Manage]

[Available]
  📝 Notion   Notes, databases, tasks          [+ Connect]
  💬 Slack    Messages, channels               [+ Connect]
  🐙 GitHub   Issues, PRs, comments            [+ Connect]

                    ▸ Show advanced options
```

When expanded:
```
──── Advanced ────
  Connect any MCP server
  [https://my-server.com/sse         ] [Connect]
```

### Chat confirmation card

When EC needs to perform a write action and trust is `ask`:

```
┌─ ⚡ First time using GitHub · create_issue ──────────────┐
│  Title: Fix login bug — auth token not persisting         │
│  Repo:  your-org/app                                      │
│                                                           │
│  [✓ Allow once]  [✓ Always allow]  [✗ Don't do this]     │
└───────────────────────────────────────────────────────────┘
```

---

## Testing

### Unit tests

- **`test_tool_registry.py`:** `get_tools_for_user` returns only tools with active `user_tool_connections`; MCP tools discovered from mock server URL are included; disconnected tools are excluded.
- **`test_tool_gate.py`:** `ask` → returns `PENDING_CONFIRMATION` with preview; `allow` → returns `APPROVED`; `deny` → returns `VETOED`; `risk_level=high` → always returns `PENDING_CONFIRMATION` even when trust is `allow`.

### Integration tests

- **`test_tool_marketplace_routes.py`:** connect writes `user_tool_connections` row; disconnect removes it; permission update changes `trust_level` in `tool_permissions`.

### ESL audit

All write outcomes (approved, auto-approved, vetoed) verified in `esl_audit_log` via existing audit infrastructure.

---

## Phasing

This spec covers the full v1 system. Suggested implementation order:

1. DB migration + seed `tool_definitions` catalogue
2. `tool_registry.py` + `tool_gate.py` (pure backend, testable in isolation)
3. Marketplace routes + OAuth flow for Notion, GitHub
4. `slack_write.py` (extends existing connector)
5. `mcp_client.py`
6. Orchestrator integration (`tool_execution_node` + ESL gate)
7. Frontend: catalogue UI + `ToolConfirmation` component
8. Write actions for GCal and Gmail (extend existing connectors)
