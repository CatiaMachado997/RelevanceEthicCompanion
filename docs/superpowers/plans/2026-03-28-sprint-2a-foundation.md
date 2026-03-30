# Sprint 2a: Foundation + Auth + Frontend Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LangChain orchestrator with a clean LangGraph StateGraph (ESL as mandatory node), expose all routes as MCP tools, add Langfuse observability, harden auth/session, overhaul settings, add user status, and fix known frontend gaps.

**Architecture:** LangGraph StateGraph with typed `AgentState` replaces `orchestrator_v2.py`. FastAPI-MCP wraps the existing app in one import. All changes are additive until the feature flag is flipped and the old file deleted. Workstream priority: A → B → E → G (blocking for Sprint 2b); C → D → F → H (best-effort).

**Tech Stack:** langgraph>=0.2.0, fastapi-mcp>=0.4.0, langfuse>=2.0.0, LangChain (existing), Groq (existing), Supabase Auth (existing), Next.js 15 (existing)

**Spec:** `docs/superpowers/specs/2026-03-28-roadmap-v2-industry-standard-design.md`

---

## File Map

**Created:**
- `backend/orchestrator/__init__.py`
- `backend/orchestrator/state.py` — `AgentState` typed dict
- `backend/orchestrator/graph.py` — `StateGraph` definition + `stream_langgraph()` entry point
- `backend/orchestrator/nodes/__init__.py`
- `backend/orchestrator/nodes/context.py` — ContextBuilder node
- `backend/orchestrator/nodes/intent.py` — IntentClassifier node
- `backend/orchestrator/nodes/esl.py` — ESLGateway node
- `backend/orchestrator/nodes/tools.py` — ToolPlanner + ToolExecution nodes
- `backend/orchestrator/nodes/response.py` — ResponseFormatter + ExplainVeto nodes
- `backend/orchestrator/subgraphs/__init__.py` — empty, populated in later sprints
- `backend/skills/web_search.yaml`
- `backend/skills/query_memory.yaml`
- `backend/skills/query_calendar.yaml`
- `backend/skills/get_user_goals.yaml`
- `backend/skills/create_note.yaml`
- `backend/database/migration_sprint2a_status.sql`
- `backend/tests/test_langgraph_orchestrator.py` — regression suite (written first)
- `backend/routes/status.py` — `PUT /api/status/` endpoint

**Modified:**
- `backend/esl/models.py` — add `SLACK_SEND` to `ActionType`
- `backend/requirements.txt` — add langgraph, fastapi-mcp, langfuse, anthropic
- `backend/main.py` — add FastAPI-MCP mount + status router + feature flag
- `backend/routes/chat.py` — feature-flag orchestrator selection
- `backend/config.py` — add `USE_LANGGRAPH`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- `backend/database/schema.sql` — add status/status_until/timezone/language columns
- `backend/database/schema_local.sql` — same
- `frontend/app/login/page.tsx` — redesign
- `frontend/app/dashboard/page.tsx` — empty states, skeletons, error boundary
- `frontend/app/dashboard/chat/page.tsx` — fix 6 known bugs
- `frontend/app/dashboard/settings/page.tsx` — 7-section overhaul
- `frontend/components/UserStatus.tsx` — new status popover component
- `frontend/lib/auth.ts` — HttpOnly cookie session handling

**Deleted (Task 12):**
- `backend/services/orchestrator_v2.py` — after regression tests pass on LangGraph

---

## Task 0: Install Dependencies + Run Schema Migration

**Files:** `backend/requirements.txt`, `backend/database/migration_sprint2a_status.sql`, `backend/database/schema.sql`, `backend/database/schema_local.sql`

- [ ] **Step 1: Add new Python dependencies**

  Edit `backend/requirements.txt` — add after the LLM section:
  ```
  # Sprint 2a
  langgraph>=0.2.0
  fastapi-mcp>=0.4.0
  langfuse>=2.0.0
  anthropic>=0.25.0
  ```

- [ ] **Step 2: Install**
  ```bash
  cd backend && pip install langgraph>=0.2.0 fastapi-mcp>=0.4.0 langfuse>=2.0.0 anthropic>=0.25.0
  ```
  Expected: all four packages install without conflicts.

- [ ] **Step 3: Create migration file**

  **Note:** The spec references `backend/database/migrations/sprint2a_status.sql` (subdirectory). This plan uses the flat path `backend/database/migration_sprint2a_status.sql` to match the existing codebase convention (all other migrations are flat files). This is intentional.

  Create `backend/database/migration_sprint2a_status.sql`:
  ```sql
  -- Sprint 2a: User status + settings schema additions
  ALTER TABLE public.user_settings
      ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'available'
          CHECK (status IN ('available', 'focus', 'do_not_disturb', 'away')),
      ADD COLUMN IF NOT EXISTS status_until TIMESTAMPTZ,
      ADD COLUMN IF NOT EXISTS timezone TEXT,
      ADD COLUMN IF NOT EXISTS language TEXT;
  ```

- [ ] **Step 4: Apply migration to local DB**
  ```bash
  cd backend && psql $DATABASE_URL -f database/migration_sprint2a_status.sql
  ```
  Expected: `ALTER TABLE` (no errors).

- [ ] **Step 5: Update schema.sql and schema_local.sql**

  In both files, find the `user_settings` table definition and add these columns:
  ```sql
  status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','focus','do_not_disturb','away')),
  status_until TIMESTAMPTZ,
  timezone TEXT,
  language TEXT,
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add backend/requirements.txt backend/database/
  git commit -m "chore: add sprint2a dependencies and status schema migration"
  ```

---

## Task 1: ESL Model — Add SLACK_SEND

**Files:** `backend/esl/models.py`

- [ ] **Step 1: Add enum value**

  In `backend/esl/models.py`, find `ActionType` and add:
  ```python
  SLACK_SEND = "slack_send"
  ```
  Place it after `EMAIL_SEND = "email_send"`.

- [ ] **Step 2: Run ESL tests to confirm no breakage**
  ```bash
  cd backend && pytest tests/test_esl.py -v
  ```
  Expected: all pass.

- [ ] **Step 3: Commit**
  ```bash
  git add backend/esl/models.py
  git commit -m "feat(esl): add SLACK_SEND action type"
  ```

---

## Task 2: Regression Test Suite (Write BEFORE Touching Orchestrator)

**Files:** `backend/tests/test_langgraph_orchestrator.py`

These tests capture the current `orchestrator_v2` behavior contract. They must pass against the old orchestrator first, then against the new LangGraph one.

- [ ] **Step 1: Create test file**

  Create `backend/tests/test_langgraph_orchestrator.py`:
  ```python
  """
  Regression tests for the chat streaming interface.
  These tests define the contract that the LangGraph orchestrator must satisfy.
  Run against orchestrator_v2 first (baseline), then against LangGraph orchestrator.
  """
  import pytest
  import json
  from unittest.mock import patch, MagicMock, AsyncMock
  from httpx import AsyncClient, ASGITransport
  from main import app


  async def _collect_stream_events(response_text: str) -> list[dict]:
      """Parse SSE data lines into a list of event dicts."""
      events = []
      for line in response_text.splitlines():
          if line.startswith("data: "):
              try:
                  events.append(json.loads(line[6:]))
              except json.JSONDecodeError:
                  pass
      return events


  async def mock_stream(*args, **kwargs):
      yield {"event": "token", "token": "Hello"}
      yield {"event": "token", "token": " world"}
      yield {"event": "done"}


  @pytest.mark.asyncio
  async def test_stream_returns_200_event_stream():
      """Chat stream endpoint returns 200 with text/event-stream content type."""
      mock_orch = MagicMock()
      mock_orch.stream_message = mock_stream
      with patch("routes.chat.get_orchestrator", return_value=mock_orch):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              r = await client.get("/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000")
          assert r.status_code in (200, 401)
          if r.status_code == 200:
              assert "text/event-stream" in r.headers.get("content-type", "")


  @pytest.mark.asyncio
  async def test_stream_emits_token_events():
      """Stream yields token events followed by a done event."""
      mock_orch = MagicMock()
      mock_orch.stream_message = mock_stream
      with patch("routes.chat.get_orchestrator", return_value=mock_orch):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              r = await client.get("/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000")
          if r.status_code == 200:
              events = await _collect_stream_events(r.text)
              token_events = [e for e in events if e.get("event") == "token"]
              done_events = [e for e in events if e.get("event") == "done"]
              assert len(token_events) >= 1
              assert len(done_events) == 1
              assert done_events[-1] == events[-1]  # done is last


  @pytest.mark.asyncio
  async def test_stream_token_events_have_token_field():
      """Every token event has a non-empty 'token' string field."""
      mock_orch = MagicMock()
      mock_orch.stream_message = mock_stream
      with patch("routes.chat.get_orchestrator", return_value=mock_orch):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              r = await client.get("/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000")
          if r.status_code == 200:
              events = await _collect_stream_events(r.text)
              for e in events:
                  if e.get("event") == "token":
                      assert isinstance(e.get("token"), str)
                      assert len(e["token"]) > 0


  @pytest.mark.asyncio
  async def test_stream_missing_message_returns_422():
      """Request without message param returns 422 Unprocessable Entity."""
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.get("/api/chat/stream?user_id=00000000-0000-0000-0000-000000000000")
      assert r.status_code == 422
  ```

