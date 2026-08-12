# Integrations and boundaries

## Authentication and browser/API boundary

The frontend uses Supabase SSR/browser clients. `frontend/proxy.ts` protects `/dashboard/**` by reading Supabase session cookies; the dashboard layout also performs a client-side redirect if its auth hook sees no session. Once mounted, the layout configures `frontend/lib/api.ts` to retrieve the current Supabase access token and attach `Authorization: Bearer …` to backend requests. A 401 redirects to `/login`.

The auth callback completes the provider session then redirects into the dashboard. The callback also attempts a backend session-cookie call, but its code labels that operation non-critical because dashboard protection validates Supabase directly.

**Change guidance:** keep proxy, client auth hook, callback, API client, and backend auth dependencies aligned. The current worktree contains uncommitted edits in callback/hook/proxy files; do not treat those edits as stable product behavior without review and tests.

## Connected knowledge sources

First-party data-source integration is the ingestion path for **Google Calendar, Gmail, and Slack**:

- OAuth and connection routes: `backend/routes/data_sources.py`
- Lifecycle orchestration: `backend/services/data_ingestion.py`
- Provider adapters: `backend/services/connectors/`, plus Gmail/Calendar/Slack sync services
- Storage/search: normalized `source_items` in Postgres and optional Weaviate indexing
- UI: `frontend/app/dashboard/integrations/`

The service stores a connection, performs an initial sync where possible, refreshes tokens when valid, marks reconnect-required failures, and schedules recurring sync. Read [workflows.md](workflows.md#2-grounded-retrieval-and-source-ingestion) before changing this pipeline.

## Tool marketplace and MCP

Action-capable integrations are separate from source ingestion. `services/tool_registry.py`, `services/composio_tools.py`, `routes/tool_marketplace.py`, and `migrations/009_tool_marketplace.sql` describe tools sourced through Composio (including GitHub, Notion, Slack/Gmail write, and Calendar write) and user-provided MCP endpoints.

Tool metadata includes tool ID, action name, and risk level. The executor routes marketplace actions through `ESLToolGate`; the gate can veto or emit a confirmation requirement based on user permissions and risk. Preserve this metadata and gate when adding a tool.

There is an integration-lifecycle ambiguity worth preserving as a caveat: the first-party connector operator supports Calendar/Gmail/Slack, while GitHub/Notion appear in marketplace/Composio paths and UI. Do not assume all integrations share the same OAuth, status, or backfill semantics.

## Provider roles

| Provider/service | Purpose in current source |
|---|---|
| Supabase | user auth and production-oriented Postgres deployment |
| Postgres | structured application records, telemetry, and production LangGraph checkpoints |
| Weaviate | semantic storage/retrieval for documents and source context |
| Groq | chat/planning model access |
| Gemini | embeddings |
| Tavily | web-search tool |
| Jina (optional) | reranking hybrid retrieval results; empty key is a graceful fallback |
| Composio | managed action-tool integrations/OAuth lifecycle |
| Google/Slack OAuth | first-party Calendar, Gmail, and Slack source connections |
| GCP Secret Manager | optional production secret loading |
| Langfuse (optional) | orchestration observability |

`backend/config.py` is the non-secret configuration inventory. It documents variable names and defaults; use `.env.example` files for setup placeholders, never live `.env` files.

## Integration checks

When changing an integration, verify: user ownership/auth, OAuth callback and token-refresh behavior, idempotent normalized upsert, index/retrieval behavior, UI status/count mapping, tool risk/confirmation if action-capable, and scheduler effects. Useful tests include connector, connector-indexer, Composio-tool, tool-gate, data-source route, and integrations-page tests.
