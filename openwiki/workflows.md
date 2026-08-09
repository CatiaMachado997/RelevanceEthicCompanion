# Key workflows

## 1. Grounded chat and planning

1. The authenticated dashboard calls the FastAPI SSE route (`GET /api/chat/stream` in `backend/routes/chat.py`).
2. `context_builder` assembles user context, conversation history, snapshots, and synced source context. Intent classification sends deep-research requests to `orchestrator/subgraphs/deep_research.py`; other requests enter the tool planner.
3. `tool_planner_node` and `tool_execution_node` (`backend/orchestrator/nodes/tools.py`) create a persisted ReAct trace (`planner_runs`), execute user-filtered tools, retry a failed action once, collect telemetry/citations, and may return to planning. The graph stops at no planned calls or the three-step cap.
4. The result passes through ESL, then the formatter streams response events and citation information. `VETOED` responses are explained rather than emitted as proposed.

**Forced retrieval:** source filters reach `AgentState.active_sources`; `force_retrieval` makes the planner include `search_documents` regardless of LLM judgement. RAG output carries per-chunk citations for the frontend.

**When changing:** preserve state fields and event names used by `frontend/app/dashboard/chat/` and `frontend/lib/api.ts`; run planner-loop, streaming, and ESL tests described in [testing](testing.md).

## 2. Retrieval and personal context

Uploads and connector items converge in Weaviate’s `DocumentMemory` collection:

```text
connector/upload → normalized source item in Postgres → chunk/index/embed → Weaviate
                                                     ↘ status/error/telemetry in Postgres
chat query → Gemini query embedding → hybrid search (dense + BM25) → optional Jina rerank → citations + trace
```

`services/connector_indexer.py` chunks indexed content at 800 characters with 100-character overlap. `services/rag_retrieval.py` performs per-user hybrid retrieval at alpha 0.7, fetches a floor of 20 candidates, optionally applies Jina reranking, and returns a transparency trace (candidates, rerank status, final chunks). Retrieval, embedding, and Weaviate failures intentionally return no context instead of failing the chat turn.

## 3. Connector and tool integration paths

There are related but distinct flows:

- **Native connector operations:** Google Calendar, Gmail, and Slack OAuth callbacks live in `routes/data_sources.py`; `routes/connectors.py` owns status, synchronous historical backfill, retry indexing, disconnect/wipe for these three source types. Backfill awaits completion by design, so large sync windows could become request-timeout risks.
- **Composio tools/sync:** `services/composio_tools.py` and `services/composio_sync.py` provide managed provider actions and sync mappings for Gmail, Calendar, Slack, GitHub, and Notion. Provider content is normalized to source items and indexed for shared retrieval.
- **Tool marketplace:** `routes/tool_marketplace.py`, `services/tool_registry.py`, and ESL tool gating handle tool discovery/action confirmation separately from the streaming pause/resume mechanism.

The integrations page currently advertises five providers, while the connector operator router supports three. Before expanding integrations, resolve that split rather than duplicating status/backfill logic.

## 4. Work management and proactive views

The dashboard has goals, projects, tasks, Today, and weekly review surfaces. The service layer and routes under `backend/routes/{goals,projects,tasks,today,weekly_review}.py` use user-scoped Postgres data. Tasks can belong to a project and/or goal; dependency-cycle protection belongs in `services/task_dependencies.py`. SQL rollup views calculate project progress/risk and goal progress from tasks/milestones (`backend/migrations/011_work_management_depth.sql`).

The onboarding guard treats a user as new only when they lack an onboarding timestamp **and** any source, value, and goal. Preserve that triple-empty condition when changing first-run experience (`frontend/app/dashboard/layout.tsx`).

## 5. AutoLab experiments

AutoLab is an internal hill-climbing facility exposed through `routes/autolab.py` and rendered by the Insights page. A track provides `surface.py`, `program.md`, and an evaluator. `HillClimbingRunner` evaluates the current surface, requests one Claude-generated unified diff, applies it with the OS `patch` tool, evaluates again, preserves strict improvements, and reverts non-improvements. Results are sent to Obsidian or local fallbacks.

**Operational boundary:** this process mutates track surfaces on disk. The runner stores `budget_secs` but does not itself impose a wall-clock timeout. Treat it as an isolated, controlled experiment mechanism; see [operations](operations.md) before enabling it in shared or production-like environments.