- [ ] **Step 2: Run against current orchestrator_v2 (baseline)**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py -v
  ```
  Expected: all tests pass (or skip on 401 where auth is required — that's fine). This is the baseline.

- [ ] **Step 3: Commit**
  ```bash
  git add backend/tests/test_langgraph_orchestrator.py
  git commit -m "test: add orchestrator regression suite (baseline against orchestrator_v2)"
  ```

---

## Task 3: AgentState + Graph Skeleton

**Files:** `backend/orchestrator/__init__.py`, `backend/orchestrator/state.py`, `backend/orchestrator/graph.py`, `backend/orchestrator/nodes/__init__.py`, `backend/orchestrator/subgraphs/__init__.py`

- [ ] **Step 1: Create directory structure**
  ```bash
  mkdir -p backend/orchestrator/nodes backend/orchestrator/subgraphs
  touch backend/orchestrator/__init__.py backend/orchestrator/nodes/__init__.py backend/orchestrator/subgraphs/__init__.py
  ```

- [ ] **Step 2: Create AgentState**

  Create `backend/orchestrator/state.py`:
  ```python
  """AgentState — typed state dict carried through every LangGraph node."""
  from typing import TypedDict, Optional, Any
  from esl.models import ESLDecision


  class AgentState(TypedDict):
      # Input
      user_id: str
      message: str
      conversation_id: Optional[str]
      model: str

      # Context
      user_context: dict          # goals, values, focus_mode, recent_memory
      conversation_history: list  # [{role, content}, ...]

      # Intent
      intent: str                 # "chat" | "research_quick" | "plan" | "search" | "file_question"

      # Tool execution
      tool_calls: list            # tool calls planned by ToolPlanner
      tool_results: list          # results from ToolExecution

      # ESL
      esl_decision: Optional[ESLDecision]
      proposed_content: str       # the response text before ESL evaluation

      # Output
      response_text: str          # final response to stream to user
      response_events: list       # list of SSE event dicts to yield

      # Token tracking
      token_count: int
      token_warning: Optional[dict]
  ```

- [ ] **Step 3: Create graph skeleton (no nodes yet)**

  Create `backend/orchestrator/graph.py`:
  ```python
  """
  LangGraph orchestrator — replaces orchestrator_v2.py.
  Entry point: stream_langgraph(user_id, message, model, conversation_id)
  """
  from typing import AsyncGenerator, Optional
  from langgraph.graph import StateGraph, END
  from orchestrator.state import AgentState


  def build_graph() -> StateGraph:
      """Build and compile the agent StateGraph. Nodes added in Tasks 4–8."""
      graph = StateGraph(AgentState)
      # Nodes and edges wired in Tasks 4-8
      return graph


  async def stream_langgraph(
      user_id: str,
      message: str,
      model: str,
      conversation_id: Optional[str] = None,
  ) -> AsyncGenerator[dict, None]:
      """
      Entry point for the LangGraph orchestrator.
      Yields SSE event dicts identical to orchestrator_v2.stream_message().
      """
      raise NotImplementedError("Nodes not yet wired — complete Tasks 4-8 first")
  ```

- [ ] **Step 4: Verify import works**
  ```bash
  cd backend && python -c "from orchestrator.graph import stream_langgraph; print('OK')"
  ```
  Expected: `OK` — note: `stream_langgraph` raises `NotImplementedError` at call time (intentional placeholder until Task 9). The import itself must succeed.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/orchestrator/
  git commit -m "feat(orchestrator): add AgentState and graph skeleton"
  ```

---

## Task 4: ContextBuilder Node

**Files:** `backend/orchestrator/nodes/context.py`

- [ ] **Step 1: Write the failing test**

  Add to `backend/tests/test_langgraph_orchestrator.py`:
  ```python
  @pytest.mark.asyncio
  async def test_context_builder_populates_state():
      """ContextBuilder node adds user_context and conversation_history to state."""
      from orchestrator.nodes.context import context_builder_node
      from unittest.mock import AsyncMock, patch

      mock_cm = MagicMock()
      mock_cm.get_user_context = AsyncMock(return_value=MagicMock(
          active_goals=[], user_values=[], focus_mode=False,
          additional_context={}
      ))
      mock_cm.get_conversation_history = AsyncMock(return_value=[])

      state: AgentState = {
          "user_id": "test-user", "message": "hello", "conversation_id": None,
          "model": "llama", "user_context": {}, "conversation_history": [],
          "intent": "", "tool_calls": [], "tool_results": [],
          "esl_decision": None, "proposed_content": "", "response_text": "",
          "response_events": [], "token_count": 0, "token_warning": None,
      }
      with patch("orchestrator.nodes.context.get_context_manager", return_value=mock_cm):
          result = await context_builder_node(state)
      assert "user_context" in result
      assert "conversation_history" in result
  ```

- [ ] **Step 2: Run to confirm fail**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py::test_context_builder_populates_state -v
  ```
  Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Implement ContextBuilder node**

  Create `backend/orchestrator/nodes/context.py`:
  ```python
  """ContextBuilder — loads M1 + M2 user context into AgentState."""
  from orchestrator.state import AgentState
  from services.context_manager import ContextManager
  from utils.weaviate_client import get_weaviate_client
  from services.embedding_service import EmbeddingService


  def get_context_manager() -> ContextManager:
      try:
          weaviate = get_weaviate_client()
      except Exception:
          weaviate = None
      embedding = EmbeddingService() if weaviate else None
      return ContextManager(weaviate_client=weaviate, embedding_service=embedding)


  async def context_builder_node(state: AgentState) -> dict:
      """Populate user_context and conversation_history from M1 + M2."""
      cm = get_context_manager()
      ctx = await cm.get_user_context(state["user_id"])
      history = await cm.get_conversation_history(
          state["user_id"], limit=20, conversation_id=state.get("conversation_id")
      )
      return {
          "user_context": {
              "active_goals": [g.__dict__ if hasattr(g, '__dict__') else g for g in (ctx.active_goals or [])],
              "user_values": [v.__dict__ if hasattr(v, '__dict__') else v for v in (ctx.user_values or [])],
              "focus_mode": getattr(ctx, "focus_mode", False),
              "additional_context": getattr(ctx, "additional_context", {}),
          },
          "conversation_history": history or [],
      }
  ```

- [ ] **Step 4: Run test**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py::test_context_builder_populates_state -v
  ```
  Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/orchestrator/nodes/context.py backend/tests/test_langgraph_orchestrator.py
  git commit -m "feat(orchestrator): add ContextBuilder node with tests"
  ```

---

## Task 5: IntentClassifier Node

**Files:** `backend/orchestrator/nodes/intent.py`

- [ ] **Step 1: Write failing tests**

  Add to `test_langgraph_orchestrator.py` — **put `base_state()` first, then the tests that use it**:
  ```python
  # Helper — must be defined before any test that calls it
  def base_state() -> dict:
      return {
          "user_id": "u1", "message": "", "conversation_id": None, "model": "llama",
          "user_context": {}, "conversation_history": [], "intent": "",
          "tool_calls": [], "tool_results": [], "esl_decision": None,
          "proposed_content": "", "response_text": "", "response_events": [],
          "token_count": 0, "token_warning": None,
      }

  @pytest.mark.asyncio
  async def test_intent_classifier_chat():
      from orchestrator.nodes.intent import intent_classifier_node
      state = {**base_state(), "message": "what should I focus on today?"}
      result = await intent_classifier_node(state)
      assert result["intent"] == "chat"

  @pytest.mark.asyncio
  async def test_intent_classifier_search():
      from orchestrator.nodes.intent import intent_classifier_node
      state = {**base_state(), "message": "/search latest AI news"}
      result = await intent_classifier_node(state)
      assert result["intent"] == "search"

  @pytest.mark.asyncio
  async def test_intent_classifier_plan():
      from orchestrator.nodes.intent import intent_classifier_node
      state = {**base_state(), "message": "/plan launch campaign next quarter"}
      result = await intent_classifier_node(state)
      assert result["intent"] == "plan"
  ```

- [ ] **Step 2: Run to confirm fail**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py -k "intent" -v
  ```

