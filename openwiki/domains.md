# Domain concepts and data ownership

## Trust model: values, boundaries, and transparency

The product’s central claim is not merely “AI with guardrails”: user values drive a mandatory Ethical Safeguard Layer. `user_values` stores boundaries, preferences, topic filters, and time windows with priority (`backend/database/schema.sql`). ESL evaluates proposed actions against user context and records decision status, reason, violated values, rules, confidence, and context snapshot in `esl_audit_log`. The Transparency UI and tool telemetry make that decision process inspectable.

Safety preferences introduced with streaming reasoning add three action-confirmation layers: a user safe-mode switch, category preferences, and named-tool preferences. Those are action-execution controls, distinct from response-level ESL evaluation.

## Personal organization

| Concept | Ownership and relationships |
|---|---|
| User/session | Supabase Auth identity is extended by `users`; user session/settings carry focus and preferences. |
| Goals | User-scoped goals have lifecycle state, priority, dates, metadata, and optional milestones. |
| Projects | User-scoped projects can link to a goal. |
| Tasks | User-scoped tasks can link to project and goal; status, priority, due date, source origin, and AI confirmation are stored. |
| Dependencies and rollups | `task_dependencies` represents directed task edges; service code prevents cycles. `v_project_rollup` and `v_goal_rollup` derive progress/risk. |
| Conversations | Named threads and turn metadata preserve chat history, plan traces, and citations used by the UI. |

The canonical work-depth migration is `backend/migrations/011_work_management_depth.sql`; routes are under `backend/routes/` and business helpers under `backend/services/`.

## Context, documents, and memories

- **Source metadata / M1:** Postgres `data_sources` tracks OAuth-backed sources and `source_items` holds normalized user-scoped source records.
- **Retrieval corpus / active M2:** Weaviate `DocumentMemory` contains chunks for uploaded documents and connector material. It is the corpus used by `RagRetrievalService` for chat and search.
- **Legacy/parallel semantic memory:** the baseline schema still defines pgvector `semantic_memory`. It should not be assumed to be the current document-retrieval authority; verify the target feature before writing to or querying it.
- **Planner memory:** `planner_runs` stores ReAct execution traces; optional episodic memory recalls similar completed runs when enabled.

All retrieval must retain user scoping. `RagRetrievalService` explicitly passes `user_id` into Weaviate hybrid search; a change that removes that filter is a data-isolation bug.

## Integration data lifecycle

The intended lifecycle is authenticate → fetch → normalize → persist source item → index chunks → retrieve with citation. Connector status separates connection state from indexed-item count and last item/sync time. Index errors are retained so health surfaces can distinguish pending/failed from empty.

Composio-managed provider actions and native connector sync share the retrieval corpus but do not currently have a completely unified operator API. See the caveat in [workflows](workflows.md).

## Auditable execution records

- `esl_audit_log`: response/action safety decisions.
- `tool_call_events`: append-oriented execution telemetry such as success and latency.
- `planner_runs`: full planning traces; planner-run association is also available on tool events/turn metadata.
- system-health SQL views and retention indexes: operational projections for monitoring/pruning.

Retention is configured as `RETENTION_DAYS` (default 90) in `backend/config.py`. Changes to data collection or tool trace payloads should review privacy, audit, retention, and Transparency rendering together.

## Schema governance caution

Provisioning artifacts coexist: `backend/database/schema.sql`, old `backend/database/migration_*.sql` files, versioned `backend/migrations/*.sql`, and idempotent startup DDL in `backend/main.py`. The migration runner tracks only versioned migration filenames in `schema_migrations`. Prefer a reviewed versioned migration for new persistent changes; do not treat a startup `CREATE TABLE IF NOT EXISTS` as a substitute for an evolvable migration without an explicit decision.
