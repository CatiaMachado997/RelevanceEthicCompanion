# Multi-Agent LangGraph Architecture + Terraform IaC

**Date:** 2026-05-22  
**Status:** Approved  
**Scope:** Upgrade the existing single-agent orchestrator to a proper multi-agent Supervisor architecture and codify all GCP infrastructure as Terraform modules.

---

## 1. Problem Statement

The current `orchestrator/graph.py` is a linear single-agent graph. Intent classification routes to either a tool planner or a deep-research subgraph — every request goes through the same nodes regardless of what kind of work is needed. This creates three concrete problems:

1. **No specialisation** — a calendar lookup and a document Q&A use the same tool pool and the same model, wasting tokens and reducing quality.
2. **Hard to extend** — adding a new capability means editing the monolithic graph rather than dropping in a new agent.
3. **Infrastructure is imperative** — deployment lives in fragile `gcloud` CLI calls inside GitHub Actions; there is no canonical source of truth for what infrastructure exists.

---

## 2. Goals

- Replace `intent_classifier` + `tool_planner` with a **Supervisor** that routes to five specialised worker agents.
- Each worker agent is an independently testable, compiled `create_react_agent` subgraph with its own tool list and model choice.
- The **ESL gateway stays mandatory and unchanged** — every path through the graph must pass through it before producing a response.
- Swap `MemorySaver` for `AsyncPostgresSaver` pointing at the existing PostgreSQL, enabling durable cross-session memory and human-in-the-loop pausing.
- Codify all GCP resources (Cloud Run, Artifact Registry, Secret Manager, IAM) as Terraform modules with a GCS remote state backend.

---

## 3. Non-Goals

- No AWS migration — the project stays on GCP + Supabase + Vercel.
- No change to the ESL rules or audit logic.
- No change to the frontend SSE consumer — the existing `astream_events(version="v2")` contract is preserved; subgraph events bubble up automatically.
- No LangSmith integration — Langfuse already provides observability and is not replaced.

---

## 4. Multi-Agent Architecture

### 4.1 Graph Structure

```
Parent Graph (orchestrator/graph.py)
│
├── context_builder          (unchanged)
│
├── supervisor               (NEW — replaces intent_classifier + tool_planner)
│   ├── research_agent       (upgrades deep_research subgraph)
│   ├── calendar_agent       (NEW)
│   ├── goals_agent          (NEW)
│   ├── document_agent       (NEW)
│   └── connectors_agent     (NEW)
│
├── esl_gateway              (unchanged — mandatory gate)
├── response_formatter       (unchanged)
└── explain_veto             (unchanged)
```

The Supervisor is a `create_react_agent` instance whose tools are the five worker agents. It uses tool-calling routing: the Supervisor LLM decides which worker(s) to invoke and in what order; results return to the Supervisor for synthesis before the ESL gate. No `Command.PARENT` handoffs — the Supervisor owns the full conversation thread.

### 4.2 Worker Agents

| Agent | File | Tools | Model |
|---|---|---|---|
| `research_agent` | `orchestrator/agents/research.py` | Tavily search, web fetch, `relevance_engine` | Llama 3.3 70B |
| `calendar_agent` | `orchestrator/agents/calendar.py` | `google_calendar_sync.py` read/write tools | Llama 3.1 8B |
| `goals_agent` | `orchestrator/agents/goals.py` | `user_values` DB read, goal CRUD | Llama 3.1 8B |
| `document_agent` | `orchestrator/agents/document.py` | `document_processor.py`, PDF Q&A, pgvector search | Llama 3.3 70B |
| `connectors_agent` | `orchestrator/agents/connectors.py` | Composio (Slack, Gmail, etc.) | Llama 3.1 8B |

Each agent file exposes a single `build_agent(llm, checkpointer) -> CompiledGraph` factory function.

### 4.3 Supervisor Routing

The Supervisor is initialised with a lightweight model (Llama 3.1 8B or Gemini Flash) for routing decisions, keeping the overhead low. It receives the full `AgentState` context (user values, conversation history, active sources) so routing decisions respect user boundaries before any worker runs.

```python
# orchestrator/agents/supervisor.py
from langgraph_supervisor import create_supervisor

supervisor = create_supervisor(
    agents=[research_agent, calendar_agent, goals_agent, document_agent, connectors_agent],
    model=routing_llm,
    prompt=SUPERVISOR_SYSTEM_PROMPT,
)
```

`SUPERVISOR_SYSTEM_PROMPT` explicitly instructs the Supervisor never to route to connectors that the user has not authorised in their `active_sources` list — a pre-ESL ethical guardrail.

### 4.4 State Changes

`AgentState` (`orchestrator/state.py`) gains three fields; all existing fields are preserved:

```python
class AgentState(TypedDict):
    # ... all existing fields unchanged ...

    # Multi-agent additions
    messages: Annotated[list, add_messages]  # canonical message thread
    active_agent: str                         # name of currently-running agent
    agent_outputs: dict[str, str]             # {agent_name: synthesised_text}
```

`messages` uses the `add_messages` reducer so concurrent agent writes are safely merged. The existing `response_text`, `tool_results`, and `citations` fields continue to be the contract for the ESL gateway and formatter nodes.

### 4.5 Checkpointing

```python
# orchestrator/graph.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def get_checkpointer():
    return await AsyncPostgresSaver.from_conn_string(settings.database_url)
```

`MemorySaver` is used in tests (via `pytest` fixture injection). Production always uses `AsyncPostgresSaver`. The checkpointer replaces the manual `_post_stream_store` function — LangGraph handles persistence automatically at every node boundary.