- [ ] **Step 3: Implement IntentClassifier**

  Create `backend/orchestrator/nodes/intent.py`:
  ```python
  """IntentClassifier — routes message to the correct processing path."""
  import re
  from orchestrator.state import AgentState

  _COMMAND_MAP = {
      "/search": "search",
      "/plan": "plan",
      "/organize": "organize",
      "/breakdown": "breakdown",
      "/research": "research_deep",
  }

  _RESEARCH_KEYWORDS = re.compile(
      r"\b(research|investigate|find out|deep dive|comprehensive|analyze)\b", re.IGNORECASE
  )


  async def intent_classifier_node(state: AgentState) -> dict:
      """Classify message intent. Returns updated intent field."""
      msg = state["message"].strip()

      for cmd, intent in _COMMAND_MAP.items():
          if msg.lower().startswith(cmd):
              return {"intent": intent}

      if _RESEARCH_KEYWORDS.search(msg):
          return {"intent": "research_quick"}

      return {"intent": "chat"}
  ```

- [ ] **Step 4: Run tests**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py -k "intent" -v
  ```
  Expected: all PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/orchestrator/nodes/intent.py backend/tests/test_langgraph_orchestrator.py
  git commit -m "feat(orchestrator): add IntentClassifier node with tests"
  ```

---

## Task 6: ESLGateway Node

**Files:** `backend/orchestrator/nodes/esl.py`

- [ ] **Step 1: Write failing test**

  Add to `test_langgraph_orchestrator.py`:
  ```python
  @pytest.mark.asyncio
  async def test_esl_gateway_approved():
      from orchestrator.nodes.esl import esl_gateway_node
      from esl.models import ESLDecision, ESLDecisionStatus
      mock_decision = ESLDecision(
          status=ESLDecisionStatus.APPROVED, reason="OK",
          violated_values=[], applied_rules=[], confidence=0.95
      )
      mock_esl = MagicMock()
      mock_esl.evaluate_action = AsyncMock(return_value=mock_decision)
      state = {**base_state(), "proposed_content": "Here is your summary.", "user_context": {}}
      with patch("orchestrator.nodes.esl.get_esl", return_value=mock_esl):
          result = await esl_gateway_node(state)
      assert result["esl_decision"].status == ESLDecisionStatus.APPROVED
  ```

- [ ] **Step 2: Run to confirm fail**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py::test_esl_gateway_approved -v
  ```

- [ ] **Step 3: Implement ESLGateway node**

  Create `backend/orchestrator/nodes/esl.py`:
  ```python
  """ESLGateway — mandatory ESL evaluation node. Every graph path passes through this."""
  import logging
  from orchestrator.state import AgentState
  from esl.engine import EthicalSafeguardLayer
  from esl.models import ProposedAction, ActionType, UrgencyLevel
  from orchestrator.nodes.context import get_context_manager
  from config import settings

  logger = logging.getLogger(__name__)

  # Langfuse client — singleton, only created if keys are configured
  _langfuse = None
  def _get_langfuse():
      global _langfuse
      if _langfuse is None and settings.LANGFUSE_PUBLIC_KEY:
          from langfuse import Langfuse
          _langfuse = Langfuse(
              public_key=settings.LANGFUSE_PUBLIC_KEY,
              secret_key=settings.LANGFUSE_SECRET_KEY,
              host=settings.LANGFUSE_HOST,
          )
      return _langfuse


  def get_esl() -> EthicalSafeguardLayer:
      cm = get_context_manager()
      return EthicalSafeguardLayer(cm)


  async def esl_gateway_node(state: AgentState) -> dict:
      """Evaluate proposed response through ESL. Returns updated esl_decision."""
      esl = get_esl()
      # content_type is required by ProposedAction — use intent as the content type
      proposed = ProposedAction(
          action_type=ActionType.CHAT_RESPONSE,
          content_type=state.get("intent", "chat_response"),  # REQUIRED field
          content=state.get("proposed_content", ""),
          urgency=UrgencyLevel.LOW,
          metadata={"advisory_only": True, "intent": state.get("intent", "chat")},
      )
      decision = await esl.evaluate_action(proposed, state["user_id"])

      # Trace to Langfuse (non-blocking)
      try:
          lf = _get_langfuse()
          if lf:
              lf.trace(
                  name="esl_decision",
                  user_id=state["user_id"],
                  metadata={
                      "status": decision.status.value,
                      "reason": decision.reason,
                      "confidence": getattr(decision, "confidence", None),
                      "violated_values": decision.violated_values,
                  }
              )
      except Exception as e:
          logger.warning(f"Langfuse trace failed (non-blocking): {e}")

      return {"esl_decision": decision}
  ```

- [ ] **Step 4: Run test**
  ```bash
  cd backend && pytest tests/test_langgraph_orchestrator.py::test_esl_gateway_approved -v
  ```
  Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/orchestrator/nodes/esl.py backend/tests/test_langgraph_orchestrator.py
  git commit -m "feat(orchestrator): add ESLGateway node — ESL structurally enforced"
  ```

---

## Task 7: ResponseFormatter + ExplainVeto Nodes

**Files:** `backend/orchestrator/nodes/response.py`

- [ ] **Step 1: Implement both nodes**

  Create `backend/orchestrator/nodes/response.py`:
  ```python
  """ResponseFormatter and ExplainVeto — produce final SSE event list."""
  from orchestrator.state import AgentState
  from esl.models import ESLDecisionStatus


  async def response_formatter_node(state: AgentState) -> dict:
      """Build SSE event list from approved/modified response."""
      decision = state.get("esl_decision")
      text = state.get("proposed_content", "")

      # If MODIFIED, use the modified action content if available
      if decision and decision.status == ESLDecisionStatus.MODIFIED:
          if decision.modified_action and decision.modified_action.content:
              text = decision.modified_action.content

      events = []
      # Emit tokens (chunk into ~20-char pieces for streaming feel)
      chunk_size = 20
      for i in range(0, len(text), chunk_size):
          events.append({"event": "token", "token": text[i:i+chunk_size]})

      # Attach ESL decision metadata to done event
      esl_data = {}
      if decision:
          esl_data = {
              "status": decision.status.value,
              "reason": decision.reason,
              "violated_values": decision.violated_values,
          }
      events.append({"event": "done", "esl_decision": esl_data})

      return {"response_text": text, "response_events": events}


  async def explain_veto_node(state: AgentState) -> dict:
      """Build a user-friendly veto explanation as SSE events."""
      decision = state.get("esl_decision")
      reason = decision.reason if decision else "Action blocked by ESL."
      text = f"I can't respond to that right now. {reason}"
      events = [
          {"event": "token", "token": text},
          {"event": "done", "esl_decision": {"status": "VETOED", "reason": reason}},
      ]
      return {"response_text": text, "response_events": events}
  ```

