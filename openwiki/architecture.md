# Architecture and control boundaries

## Runtime composition

- **Frontend:** Next.js 16 App Router in `frontend/`. The dashboard layout configures a Supabase access-token provider for the shared API client, redirects unauthenticated users to `/login`, and redirects an entirely empty first-time account to onboarding (`frontend/app/dashboard/layout.tsx`).
- **Backend:** FastAPI application in `backend/main.py`. Its lifespan opens the DB pool, performs compatibility DDL, runs versioned migrations, then attempts to start scheduled ingestion. Migration failure prevents the server from serving; scheduler failure logs a warning and leaves manual sync available.
- **State and stores:** Supabase/Postgres holds user-scoped product data, audit and planner telemetry; Weaviate holds retrieval chunks. See [domain concepts](domains.md).
- **External boundaries:** Supabase Auth authenticates the dashboard/API relationship. LLMs, embedding/reranking providers, OAuth/connectors, and Composio are accessed from the backend. See [workflows](workflows.md).

`frontend/lib/api.ts` is the practical UI/API contract: it supplies bearer auth, a 30-second request abort, and typed resource clients. Treat a route change and its matching client method as one change.

## Normal chat graph

`backend/orchestrator/graph.py` builds this synchronous LangGraph path:

```text
context_builder → intent_classifier ─┬→ deep_research ─┐
                                     └→ tool_planner → tool_execution ─┐
                                                      ↑                 │
                                                      └── (up to cap) ──┘
                                                       → esl_gateway
                                                          ├→ response_formatter → END
                                                          └→ explain_veto → END
```

`AgentState` (`backend/orchestrator/state.py`) carries input, user/context history, selected sources, planned and executed tools, ReAct trace, citations, document citations, ESL decision, output events, and loop counters. The planner increments `planner_step`; the router stops tool replanning at `max_planner_steps` (default 3) even if the model asks for more. This guard was reinforced by the most recent planner-termination fix.

`GET /api/chat/stream` (`backend/routes/chat.py`) turns graph events into SSE. It accepts an optional conversation, comma-separated active sources, model, and `force_retrieval`; the UI’s `/ask` behavior sets the last flag to require document search.

## Ethical and action safety layers

### Response gate — always in the graph

`EthicalSafeguardLayer.evaluate_action()` (`backend/esl/engine.py`) retrieves user context and applies time, manipulation, engagement, and topic checks. It returns `APPROVED`, `MODIFIED`, or `VETOED`, and persists an audit decision through its audit logger. The ESL gateway runs after normal planning/tooling and after deep research. A veto routes to `explain_veto`; a modification is applied by the formatter.

### Tool confirmation — streaming-reasoning mode

When streaming reasoning is enabled, tool execution consults user safety preferences: master safe mode, tool category preferences, then individual tool preferences. A confirmation can pause the durable LangGraph thread. `POST /api/chat/resume` continues the thread with `approve`, `skip`, or `cancel`; `trust` relaxes only the individual-tool preference. `backend/routes/safety_preferences.py` exposes the matching settings API.

Marketplace tools retain a separate ESL tool-gate/pending-confirmation path. Do not assume a generic streaming interrupt covers all tool invocation types.

## Graph modes and flags

All are configured in `backend/config.py`; the safe/legacy behavior is generally the default.

| Control | Default | Effect / change caution |
|---|---:|---|
| `USE_LANGGRAPH` | true | LangGraph is the only configured orchestrator. |
| `PLANNER_PARALLEL_ENABLED` | false | Planner emits action batches and executor uses parallel gather/retry only when enabled. |
| `STREAMING_REASONING_ENABLED` | false | Enables streamed thought/action events and interrupt/checkpointer behavior. Requires checkpoint reliability for resume semantics. |
| `EPISODIC_MEMORY_ENABLED` | false | Adds retrieved completed planner runs to the planning prompt; controls have top-K 3, score floor 0.6, 90-day window. |
| `MULTI_AGENT` environment variable | false | Selects supervisor/workers (research, calendar, goals, document, connectors). Streaming reasoning takes precedence and multi-agent is ignored when both are enabled. |

In development/test the streaming checkpointer is in memory. Production attempts `AsyncPostgresSaver` and falls back to memory on failure (`backend/orchestrator/graph.py`). Test both the enabled and disabled paths when changing graph or event behavior.

## Change checklist

- Preserve the **ESL edge** for any new response-producing route or subgraph.
- Preserve the planner cap/duplicate-call safeguards when changing planner/executor routing.
- Update backend route, `frontend/lib/api.ts`, and the consuming page/component together.
- Add SSE ordering/resume coverage for new streamed event types.
- Avoid silently changing feature-flag defaults; describe new operational prerequisites in [operations](operations.md).