A `thread_id` (mapped from `conversation_id`) is passed in the graph config on every `astream_events` call, giving automatic cross-session memory replay.

### 4.6 Streaming Contract

No changes to the SSE route or frontend. Events from worker agent subgraphs automatically appear in the parent's `astream_events(version="v2")` stream. The `langgraph_node` metadata field in each event identifies which agent produced the token, allowing the frontend to optionally show which agent is active.

```python
# Already works — no code change needed
async for event in graph.astream_events(initial_state, config={"configurable": {"thread_id": conversation_id}}, version="v2"):
    node = event["metadata"].get("langgraph_node", "")
    # node is now e.g. "research_agent", "calendar_agent", etc.
```

---

## 5. File Layout Changes

```
backend/orchestrator/
├── graph.py          (modified — wires Supervisor into parent graph)
├── state.py          (modified — adds messages, active_agent, agent_outputs)
├── token_tracker.py  (unchanged)
├── nodes/
│   ├── context.py    (unchanged)
│   ├── esl.py        (unchanged)
│   ├── intent.py     (DELETED — replaced by Supervisor)
│   ├── response.py   (unchanged)
│   └── tools.py      (DELETED — tools moved into individual agents)
├── agents/           (NEW directory)
│   ├── __init__.py
│   ├── supervisor.py
│   ├── research.py
│   ├── calendar.py
│   ├── goals.py
│   ├── document.py
│   └── connectors.py
└── subgraphs/
    └── deep_research.py  (absorbed into research_agent, file deleted after migration)
```

---

## 6. Terraform Infrastructure

### 6.1 Directory Structure

```
infra/
├── backend.tf              ← GCS bucket remote state (team locking)
├── main.tf                 ← root module composition
├── variables.tf
├── outputs.tf
├── environments/
│   ├── dev.tfvars
│   └── prod.tfvars
└── modules/
    ├── cloud-run/          ← Cloud Run service, traffic splitting, health checks
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── artifact-registry/  ← Docker image repository
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    ├── secrets/            ← Secret Manager secrets + IAM bindings
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── iam/                ← Least-privilege service accounts
        ├── main.tf
        ├── variables.tf
        └── outputs.tf
```

### 6.2 Remote State Backend

```hcl
# infra/backend.tf
terraform {
  backend "gcs" {
    bucket = "ethic-companion-tfstate"
    prefix = "terraform/state"
  }
}
```

The GCS bucket is created once manually (bootstrap) and checked into git. All subsequent changes go through `terraform plan` → review → `terraform apply`.

### 6.3 Resource Coverage

**`modules/cloud-run`** provisions:
- Cloud Run v2 service with container image from Artifact Registry
- Traffic splitting (new revision gets 0% traffic until health check passes)
- Min/max instance configuration per environment
- VPC connector reference for private PostgreSQL access
- Secret Manager secret references injected as environment variables

**`modules/artifact-registry`** provisions:
- Docker repository in the project region
- IAM binding for the Cloud Run service account to pull images

**`modules/secrets`** provisions:
- One `google_secret_manager_secret` + `google_secret_manager_secret_version` per API key
- IAM binding: Cloud Run service account gets `secretmanager.secretAccessor` on each secret

**`modules/iam`** provisions:
- `ethic-companion-backend` service account (replaces default compute SA)
- Roles: `run.invoker`, `cloudsql.client`, `secretmanager.secretAccessor`, `artifactregistry.reader`

### 6.4 GitHub Actions Integration

The existing `deploy-backend.yml` workflow is updated:

```yaml
- name: Terraform plan
  run: terraform -chdir=infra plan -var-file=environments/prod.tfvars -out=tfplan

- name: Terraform apply
  run: terraform -chdir=infra apply tfplan
```

`gcloud run deploy` and `gcloud run services update-traffic` calls are removed — Terraform owns the Cloud Run resource state. The `Build and push Docker image` step remains (image building stays in CI, Terraform only references the image tag).

---

## 7. Dependencies to Add

```
# requirements.txt additions
langgraph-supervisor>=0.1.0
langgraph[postgres]>=0.2.0   # pulls AsyncPostgresSaver
```

```
# infra — no Python deps, Terraform binary only
# Terraform >= 1.7, hashicorp/google provider >= 6.0
```

---

## 8. Testing Strategy

- Each `build_agent()` factory is unit-tested with `MemorySaver` and a mock LLM — no database required.
- The parent graph is integration-tested end-to-end with `AsyncPostgresSaver` pointed at the test PostgreSQL container (already spun up in CI).
- ESL tests (`tests/test_esl.py`) are unchanged — the ESL gateway node interface does not change.
- Terraform: `terraform validate` + `terraform plan` run in CI against dev vars; no `terraform apply` in CI without manual approval.

---

## 9. Migration Path

1. Add `agents/` directory with all five agents and `supervisor.py` — no existing code touched yet.
2. Wire Supervisor into `graph.py` behind a feature flag (`MULTI_AGENT=true` env var) so the old graph stays live during rollout.
3. Run both graphs in parallel in staging, compare ESL decision quality and latency.
4. Flip flag in production, monitor for 48h, then delete `nodes/intent.py`, `nodes/tools.py`, and `subgraphs/deep_research.py`.
5. Land Terraform in a separate PR: bootstrap GCS bucket → `terraform import` existing Cloud Run + Artifact Registry resources → replace gcloud calls in CI.