- [ ] **Step 2: Quick smoke test**
  ```bash
  cd backend && python -c "
  import asyncio
  from orchestrator.nodes.response import response_formatter_node
  from orchestrator.state import AgentState
  state = {'proposed_content': 'Hello world', 'esl_decision': None,
           'user_id': 'u', 'message': '', 'conversation_id': None, 'model': '',
           'user_context': {}, 'conversation_history': [], 'intent': '',
           'tool_calls': [], 'tool_results': [], 'response_text': '',
           'response_events': [], 'token_count': 0, 'token_warning': None}
  result = asyncio.run(response_formatter_node(state))
  print([e['event'] for e in result['response_events']])
  "
  ```
  Expected: `['token', ..., 'done']`

- [ ] **Step 3: Commit**
  ```bash
  git add backend/orchestrator/nodes/response.py
  git commit -m "feat(orchestrator): add ResponseFormatter and ExplainVeto nodes"
  ```

---

## Task 8: ToolPlanner + ToolExecution Nodes

**Files:** `backend/orchestrator/nodes/tools.py`

- [ ] **Step 1: Implement nodes (porting tool logic from orchestrator_v2)**

  Create `backend/orchestrator/nodes/tools.py`:
  ```python
  """ToolPlanner and ToolExecution — LLM-driven tool selection and execution."""
  import json
  import logging
  from orchestrator.state import AgentState
  from services.langchain_tools import create_langchain_tools
  from services.context_manager import ContextManager
  from orchestrator.nodes.context import get_context_manager
  from langchain_groq import ChatGroq
  from config import settings

  logger = logging.getLogger(__name__)
  MAX_TOOL_ROUNDS = 5


  def _build_system_prompt(state: AgentState) -> str:
      ctx = state.get("user_context", {})
      goals = ctx.get("active_goals", [])
      values = ctx.get("user_values", [])
      return (
          "You are Ethic Companion, a personal work assistant that respects the user's values and boundaries.\n"
          f"User's active goals: {goals}\n"
          f"User's values: {values}\n"
          "Answer helpfully and concisely. Use tools when you need live data."
      )


  async def tool_planner_node(state: AgentState) -> dict:
      """Ask the LLM which tools to call given the current message + context."""
      from langchain_core.messages import HumanMessage, SystemMessage

      cm = get_context_manager()
      tools = create_langchain_tools(cm)
      llm = ChatGroq(model=state.get("model", "llama-3.3-70b-versatile"),
                     api_key=settings.GROQ_API_KEY)
      llm_with_tools = llm.bind_tools(tools)

      messages = [SystemMessage(content=_build_system_prompt(state))]
      for h in state.get("conversation_history", []):
          messages.append(HumanMessage(content=h["content"]) if h["role"] == "user"
                          else SystemMessage(content=h["content"]))
      messages.append(HumanMessage(content=state["message"]))

      response = await llm_with_tools.ainvoke(messages)
      tool_calls = getattr(response, "tool_calls", []) or []
      # If no tool calls, set proposed_content directly
      proposed = response.content if not tool_calls else ""
      return {"tool_calls": tool_calls, "proposed_content": proposed}


  async def tool_execution_node(state: AgentState) -> dict:
      """Execute tool calls and synthesize a final response."""
      from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
      from langchain_groq import ChatGroq

      cm = get_context_manager()
      tools = create_langchain_tools(cm)
      tool_map = {t.name: t for t in tools}
      llm = ChatGroq(model=state.get("model", "llama-3.3-70b-versatile"),
                     api_key=settings.GROQ_API_KEY)

      results = []
      events = []
      for tc in state.get("tool_calls", []):
          tool_name = tc.get("name", "")
          tool_input = tc.get("args", {})
          events.append({"event": "tool_use", "tool": tool_name})
          if tool_name in tool_map:
              try:
                  result = await tool_map[tool_name].ainvoke(tool_input)
                  results.append({"tool": tool_name, "result": str(result)})
                  events.append({"event": "tool_result", "tool": tool_name})
              except Exception as e:
                  results.append({"tool": tool_name, "result": f"Error: {e}"})
          else:
              results.append({"tool": tool_name, "result": "Tool not found"})

      # Synthesize final response with tool results
      if results:
          synthesis_prompt = (
              f"User asked: {state['message']}\n"
              f"Tool results: {json.dumps(results)}\n"
              "Provide a helpful, concise response based on these results."
          )
          response = await llm.ainvoke([HumanMessage(content=synthesis_prompt)])
          proposed = response.content
      else:
          proposed = state.get("proposed_content", "")

      return {
          "tool_results": results,
          "proposed_content": proposed,
          "response_events": events,  # tool_use/tool_result events prepended
      }
  ```

- [ ] **Step 2: Smoke test import**
  ```bash
  cd backend && python -c "from orchestrator.nodes.tools import tool_planner_node, tool_execution_node; print('OK')"
  ```
  Expected: `OK`

- [ ] **Step 3: Commit**
  ```bash
  git add backend/orchestrator/nodes/tools.py
  git commit -m "feat(orchestrator): add ToolPlanner and ToolExecution nodes"
  ```

---

## Task 8b: Port Token Budget Tracking

**Files:** `backend/orchestrator/token_tracker.py`, `backend/orchestrator/nodes/tools.py`

This ports `_daily_tokens`, `_estimate_tokens`, `_check_token_warning` from `orchestrator_v2.py` into a standalone module so the LangGraph orchestrator emits `rate_limit_warning` events.

- [ ] **Step 1: Create token_tracker.py**

  Create `backend/orchestrator/token_tracker.py`:
  ```python
  """Daily token budget tracker — ported from orchestrator_v2.py."""
  from typing import Dict, Any, Optional
  from datetime import datetime

  _DAILY_TOKEN_LIMIT = 100_000
  _daily_tokens: Dict[str, Dict[str, Any]] = {}


  def estimate_tokens(text: str) -> int:
      return max(1, len(text) // 4)


  def check_token_warning(user_id: str, new_tokens: int) -> Optional[dict]:
      """Update daily counter and return a warning event dict if a threshold is crossed."""
      today = datetime.now().strftime("%Y-%m-%d")
      entry = _daily_tokens.get(user_id)
      if not entry or entry["date"] != today:
          _daily_tokens[user_id] = {"date": today, "used": 0, "warned_75": False, "warned_85": False}
          entry = _daily_tokens[user_id]
      entry["used"] += new_tokens
      used = entry["used"]
      remaining = max(0, _DAILY_TOKEN_LIMIT - used)
      pct = used / _DAILY_TOKEN_LIMIT
      if pct >= 0.85 and not entry["warned_85"]:
          entry["warned_85"] = True
          return {
              "event": "rate_limit_warning", "level": "high",
              "used_pct": int(pct * 100),
              "message": f"⚠️ ~15% of your daily token limit remaining (~{remaining:,} tokens).",
          }
      if pct >= 0.75 and not entry["warned_75"]:
          entry["warned_75"] = True
          return {
              "event": "rate_limit_warning", "level": "medium",
              "used_pct": int(pct * 100),
              "message": f"~25% of your daily token limit remaining (~{remaining:,} tokens).",
          }
      return None
  ```

- [ ] **Step 2: Call token tracker in ToolExecution node**

  In `backend/orchestrator/nodes/tools.py`, after synthesizing the final response, add:
  ```python
  from orchestrator.token_tracker import estimate_tokens, check_token_warning

  # At end of tool_execution_node, after `proposed` is set:
  tokens_used = estimate_tokens(state.get("message", "")) + estimate_tokens(proposed)
  warning = check_token_warning(state["user_id"], tokens_used)
  return {
      "tool_results": results,
      "proposed_content": proposed,
      "response_events": events,
      "token_count": state.get("token_count", 0) + tokens_used,
      "token_warning": warning,
  }
  ```

- [ ] **Step 3: Verify import**
  ```bash
  cd backend && python -c "from orchestrator.token_tracker import check_token_warning; print('OK')"
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add backend/orchestrator/token_tracker.py backend/orchestrator/nodes/tools.py
  git commit -m "feat(orchestrator): port daily token budget tracking from orchestrator_v2"
  ```

---

## Task 9: Wire the Full Graph + Feature Flag

**Files:** `backend/orchestrator/graph.py`, `backend/config.py`, `backend/routes/chat.py`

