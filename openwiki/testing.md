# Testing and change verification

## Fast paths

```bash
make test    # backend pytest tests/ -v, then frontend Jest
make lint    # Black check, Flake8, mypy, then frontend ESLint
```

For a release-quality local check, also run from `frontend/`:

```bash
npx tsc --noEmit
npm run build
```

CI is the authoritative composite gate in `.github/workflows/ci.yml`: it starts Postgres and Weaviate for backend tests, initializes the schema, runs backend coverage, runs ESL tests with `--cov-fail-under=75`, then lints/type-checks/builds the frontend.

## Test layers and anchors

| Change area | Start with | Important behavior |
|---|---|---|
| ESL rules/audit | `backend/tests/test_esl.py` | Critical coverage threshold; approval/veto/modification and audit outcomes. |
| Graph shape/routing | `test_langgraph_orchestrator.py` | context/intent/planner/ESL edges, multi-agent/checkpointer selection. |
| Planner termination | `test_planner_loop.py` | chaining, three-step cap, duplicate-call early stop. |
| Tool execution | `test_tool_planner_parallel.py`, `test_execute_with_retry.py` | serial versus parallel flags, one retry, telemetry. |
| Streaming/interrupts | `test_streaming.py`, `test_streaming_events.py`, `test_interrupt_flow.py`, `test_chat_stream.py` | SSE ordering, paused state, resume decisions, final `done`. |
| Safety preferences | `test_safety_preferences_service.py`, `test_safety_preferences_route.py` | master/category/tool precedence and persisted API behavior. |
| RAG/indexing | `test_rag_retrieval.py`, `test_connector_indexer.py` | user filter, hybrid/rerank tracing, chunk/index error handling, graceful dependency failure. |
| Connectors | `test_connectors.py` and connector/service tests | status/backfill/disconnect correctness and source ownership. |
| Work management | `test_task_dependencies.py`, route/service tests | dependency cycles, rollups, user isolation. |
| Migrations | `test_migration_runner.py` | ordering, skipping applied entries, idempotency. |
| AutoLab | `test_autolab_runner.py`, `test_autolab_routes.py` | improvement retention, regression reversion, skip/error behavior, route shapes. |
| Frontend | `frontend/__tests__/` | dashboard/page behavior; add a focused Jest test when changing client UX or API event rendering. |

Test file names may be refined over time; locate nearby coverage under `backend/tests/` before introducing duplicate fixtures.

## Scenario checks for risky changes

### Agent or tool changes

- Verify no-tool, one-tool, chained-tool, failed-tool/retry, and cap-reached turns.
- Verify ESL `APPROVED`, `MODIFIED`, and `VETOED` outcomes.
- With streaming disabled, confirm legacy path remains stable. With it enabled, confirm pause/resume for approve, skip, cancel, and tool-specific trust.
- Check the UI’s transparency/tool-call presentation and citation cards, not just backend events.

### Retrieval or connector changes

- Prove per-user filtering with fixtures for two users.
- Cover Weaviate unavailable and embedding/reranker failure paths; chat should still finish.
- Confirm chunk citation source type reaches API client/UI.
- Test sync status, index error persistence, retry and disconnect/wipe behavior.

### Schema or rollout changes

- Run migration runner unit coverage plus a fresh local bootstrap and an upgrade path when feasible.
- Keep `make migrate-dry` in the review procedure.
- For flags, test both defaults and enabled state; defaults are part of compatibility.

## Existing validation signal

Recent history records a live-validation fix for planner termination, episodic memory, and feature-flag/UI gaps after the Sprint I–K agent enhancements. Use that context to treat planner loop, state persistence, and flag interactions as regression-prone rather than “already solved.”