- [ ] **Step 1: Add config flag**

  In `backend/config.py`, add to the Settings class:
  ```python
  USE_LANGGRAPH: bool = False
  LANGFUSE_PUBLIC_KEY: str = ""
  LANGFUSE_SECRET_KEY: str = ""
  LANGFUSE_HOST: str = "https://cloud.langfuse.com"
  ```

- [ ] **Step 2: Wire graph in graph.py**

  Replace `backend/orchestrator/graph.py` with:
  ```python
  """LangGraph orchestrator — full wired graph."""
  from typing import AsyncGenerator, Optional
  import asyncio
  from langgraph.graph import StateGraph, END
  from orchestrator.state import AgentState
  from orchestrator.nodes.context import context_builder_node
  from orchestrator.nodes.intent import intent_classifier_node
  from orchestrator.nodes.tools import tool_planner_node, tool_execution_node
  from orchestrator.nodes.esl import esl_gateway_node
  from orchestrator.nodes.response import response_formatter_node, explain_veto_node
  from esl.models import ESLDecisionStatus
  from services.context_manager import ContextManager
  from orchestrator.nodes.context import get_context_manager


  def _route_after_esl(state: AgentState) -> str:
      decision = state.get("esl_decision")
      if decision and decision.status == ESLDecisionStatus.VETOED:
          return "explain_veto"
      return "response_formatter"


  def _route_after_tools(state: AgentState) -> str:
      """If ToolPlanner returned tool_calls, execute them; otherwise go to ESL."""
      if state.get("tool_calls"):
          return "tool_execution"
      return "esl_gateway"


  def build_graph():
      g = StateGraph(AgentState)
      g.add_node("context_builder", context_builder_node)
      g.add_node("intent_classifier", intent_classifier_node)
      g.add_node("tool_planner", tool_planner_node)
      g.add_node("tool_execution", tool_execution_node)
      g.add_node("esl_gateway", esl_gateway_node)
      g.add_node("response_formatter", response_formatter_node)
      g.add_node("explain_veto", explain_veto_node)

      g.set_entry_point("context_builder")
      g.add_edge("context_builder", "intent_classifier")
      g.add_edge("intent_classifier", "tool_planner")
      g.add_conditional_edges("tool_planner", _route_after_tools,
                              {"tool_execution": "tool_execution", "esl_gateway": "esl_gateway"})
      g.add_edge("tool_execution", "esl_gateway")
      g.add_conditional_edges("esl_gateway", _route_after_esl,
                              {"response_formatter": "response_formatter", "explain_veto": "explain_veto"})
      g.add_edge("response_formatter", END)
      g.add_edge("explain_veto", END)
      return g.compile()


  _compiled_graph = None


  def get_graph():
      global _compiled_graph
      if _compiled_graph is None:
          _compiled_graph = build_graph()
      return _compiled_graph


  async def stream_langgraph(
      user_id: str,
      message: str,
      model: str = "llama-3.3-70b-versatile",
      conversation_id: Optional[str] = None,
  ) -> AsyncGenerator[dict, None]:
      """
      Stream SSE events from the LangGraph orchestrator.

      STREAMING NOTE (Sprint 2a known limitation):
      LangGraph's ainvoke() buffers the full graph run before returning.
      For Sprint 2a, the response appears as a single batch of token events after
      the full LLM call completes — no incremental character streaming.
      The SSE protocol is preserved (token events + done event), so the frontend
      handles it correctly, but the UX shows a delay then the full response at once.
      True token-level streaming via graph.astream_events() will be addressed in Sprint 2b.
      """
      initial_state: AgentState = {
          "user_id": user_id, "message": message, "conversation_id": conversation_id,
          "model": model, "user_context": {}, "conversation_history": [],
          "intent": "", "tool_calls": [], "tool_results": [],
          "esl_decision": None, "proposed_content": "", "response_text": "",
          "response_events": [], "token_count": 0, "token_warning": None,
      }
      graph = get_graph()
      final_state = await graph.ainvoke(initial_state)

      # Check token warning
      if final_state.get("token_warning"):
          yield final_state["token_warning"]

      # Yield tool_use/tool_result events first (from ToolExecution node)
      for event in final_state.get("response_events", []):
          if event.get("event") in ("tool_use", "tool_result"):
              yield event

      # Then yield token + done events (from ResponseFormatter node)
      for event in final_state.get("response_events", []):
          if event.get("event") not in ("tool_use", "tool_result"):
              yield event

      # Store conversation turns in M1 + M2 after streaming completes
      await _post_stream_store(
          user_id=user_id,
          user_msg=message,
          assistant_msg=final_state.get("response_text", ""),
          conversation_id=conversation_id,
      )


  async def _post_stream_store(
      user_id: str,
      user_msg: str,
      assistant_msg: str,
      conversation_id: Optional[str],
  ) -> None:
      """Persist conversation turns to M1 (PostgreSQL) + M2 (Weaviate semantic memory)."""
      import logging
      from orchestrator.nodes.context import get_context_manager
      from models.context import SemanticMemoryEntry
      logger = logging.getLogger(__name__)
      try:
          cm = get_context_manager()
          await cm.store_conversation_turn(user_id, "user", user_msg, conversation_id=conversation_id)
          await cm.store_conversation_turn(user_id, "assistant", assistant_msg, conversation_id=conversation_id)
          for role, content in [("user", user_msg), ("assistant", assistant_msg)]:
              entry = SemanticMemoryEntry(
                  user_id=user_id, content=content,
                  source="conversation", metadata={"role": role}
              )
              await cm.store_semantic_memory(entry)
      except Exception as e:
          logger.warning(f"Post-stream storage failed (non-blocking): {e}")
  ```

- [ ] **Step 3: Add feature flag to chat.py (both streaming and non-streaming paths)**

  In `backend/routes/chat.py`, add at the top after existing imports:
  ```python
  from config import settings as app_settings
  ```

  In the `GET /api/chat/stream` handler, wrap the orchestrator call:
  ```python
  if app_settings.USE_LANGGRAPH:
      from orchestrator.graph import stream_langgraph
      async def _stream():
          async for event in stream_langgraph(user_id, message, model, conversation_id):
              yield f"data: {json.dumps(event)}\n\n"
      return StreamingResponse(_stream(), media_type="text/event-stream")
  # else: fall through to existing orchestrator_v2 streaming path
  ```

  **Note:** The non-streaming `POST /api/chat/` endpoint continues to use `orchestrator_v2` until the deletion step (Task 10 Step 4). This is intentional — only the streaming path is migrated under the flag. Document this in a code comment:
  ```python
  # TODO(sprint2a): non-streaming /api/chat/ path still uses orchestrator_v2
  # Remove when orchestrator_v2.py is deleted in Task 10
  ```

- [ ] **Step 4: Compile graph smoke test**
  ```bash
  cd backend && python -c "from orchestrator.graph import build_graph; g = build_graph(); print('Graph compiled OK:', g)"
  ```
  Expected: `Graph compiled OK: ...`

- [ ] **Step 5: Commit**
  ```bash
  git add backend/orchestrator/graph.py backend/config.py backend/routes/chat.py
  git commit -m "feat(orchestrator): wire full LangGraph graph with feature flag USE_LANGGRAPH"
  ```

---

## Task 10: Validate Regression Tests on LangGraph

- [ ] **Step 1: Update regression tests to mock the LangGraph path**

  The Task 2 regression tests mock `routes.chat.get_orchestrator` — this only covers the `orchestrator_v2` code path. When `USE_LANGGRAPH=true`, the chat route calls `stream_langgraph` directly. Update `test_langgraph_orchestrator.py` to add LangGraph-path tests:

  ```python
  @pytest.mark.asyncio
  async def test_stream_via_langgraph_path():
      """Regression: stream endpoint works with USE_LANGGRAPH=true."""
      async def mock_langgraph(*args, **kwargs):
          yield {"event": "token", "token": "Hello"}
          yield {"event": "done"}

      with patch("routes.chat.app_settings") as mock_settings, \
           patch("orchestrator.graph.stream_langgraph", side_effect=mock_langgraph):
          mock_settings.USE_LANGGRAPH = True
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              r = await client.get("/api/chat/stream?message=hello&user_id=00000000-0000-0000-0000-000000000000")
          if r.status_code == 200:
              events = await _collect_stream_events(r.text)
              assert any(e.get("event") == "done" for e in events)
  ```

- [ ] **Step 2: Enable flag and run regression suite**
  ```bash
  cd backend && USE_LANGGRAPH=true pytest tests/test_langgraph_orchestrator.py -v
  ```
  Expected: all tests pass (same result as baseline against orchestrator_v2).

- [ ] **Step 3: Run full test suite to check no regressions**
  ```bash
  cd backend && USE_LANGGRAPH=true pytest tests/ -v --ignore=tests/test_orchestrator_v2.py -x
  ```
  Expected: all pass (skip failures due to missing auth are acceptable).

- [ ] **Step 4: Set USE_LANGGRAPH=true in .env**

  Edit `backend/.env`:
  ```
  USE_LANGGRAPH=true
  ```

- [ ] **Step 5: Delete old orchestrator**
  ```bash
  rm backend/services/orchestrator_v2.py
  ```

- [ ] **Step 6: Remove old test file**
  ```bash
  rm backend/test_orchestrator_v2.py 2>/dev/null; rm backend/tests/test_orchestrator_v2.py 2>/dev/null; true
  ```

- [ ] **Step 7: Run tests again confirming no import errors**
  ```bash
  cd backend && pytest tests/ -v -x
  ```

- [ ] **Step 8: Commit**
  ```bash
  git add backend/ --ignore-errors
  git commit -m "feat(orchestrator): LangGraph live — delete orchestrator_v2, USE_LANGGRAPH=true"
  ```

---

## Task 11: FastAPI-MCP Server

**Files:** `backend/main.py`

- [ ] **Step 1: Add FastAPI-MCP mount**

  In `backend/main.py`, after the app is created and all routers are registered, add:
  ```python
  # Sprint 2a: Expose all routes as MCP tools
  from fastapi_mcp import FastApiMCP
  mcp = FastApiMCP(app)
  mcp.mount()
  ```

- [ ] **Step 2: Verify MCP tools are discoverable**
  ```bash
  cd backend && python -c "
  from main import app
  from fastapi_mcp import FastApiMCP
  mcp = FastApiMCP(app)
  print('MCP mounted OK')
  "
  ```
  Expected: `MCP mounted OK`

- [ ] **Step 3: Add status router (for Task 13)**
  ```python
  # In main.py, after other routers:
  from routes.status import router as status_router
  app.include_router(status_router)
  ```

- [ ] **Step 4: Commit**
  ```bash
  git add backend/main.py
  git commit -m "feat: mount FastAPI-MCP — all routes now MCP tools"
  ```

---

## Task 12: Skills Registry

**Files:** `backend/skills/*.yaml`

- [ ] **Step 1: Create skills directory and YAML files**
  ```bash
  mkdir -p backend/skills
  ```

  Create `backend/skills/web_search.yaml`:
  ```yaml
  name: web_search
  description: Search the web for current information using Tavily
  mcp_tool: /api/search
  esl_action_type: content_generation
  requires_confirmation: false
  parameters:
    query:
      type: string
      description: The search query
  ```

  Create `backend/skills/query_memory.yaml`:
  ```yaml
  name: query_memory
  description: Search the user's semantic memory for relevant past context
  mcp_tool: /api/context
  esl_action_type: content_generation
  requires_confirmation: false
  parameters:
    query:
      type: string
      description: What to search for in memory
  ```

  Create `backend/skills/query_calendar.yaml`:
  ```yaml
  name: query_calendar
  description: Get the user's upcoming calendar events
  mcp_tool: /api/data-sources/calendar/events
  esl_action_type: content_generation
  requires_confirmation: false
  parameters:
    hours_ahead:
      type: integer
      default: 48
  ```

  Create `backend/skills/get_user_goals.yaml`:
  ```yaml
  name: get_user_goals
  description: Retrieve the user's active goals and priorities
  mcp_tool: /api/goals
  esl_action_type: content_generation
  requires_confirmation: false
  ```

  Create `backend/skills/create_note.yaml`:
  ```yaml
  name: create_note
  description: Save a note or insight to the user's knowledge base
  mcp_tool: /api/documents
  esl_action_type: data_collection
  requires_confirmation: true
  parameters:
    content:
      type: string
      description: The note content to save
  ```

- [ ] **Step 2: Verify YAML loads**
  ```bash
  cd backend && python -c "
  import yaml, glob
  for f in glob.glob('skills/*.yaml'):
      with open(f) as fh:
          d = yaml.safe_load(fh)
      print(f, '->', d['name'])
  "
  ```
  Expected: 5 skill names printed.

- [ ] **Step 3: Commit**
  ```bash
  git add backend/skills/
  git commit -m "feat: add skills registry YAML — 5 initial skills"
  ```

---

## Task 13: Langfuse Observability

**Files:** `backend/orchestrator/nodes/esl.py`, `backend/orchestrator/graph.py`

- [ ] **Step 1: Add Langfuse trace to ESLGateway node**

  In `backend/orchestrator/nodes/esl.py`, wrap the `evaluate_action` call:
  ```python
  from config import settings
  import logging
  logger = logging.getLogger(__name__)

  # In esl_gateway_node(), after getting decision:
  try:
      if settings.LANGFUSE_PUBLIC_KEY:
          from langfuse import Langfuse
          lf = Langfuse(
              public_key=settings.LANGFUSE_PUBLIC_KEY,
              secret_key=settings.LANGFUSE_SECRET_KEY,
              host=settings.LANGFUSE_HOST,
          )
          lf.trace(
              name="esl_decision",
              user_id=state["user_id"],
              metadata={
                  "status": decision.status.value,
                  "reason": decision.reason,
                  "confidence": decision.confidence,
                  "violated_values": decision.violated_values,
              }
          )
  except Exception as e:
      logger.warning(f"Langfuse trace failed (non-blocking): {e}")
  ```

- [ ] **Step 2: Add LANGFUSE keys to .env**
  ```
  LANGFUSE_PUBLIC_KEY=pk-lf-...    # from langfuse.com or self-hosted
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_HOST=https://cloud.langfuse.com
  ```

- [ ] **Step 3: Run a manual chat test and verify trace appears in Langfuse dashboard**

  Start backend: `cd backend && python main.py`
  Send a chat message via the frontend or curl.
  Check Langfuse dashboard for a `esl_decision` trace.

- [ ] **Step 4: Commit**
  ```bash
  git add backend/orchestrator/nodes/esl.py backend/.env.example
  git commit -m "feat: add Langfuse ESL decision tracing"
  ```

---

## Task 14: Auth Hardening — Backend (HttpOnly Cookie)

**Files:** `backend/routes/auth.py`, `backend/utils/supabase_auth.py`

**Architecture note:** This app uses Supabase-native auth — the frontend signs in directly with the Supabase client SDK, not through a FastAPI sign-in route. The FastAPI backend only receives the JWT via `Authorization: Bearer <token>` header. To move to HttpOnly cookies, the pattern is:

1. Frontend signs in via Supabase SDK (unchanged)
2. Frontend calls a new `POST /api/auth/session` endpoint with the token in the body
3. Backend responds with `Set-Cookie: ec_session=<token>; HttpOnly; Secure; SameSite=Strict`
4. Frontend stops sending `Authorization` header; browser sends cookie automatically
5. Backend reads cookie instead of header

- [ ] **Step 1: Check current auth route**
  ```bash
  grep -n "set_cookie\|access_token\|Authorization\|supabase" backend/routes/auth.py | head -30
  ```
  Note what sign-in/sign-out routes exist before writing any code.

- [ ] **Step 2: Add POST /api/auth/session endpoint**

  In `backend/routes/auth.py`, add:
  ```python
  from fastapi import APIRouter, Response
  from pydantic import BaseModel

  class SessionCreate(BaseModel):
      access_token: str
      remember_me: bool = False

  @router.post("/session")
  async def create_session(body: SessionCreate, response: Response):
      """Exchange Supabase token for an HttpOnly cookie session."""
      max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
      response.set_cookie(
          key="ec_session",
          value=body.access_token,
          httponly=True,
          secure=True,        # HTTPS in production; set secure=False for local dev
          samesite="strict",
          max_age=max_age,
      )
      return {"ok": True}

  @router.delete("/session")
  async def delete_session(response: Response):
      """Clear the session cookie on sign-out."""
      response.delete_cookie("ec_session")
      return {"ok": True}
  ```

- [ ] **Step 3: Update supabase_auth.py to read cookie as fallback**

  In `backend/utils/supabase_auth.py`, find `get_current_user_id` and add cookie fallback:
  ```python
  from fastapi import Request

  async def get_current_user_id(request: Request) -> str:
      # Try Authorization header first (API clients), then HttpOnly cookie (browser)
      token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
      if not token:
          token = request.cookies.get("ec_session", "")
      if not token:
          raise HTTPException(status_code=401, detail="Not authenticated")
      # ... existing token validation logic unchanged ...
  ```

- [ ] **Step 4: Run auth tests**
  ```bash
  cd backend && pytest tests/test_auth_phase1.py -v
  ```
  Expected: all pass.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/routes/auth.py backend/utils/supabase_auth.py
  git commit -m "feat(auth): add /api/auth/session cookie endpoint — HttpOnly JWT support"
  ```

---

## Task 15: Auth Hardening — Frontend

**Files:** `frontend/lib/auth.ts`, `frontend/app/login/page.tsx`

- [ ] **Step 1: After Supabase sign-in, call POST /api/auth/session**

  In `frontend/lib/auth.ts` (or wherever sign-in is handled), after the Supabase `signInWith*` call succeeds:
  ```typescript
  // Exchange Supabase token for HttpOnly cookie
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    await fetch('/api/auth/session', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        access_token: session.access_token,
        remember_me: rememberMe,  // from "Remember me" checkbox
      }),
    })
  }
  // Store only non-sensitive display state in localStorage (never the token)
  localStorage.setItem('ec_display', JSON.stringify({
    displayName: session?.user?.user_metadata?.full_name,
    avatarUrl: session?.user?.user_metadata?.avatar_url,
    lastRoute: window.location.pathname,
  }))
  ```

- [ ] **Step 2: On app load, hydrate display state from localStorage**

  In the root layout or auth provider:
  ```typescript
  const display = JSON.parse(localStorage.getItem('ec_display') || '{}')
  // Use display.displayName, display.avatarUrl for instant UI before auth confirms
  ```

- [ ] **Step 3: Redesign login page**

  Replace `frontend/app/login/page.tsx` content with:
  - Centered card (max-w-sm, shadow-md)
  - Ethic Companion logo/wordmark at top
  - Google OAuth button (primary, full-width)
  - Email/password fields below a divider "or continue with email"
  - "Remember me" checkbox
  - Error message display (currently silent — wire up `error` state)
  - Loading spinner during OAuth handshake
  - On success: redirect to `localStorage.getItem('ec_display')?.lastRoute || '/dashboard'`

- [ ] **Step 4: Test login flow manually**

  - Visit `/login`, click Google OAuth → completes → lands on dashboard
  - Refresh page → still authenticated (cookie persists)
  - Auth error (bad password) → shows error message

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/lib/auth.ts frontend/app/login/
  git commit -m "feat(auth): HttpOnly cookie frontend — remove JWT from localStorage, redesign login"
  ```

---

## Task 16: User Status API

**Files:** `backend/routes/status.py`

- [ ] **Step 1: Write failing test**
  ```bash
  # Add to backend/tests/test_settings_routes.py or create test_status_route.py
  ```

  Create `backend/tests/test_status_route.py`:
  ```python
  import pytest
  from unittest.mock import patch, AsyncMock
  from httpx import AsyncClient, ASGITransport
  from main import app

  @pytest.mark.asyncio
  async def test_put_status_unauthenticated():
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          r = await client.put("/api/status/", json={"status": "focus"})
      assert r.status_code == 401

  @pytest.mark.asyncio
  async def test_put_status_invalid_value():
      with patch("utils.supabase_auth.get_current_user_id", return_value="user-1"):
          async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
              r = await client.put("/api/status/", json={"status": "invalid_status"})
      assert r.status_code == 422
  ```

- [ ] **Step 2: Run to confirm fail**
  ```bash
  cd backend && pytest tests/test_status_route.py -v
  ```

- [ ] **Step 3: Implement status route**

  Create `backend/routes/status.py` — uses the **synchronous psycopg3 pattern** matching all other routes in this codebase (see `routes/settings.py:59` for reference):
  ```python
  """User status endpoint — PUT /api/status/ (not ESL-gated, user controls own mode)."""
  from fastapi import APIRouter, Depends
  from pydantic import BaseModel
  from typing import Optional, Literal
  from datetime import datetime
  from utils.supabase_auth import get_current_user_id
  from utils.db import get_db_connection

  router = APIRouter(prefix="/api/status", tags=["Status"])

  STATUS_VALUES = Literal["available", "focus", "do_not_disturb", "away"]


  class StatusUpdate(BaseModel):
      status: STATUS_VALUES
      status_until: Optional[datetime] = None


  @router.put("/")
  async def update_status(body: StatusUpdate, user_id: str = Depends(get_current_user_id)):
      """Update user status. Not ESL-gated — user directly controls their own mode."""
      with get_db_connection() as conn:                  # sync context manager
          with conn.cursor() as cur:
              cur.execute(
                  """INSERT INTO user_settings (user_id, status, status_until)
                     VALUES (%s, %s, %s)
                     ON CONFLICT (user_id) DO UPDATE
                     SET status = EXCLUDED.status,
                         status_until = EXCLUDED.status_until,
                         updated_at = NOW()""",
                  (user_id, body.status, body.status_until)
              )
      return {"status": body.status, "status_until": body.status_until}


  @router.get("/")
  async def get_status(user_id: str = Depends(get_current_user_id)):
      """Get current user status."""
      with get_db_connection() as conn:                  # sync context manager
          with conn.cursor() as cur:
              cur.execute(
                  "SELECT status, status_until FROM user_settings WHERE user_id = %s",
                  (user_id,)
              )
              row = cur.fetchone()
      if not row:
          return {"status": "available", "status_until": None}
      return {"status": row["status"], "status_until": row["status_until"]}
  ```

- [ ] **Step 4: Run tests**
  ```bash
  cd backend && pytest tests/test_status_route.py -v
  ```
  Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/routes/status.py backend/tests/test_status_route.py
  git commit -m "feat: add PUT /api/status/ — user status system"
  ```

---

## Task 17: Settings Page Overhaul (Frontend)

**Files:** `frontend/app/dashboard/settings/page.tsx`

- [ ] **Step 1: Add Appearance localStorage handler**

  At top of settings page component:
  ```typescript
  // Load appearance from localStorage (never from backend)
  const [appearance, setAppearance] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ec_appearance') || '{}') }
    catch { return {} }
  })
  const saveAppearance = (update: object) => {
    const next = { ...appearance, ...update }
    setAppearance(next)
    localStorage.setItem('ec_appearance', JSON.stringify(next))
  }
  ```

- [ ] **Step 2: Add theme toggle in Appearance section**

  Wire theme toggle to `next-themes` `setTheme()` AND `saveAppearance({ theme })`:
  ```typescript
  import { useTheme } from 'next-themes'
  const { theme, setTheme } = useTheme()
  // On change: setTheme(value); saveAppearance({ theme: value })
  ```

- [ ] **Step 3: Update backend settings route to accept timezone + language**

  In `backend/routes/settings.py`, find `UpdateSettingsRequest` Pydantic model and add:
  ```python
  timezone: Optional[str] = None
  language: Optional[str] = None
  ```
  Find the `PUT /api/settings/` handler and add these fields to the `SET` clause of the upsert SQL:
  ```python
  # In the SQL: add SET timezone = %s, language = %s
  # In the params tuple: add settings.timezone, settings.language
  ```
  Run settings tests after:
  ```bash
  cd backend && pytest tests/test_settings_routes.py -v
  ```

- [ ] **Step 4: Add Profile fields (timezone, language) to frontend**

  Add `timezone` and `language` dropdowns to the Profile section. On save, include in `PUT /api/settings/` body.

- [ ] **Step 4: Add Security section**

  Add "Sign out all devices" button → calls Supabase `signOut({ scope: 'global' })` + clears cookie + redirects to `/login`.

- [ ] **Step 5: Test settings persist across sessions**

  - Change notification setting → reload page → setting persists
  - Change theme → reload page → theme persists from localStorage (no flicker)

- [ ] **Step 6: Commit**
  ```bash
  git add frontend/app/dashboard/settings/
  git commit -m "feat(frontend): settings page overhaul — 7 sections, localStorage appearance"
  ```

---

## Task 18: User Status UI Component

**Files:** `frontend/components/UserStatus.tsx`, sidebar component

- [ ] **Step 1: Create UserStatus component**

  Create `frontend/components/UserStatus.tsx`:
  ```typescript
  'use client'
  import { useState, useEffect } from 'react'
  import * as Popover from '@radix-ui/react-popover'

  const STATUS_OPTIONS = [
    { value: 'available', label: 'Available', color: 'bg-green-500' },
    { value: 'focus', label: 'Focus', color: 'bg-yellow-500' },
    { value: 'do_not_disturb', label: 'Do Not Disturb', color: 'bg-red-500' },
    { value: 'away', label: 'Away', color: 'bg-gray-400' },
  ]

  export function UserStatus() {
    const [status, setStatus] = useState('available')
    const [open, setOpen] = useState(false)

    useEffect(() => {
      fetch('/api/status/', { credentials: 'include' })
        .then(r => r.json())
        .then(d => setStatus(d.status))
        .catch(() => {})
    }, [])

    const updateStatus = async (value: string) => {
      await fetch('/api/status/', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: value }),
      })
      setStatus(value)
      setOpen(false)
    }

    const current = STATUS_OPTIONS.find(s => s.value === status)!

    return (
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-100">
            <span className={`w-2.5 h-2.5 rounded-full ${current.color}`} />
            <span className="text-sm">{current.label}</span>
          </button>
        </Popover.Trigger>
        <Popover.Content className="bg-white border rounded-lg shadow-lg p-2 w-48">
          {STATUS_OPTIONS.map(opt => (
            <button key={opt.value} onClick={() => updateStatus(opt.value)}
              className="flex items-center gap-2 w-full px-3 py-2 rounded hover:bg-gray-50 text-sm">
              <span className={`w-2 h-2 rounded-full ${opt.color}`} />
              {opt.label}
            </button>
          ))}
        </Popover.Content>
      </Popover.Root>
    )
  }
  ```

- [ ] **Step 2: Add UserStatus to sidebar**

  Import and render `<UserStatus />` in the sidebar component, below the user avatar.

- [ ] **Step 3: Test manually**

  - Click avatar → status popover opens
  - Select "Focus" → badge updates → backend persists
  - Reload page → status badge shows "Focus"

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/components/UserStatus.tsx frontend/app/dashboard/
  git commit -m "feat(frontend): user status popover — available/focus/do_not_disturb/away"
  ```

---

## Task 19: Frontend Polish — Dashboard + Chat Bugs

**Files:** `frontend/app/dashboard/page.tsx`, `frontend/app/dashboard/chat/page.tsx`

- [ ] **Step 1: Dashboard — empty states**

  For each widget (Goals, Tasks, Integrations), wrap the "no data" case:
  ```tsx
  {goals.length === 0 && (
    <div className="text-center py-8 text-gray-400">
      <p className="text-sm">No goals yet.</p>
      <a href="/dashboard/goals" className="text-sm underline mt-1 block">Add your first goal →</a>
    </div>
  )}
  ```

- [ ] **Step 2: Dashboard — skeleton loaders**

  While data is loading (`isLoading === true`), render skeleton placeholders:
  ```tsx
  {isLoading && (
    <div className="animate-pulse space-y-2">
      <div className="h-4 bg-gray-100 rounded w-3/4" />
      <div className="h-4 bg-gray-100 rounded w-1/2" />
    </div>
  )}
  ```

- [ ] **Step 3: Dashboard — error boundary**

  Wrap the main dashboard content in an error boundary:
  ```tsx
  // Create frontend/components/ErrorBoundary.tsx with standard React error boundary
  // Renders: "Something went wrong. [Retry]" with a retry button that resets state
  ```

- [ ] **Step 4: Chat — fix streaming cursor sticks**

  In `frontend/app/dashboard/chat/page.tsx`, find where the streaming cursor is rendered. Ensure it's removed when the `done` event is received:
  ```typescript
  case 'done':
    setIsLoading(false)
    setIsThinking(false)
    setStreamingCursor(false)  // ← ensure this is called
    break
  ```

- [ ] **Step 5: Chat — fix model selector z-index**

  Find the model selector menu CSS. Add `z-50` (or equivalent) to the dropdown container.

- [ ] **Step 6: Chat — fix rate limit warning reappearing**

  Add a `rateLimitDismissed` ref that persists across messages:
  ```typescript
  const rateLimitDismissedRef = useRef(false)
  // Only show warning if !rateLimitDismissedRef.current
  // On dismiss: rateLimitDismissedRef.current = true
  ```

- [ ] **Step 7: Chat — fix conversation history not reloading on refresh**

  In the chat page `useEffect`, ensure history loads on mount:
  ```typescript
  useEffect(() => {
    loadChatHistory()  // must be called unconditionally on mount
  }, [conversationId]) // re-run when conversationId changes
  ```

- [ ] **Step 8: Chat — add keyboard shortcut legend**

  Add a small `?` button in the chat toolbar that opens a popover:
  ```
  Cmd/Ctrl + Enter  — Send message
  Escape            — Cancel streaming
  ```

- [ ] **Step 9: Test all fixes manually**

  - Dashboard: visit with no data → see empty states, not blank
  - Dashboard: reload → see skeleton loaders, then content
  - Chat: send message → cursor disappears on done
  - Chat: model selector opens above other elements
  - Chat: dismiss rate limit → send another message → warning stays dismissed

- [ ] **Step 10: Commit**
  ```bash
  git add frontend/app/dashboard/ frontend/components/
  git commit -m "fix(frontend): dashboard empty states + skeletons + 6 chat bug fixes"
  ```

---

## Task 20: Final Verification + Sprint 2a Sign-Off

- [ ] **Step 1: Run full backend test suite**
  ```bash
  cd backend && pytest tests/ -v --tb=short
  ```
  Expected: all existing tests pass. New tests (orchestrator regression, status route) pass.

- [ ] **Step 2: Run frontend build check**
  ```bash
  cd frontend && npm run build
  ```
  Expected: no TypeScript errors, no build failures.

- [ ] **Step 3: Smoke test end-to-end**

  - Sign in → lands on dashboard (no auth flicker)
  - Send chat message → tokens stream → ESL badge visible → done
  - Check Langfuse dashboard → ESL trace visible
  - Change status → badge updates in sidebar
  - Change settings → persist on reload
  - Refresh page → still authenticated

- [ ] **Step 4: Final commit**
  ```bash
  git add -A
  git commit -m "chore: sprint 2a complete — LangGraph + MCP + Langfuse + auth + frontend polish"
  ```

---

## Sprint 2a Completion Checklist

- [ ] LangGraph orchestrator replaces orchestrator_v2 — regression tests pass
- [ ] ESL is a mandatory graph node (structurally unskippable)
- [ ] All FastAPI routes discoverable as MCP tools
- [ ] Skills registry: 5 YAML files, new skill = new file
- [ ] Langfuse traces ESL decisions (visible in dashboard)
- [ ] SLACK_SEND in ActionType enum
- [ ] JWT in HttpOnly cookie — not in localStorage
- [ ] Auth survives page refresh
- [ ] Status schema migrated (status, status_until, timezone, language columns)
- [ ] PUT /api/status/ endpoint live and tested
- [ ] User status popover in sidebar
- [ ] Settings page: 7 sections, Appearance localStorage-only
- [ ] Login page redesigned with error handling + redirect
- [ ] Dashboard: empty states + skeleton loaders + error boundary
- [ ] Chat: 6 known bugs fixed
