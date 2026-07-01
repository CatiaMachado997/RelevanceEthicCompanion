# Multi-Agent LangGraph Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-agent `intent_classifier + tool_planner` with a Supervisor that routes to five specialised worker agents, each with its own tools and model, while keeping the ESL gateway unchanged and mandatory.

**Architecture:** A `langgraph-supervisor` Supervisor node replaces `intent_classifier` and `tool_planner` in the parent graph. Each worker agent is a `create_react_agent` compiled subgraph with its own LangChain tools. The Supervisor LLM chooses which worker(s) to invoke; results return for synthesis before the ESL gate. `AsyncPostgresSaver` replaces `MemorySaver` for production checkpointing.

**Tech Stack:** `langgraph>=0.2.0`, `langgraph-supervisor>=0.1.0`, `langgraph[postgres]`, `langchain-groq`, `langchain-google-genai`, existing `services/` tools.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/requirements.txt` | Add `langgraph-supervisor`, `langgraph[postgres]` |
| Modify | `backend/orchestrator/state.py` | Add `messages`, `active_agent`, `agent_outputs` fields |
| Create | `backend/orchestrator/agents/__init__.py` | Package marker + convenience exports |
| Create | `backend/orchestrator/agents/research.py` | ResearchAgent: Tavily + memory tools |
| Create | `backend/orchestrator/agents/calendar.py` | CalendarAgent: Google Calendar read tools |
| Create | `backend/orchestrator/agents/goals.py` | GoalsAgent: user_values + goals DB tools |
| Create | `backend/orchestrator/agents/document.py` | DocumentAgent: PDF Q&A + pgvector search |
| Create | `backend/orchestrator/agents/connectors.py` | ConnectorsAgent: Composio tools |
| Create | `backend/orchestrator/agents/supervisor.py` | Supervisor: routes to worker agents |
| Modify | `backend/orchestrator/graph.py` | Wire Supervisor behind `MULTI_AGENT` env flag |
| Create | `backend/tests/test_agents.py` | Unit tests for all five agents + supervisor |
| Delete (later) | `backend/orchestrator/nodes/intent.py` | Removed after flag flip |
| Delete (later) | `backend/orchestrator/nodes/tools.py` | Removed after flag flip |
| Delete (later) | `backend/orchestrator/subgraphs/deep_research.py` | Absorbed into research_agent |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add packages**

Open `backend/requirements.txt`. After the `langgraph>=0.2.0` line add:

```
langgraph-supervisor>=0.1.0
langgraph[postgres]>=0.2.0
```

- [ ] **Step 2: Install and verify**

```bash
cd backend && source venv/bin/activate
pip install "langgraph-supervisor>=0.1.0" "langgraph[postgres]>=0.2.0"
python -c "from langgraph_supervisor import create_supervisor; print('OK')"
python -c "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver; print('OK')"
```

Expected: two `OK` lines, no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add langgraph-supervisor and langgraph[postgres] deps"
```

---

## Task 2: Extend AgentState

**Files:**
- Modify: `backend/orchestrator/state.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_agents.py` (create the file):

```python
"""Tests for multi-agent orchestrator components."""
import pytest
from orchestrator.state import AgentState
from typing import get_type_hints


def test_agent_state_has_messages_field():
    hints = get_type_hints(AgentState)
    assert "messages" in hints, "AgentState must have a 'messages' field"


def test_agent_state_has_active_agent_field():
    hints = get_type_hints(AgentState)
    assert "active_agent" in hints


def test_agent_state_has_agent_outputs_field():
    hints = get_type_hints(AgentState)
    assert "agent_outputs" in hints
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py -v
```

Expected: FAIL — `assert "messages" in hints`

- [ ] **Step 3: Update AgentState**

In `backend/orchestrator/state.py`, add these imports at the top:

```python
from typing import Annotated
from langgraph.graph.message import add_messages
```

Add three fields at the end of the `AgentState` TypedDict body (after `source_context`):

```python
    # Multi-agent fields
    messages: Annotated[list, add_messages]
    active_agent: str
    agent_outputs: dict
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_agents.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/state.py backend/tests/test_agents.py
git commit -m "feat(agents): extend AgentState for multi-agent fields"
```

---

## Task 3: Research Agent

**Files:**
- Create: `backend/orchestrator/agents/__init__.py`
- Create: `backend/orchestrator/agents/research.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver


def _mock_llm():
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


def test_research_agent_builds():
    """build_agent returns a compiled graph without raising."""
    from orchestrator.agents.research import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_research_agent_has_tavily_tool():
    from orchestrator.agents.research import build_research_tools
    with patch("orchestrator.agents.research.settings") as mock_settings:
        mock_settings.TAVILY_API_KEY = "test-key"
        tools = build_research_tools(user_id="u1", context_manager=MagicMock())
    names = [t.name for t in tools]
    assert "web_search" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_research_agent_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.research`

- [ ] **Step 3: Create package marker**

Create `backend/orchestrator/agents/__init__.py`:

```python
from orchestrator.agents.research import build_agent as build_research_agent
from orchestrator.agents.calendar import build_agent as build_calendar_agent
from orchestrator.agents.goals import build_agent as build_goals_agent
from orchestrator.agents.document import build_agent as build_document_agent
from orchestrator.agents.connectors import build_agent as build_connectors_agent

__all__ = [
    "build_research_agent",
    "build_calendar_agent",
    "build_goals_agent",
    "build_document_agent",
    "build_connectors_agent",
]
```

- [ ] **Step 4: Create research agent**

Create `backend/orchestrator/agents/research.py`:

```python
"""ResearchAgent — web search + semantic memory retrieval."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Research Specialist. Your job is to gather information using web search "
    "and the user's past conversation memory. Always cite your sources. "
    "Return a structured response with Key Findings, Sources, and Next Steps. "
    "Never fabricate citations."
)


def build_research_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from config import settings
    tools: list[BaseTool] = []

    # Tavily web search
    if getattr(settings, "TAVILY_API_KEY", None):
        from langchain_community.tools.tavily_search import TavilySearchResults
        from pydantic import SecretStr
        tools.append(
            TavilySearchResults(
                max_results=5,
                api_key=SecretStr(settings.TAVILY_API_KEY),
                name="web_search",
                description="Search the web for current information on any topic.",
            )
        )

    # Semantic memory query
    from services.langchain_tools import MemoryQueryTool
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))

    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled ResearchAgent graph."""
    tools = build_research_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_research_agent_builds tests/test_agents.py::test_research_agent_has_tavily_tool -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/agents/__init__.py backend/orchestrator/agents/research.py backend/tests/test_agents.py
git commit -m "feat(agents): add ResearchAgent with Tavily + memory tools"
```

---

## Task 4: Calendar Agent

**Files:**
- Create: `backend/orchestrator/agents/calendar.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
def test_calendar_agent_builds():
    from orchestrator.agents.calendar import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_calendar_agent_has_query_tool():
    from orchestrator.agents.calendar import build_calendar_tools
    tools = build_calendar_tools(user_id="u1", context_manager=MagicMock())
    names = [t.name for t in tools]
    assert "query_calendar" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_calendar_agent_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.calendar`

- [ ] **Step 3: Create calendar agent**

Create `backend/orchestrator/agents/calendar.py`:

```python
"""CalendarAgent — reads Google Calendar events for the user."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Calendar Assistant. You help users understand their schedule, "
    "find free time, and summarise upcoming events. "
    "Only read events — never create or modify calendar entries unless explicitly asked. "
    "Always present times in the user's local timezone."
)


def build_calendar_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def query_calendar(query: str) -> str:
        """Retrieve Google Calendar events relevant to the query."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT title, start_time, end_time, description
                        FROM source_items
                        WHERE user_id = %s
                          AND source_type = 'google_calendar'
                          AND (title ILIKE %s OR description ILIKE %s)
                        ORDER BY start_time
                        LIMIT 10
                        """,
                        (user_id, f"%{query}%", f"%{query}%"),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Calendar lookup failed: {e}"

        if not rows:
            return "No calendar events found matching your query."

        lines = []
        for title, start, end, desc in rows:
            lines.append(f"- {title}: {start} → {end}" + (f" ({desc[:80]})" if desc else ""))
        return "\n".join(lines)

    tools: list[BaseTool] = [query_calendar]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled CalendarAgent graph."""
    tools = build_calendar_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_calendar_agent_builds tests/test_agents.py::test_calendar_agent_has_query_tool -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/agents/calendar.py backend/tests/test_agents.py
git commit -m "feat(agents): add CalendarAgent"
```

---

## Task 5: Goals Agent

**Files:**
- Create: `backend/orchestrator/agents/goals.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
def test_goals_agent_builds():
    from orchestrator.agents.goals import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_goals_agent_has_get_goals_tool():
    from orchestrator.agents.goals import build_goals_tools
    tools = build_goals_tools(user_id="u1", context_manager=MagicMock())
    names = [t.name for t in tools]
    assert "get_user_goals" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_goals_agent_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.goals`

- [ ] **Step 3: Create goals agent**

Create `backend/orchestrator/agents/goals.py`:

```python
"""GoalsAgent — reads user values and goals from M1 (PostgreSQL)."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Goals and Values Coach. You help users reflect on their goals, "
    "understand their stated values, and make decisions aligned with what they care about. "
    "Always reference the user's actual goals — never invent or assume goals they haven't set. "
    "Suggest actions that respect the user's boundaries."
)


def build_goals_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def get_user_goals(limit: int = 10) -> str:
        """Retrieve the user's active goals from the database."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT title, description, status, priority
                        FROM goals
                        WHERE user_id = %s AND status != 'archived'
                        ORDER BY priority DESC, created_at DESC
                        LIMIT %s
                        """,
                        (user_id, limit),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Could not retrieve goals: {e}"

        if not rows:
            return "No active goals found."

        lines = [f"- [{row[2]}] {row[0]}" + (f": {row[1][:100]}" if row[1] else "") for row in rows]
        return "\n".join(lines)

    @tool
    async def get_user_values() -> str:
        """Retrieve the user's stated values and boundaries."""
        try:
            from utils.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value_name, description, boundary_type FROM user_values WHERE user_id = %s",
                        (user_id,),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            return f"Could not retrieve values: {e}"

        if not rows:
            return "No values configured."

        return "\n".join(f"- {row[0]} ({row[2]}): {row[1] or ''}" for row in rows)

    tools: list[BaseTool] = [get_user_goals, get_user_values]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled GoalsAgent graph."""
    tools = build_goals_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_goals_agent_builds tests/test_agents.py::test_goals_agent_has_get_goals_tool -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/agents/goals.py backend/tests/test_agents.py
git commit -m "feat(agents): add GoalsAgent with goals + values tools"
```

---

## Task 6: Document Agent

**Files:**
- Create: `backend/orchestrator/agents/document.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
def test_document_agent_builds():
    from orchestrator.agents.document import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_document_agent_has_search_tool():
    from orchestrator.agents.document import build_document_tools
    tools = build_document_tools(user_id="u1", context_manager=MagicMock())
    names = [t.name for t in tools]
    assert "search_documents" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_document_agent_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.document`

- [ ] **Step 3: Create document agent**

Create `backend/orchestrator/agents/document.py`:

```python
"""DocumentAgent — semantic search over user-uploaded documents."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Document Analyst. You answer questions by searching the user's uploaded documents "
    "and files. Always quote the source document name when referencing content. "
    "If the answer is not found in documents, say so — do not guess."
)


def build_document_tools(user_id: str, context_manager: Any) -> list[BaseTool]:
    from services.langchain_tools import MemoryQueryTool

    @tool
    async def search_documents(query: str, limit: int = 5) -> str:
        """Semantically search the user's uploaded documents for relevant content."""
        try:
            results = await context_manager.query_semantic_memory(
                user_id=user_id,
                query=query,
                limit=limit,
            )
        except Exception as e:
            return f"Document search failed: {e}"

        if not results:
            return "No relevant document content found."

        lines = []
        for r in results:
            source = getattr(r, "source", "unknown")
            content = getattr(r, "content", "")[:300]
            lines.append(f"[{source}]: {content}")
        return "\n\n".join(lines)

    tools: list[BaseTool] = [search_documents]
    tools.append(MemoryQueryTool(context_manager=context_manager, user_id=user_id))
    return tools


def build_agent(llm: Any, checkpointer: Any, user_id: str = "", context_manager: Any = None):
    """Return a compiled DocumentAgent graph."""
    tools = build_document_tools(user_id=user_id, context_manager=context_manager) if context_manager else []
    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_document_agent_builds tests/test_agents.py::test_document_agent_has_search_tool -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/agents/document.py backend/tests/test_agents.py
git commit -m "feat(agents): add DocumentAgent with semantic document search"
```

---

## Task 7: Connectors Agent

**Files:**
- Create: `backend/orchestrator/agents/connectors.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
def test_connectors_agent_builds():
    from orchestrator.agents.connectors import build_agent
    checkpointer = MemorySaver()
    agent = build_agent(llm=_mock_llm(), checkpointer=checkpointer)
    assert agent is not None


def test_connectors_agent_returns_empty_tools_when_no_composio_key():
    from orchestrator.agents.connectors import build_connector_tools
    with patch("orchestrator.agents.connectors.settings") as mock_settings:
        mock_settings.COMPOSIO_API_KEY = None
        tools = build_connector_tools(user_id="u1", connected_tool_ids=set())
    assert tools == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_connectors_agent_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.connectors`

- [ ] **Step 3: Create connectors agent**

Create `backend/orchestrator/agents/connectors.py`:

```python
"""ConnectorsAgent — Composio-managed integrations (Slack, Gmail, GitHub, Notion)."""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Connectors Agent. You interact with the user's connected apps "
    "(Slack, Gmail, GitHub, Notion) only when explicitly authorised. "
    "Before taking any write action (send message, create issue, etc.), "
    "confirm the action with the user. Never act without confirmation on destructive operations."
)


def build_connector_tools(user_id: str, connected_tool_ids: set[str]) -> list[BaseTool]:
    from config import settings
    if not getattr(settings, "COMPOSIO_API_KEY", None):
        return []

    try:
        from services.composio_tools import get_composio_tools_for_user
        import asyncio
        tools = asyncio.get_event_loop().run_until_complete(
            get_composio_tools_for_user(
                user_id=user_id,
                connected_tool_ids=connected_tool_ids,
            )
        )
        return tools or []
    except Exception as e:
        logger.warning(f"Could not load Composio tools: {e}")
        return []


def build_agent(
    llm: Any,
    checkpointer: Any,
    user_id: str = "",
    connected_tool_ids: set[str] | None = None,
):
    """Return a compiled ConnectorsAgent graph."""
    tools = build_connector_tools(
        user_id=user_id,
        connected_tool_ids=connected_tool_ids or set(),
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_connectors_agent_builds tests/test_agents.py::test_connectors_agent_returns_empty_tools_when_no_composio_key -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/agents/connectors.py backend/tests/test_agents.py
git commit -m "feat(agents): add ConnectorsAgent for Composio integrations"
```

---

## Task 8: Supervisor

**Files:**
- Create: `backend/orchestrator/agents/supervisor.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_agents.py`:

```python
def test_supervisor_builds():
    from orchestrator.agents.supervisor import build_supervisor
    checkpointer = MemorySaver()
    llm = _mock_llm()
    supervisor = build_supervisor(
        routing_llm=llm,
        worker_llm=llm,
        checkpointer=checkpointer,
    )
    assert supervisor is not None


def test_supervisor_system_prompt_mentions_active_sources():
    from orchestrator.agents.supervisor import SUPERVISOR_SYSTEM_PROMPT
    assert "active_sources" in SUPERVISOR_SYSTEM_PROMPT.lower() or "authorised" in SUPERVISOR_SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_agents.py::test_supervisor_builds -v
```

Expected: FAIL — `ModuleNotFoundError: orchestrator.agents.supervisor`

- [ ] **Step 3: Create supervisor**

Create `backend/orchestrator/agents/supervisor.py`:

```python
"""Supervisor — routes user requests to specialised worker agents."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph_supervisor import create_supervisor

from orchestrator.agents.research import build_agent as build_research
from orchestrator.agents.calendar import build_agent as build_calendar
from orchestrator.agents.goals import build_agent as build_goals
from orchestrator.agents.document import build_agent as build_document
from orchestrator.agents.connectors import build_agent as build_connectors

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Ethic Companion Supervisor. Your only job is to decide which specialist "
    "agent(s) to call to answer the user's request. Never answer directly — always delegate.\n\n"
    "Agents available:\n"
    "- research_agent: web searches, deep research, current events\n"
    "- calendar_agent: schedule, events, time management\n"
    "- goals_agent: user goals, values, decision-making alignment\n"
    "- document_agent: questions about uploaded files and documents\n"
    "- connectors_agent: actions in Slack, Gmail, GitHub, Notion (only if user has authorised "
    "those connectors in their active_sources list)\n\n"
    "Rules:\n"
    "1. Never invoke connectors_agent for a connector not in the user's active_sources.\n"
    "2. For ambiguous requests, prefer research_agent.\n"
    "3. You may call multiple agents in sequence when a request spans domains.\n"
    "4. Synthesise the agents' outputs into one coherent final answer."
)


def build_supervisor(
    routing_llm: Any,
    worker_llm: Any,
    checkpointer: Any = None,
    user_id: str = "",
    context_manager: Any = None,
    connected_tool_ids: set[str] | None = None,
):
    """Return a compiled Supervisor graph with all five worker agents."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    workers = [
        build_research(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager),
        build_calendar(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager),
        build_goals(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager),
        build_document(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, context_manager=context_manager),
        build_connectors(llm=worker_llm, checkpointer=checkpointer, user_id=user_id, connected_tool_ids=connected_tool_ids),
    ]

    return create_supervisor(
        agents=workers,
        model=routing_llm,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
    ).compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_agents.py::test_supervisor_builds tests/test_agents.py::test_supervisor_system_prompt_mentions_active_sources -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run full agent test suite**

```bash
cd backend && pytest tests/test_agents.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/agents/supervisor.py backend/tests/test_agents.py
git commit -m "feat(agents): add Supervisor routing across five worker agents"
```

---

## Task 9: Wire Supervisor into Parent Graph

**Files:**
- Modify: `backend/orchestrator/graph.py`
- Modify: `backend/tests/test_langgraph_orchestrator.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_langgraph_orchestrator.py`:

```python
def test_multi_agent_flag_selects_supervisor_path():
    """When MULTI_AGENT=true, get_graph returns a graph that includes supervisor node."""
    import os
    os.environ["MULTI_AGENT"] = "true"
    # Reset cached graph so flag takes effect
    import orchestrator.graph as og
    og._compiled_graph = None
    graph = og.get_graph()
    node_names = list(graph.get_graph().nodes.keys())
    assert any("supervisor" in n for n in node_names), f"Expected supervisor node, got: {node_names}"
    os.environ.pop("MULTI_AGENT", None)
    og._compiled_graph = None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_langgraph_orchestrator.py::test_multi_agent_flag_selects_supervisor_path -v
```

Expected: FAIL.

- [ ] **Step 3: Update graph.py**

In `backend/orchestrator/graph.py`, add the new `build_multi_agent_graph` function and update `get_graph()`. The existing `build_graph()` function stays untouched.

Add these imports at the top of `graph.py` (after existing imports):

```python
import os
```

Add this new function after the existing `build_graph()` function:

```python
def build_multi_agent_graph():
    """Multi-agent graph: context_builder → supervisor → esl_gateway → formatter."""
    from pydantic import SecretStr
    from orchestrator.agents.supervisor import build_supervisor
    from orchestrator.nodes.context import get_context_manager
    from config import settings

    # Routing LLM — cheap model for supervisor decisions
    try:
        from langchain_groq import ChatGroq
        routing_llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=SecretStr(settings.GROQ_API_KEY),
        )
        worker_llm = ChatGroq(
            model=settings.DEFAULT_MODEL if hasattr(settings, "DEFAULT_MODEL") else "llama-3.3-70b-versatile",
            api_key=SecretStr(settings.GROQ_API_KEY),
        )
    except Exception:
        routing_llm = None
        worker_llm = None

    supervisor_node = build_supervisor(
        routing_llm=routing_llm,
        worker_llm=worker_llm,
    )

    g = StateGraph(AgentState)
    g.add_node("context_builder", context_builder_node)
    g.add_node("supervisor", supervisor_node)
    g.add_node("esl_gateway", esl_gateway_node)
    g.add_node("response_formatter", response_formatter_node)
    g.add_node("explain_veto", explain_veto_node)

    g.set_entry_point("context_builder")
    g.add_edge("context_builder", "supervisor")
    g.add_edge("supervisor", "esl_gateway")
    g.add_conditional_edges(
        "esl_gateway",
        _route_after_esl,
        {"response_formatter": "response_formatter", "explain_veto": "explain_veto"},
    )
    g.add_edge("response_formatter", END)
    g.add_edge("explain_veto", END)
    return g.compile()
```

Update `get_graph()` to check the env flag:

```python
def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        if os.getenv("MULTI_AGENT", "").lower() == "true":
            _compiled_graph = build_multi_agent_graph()
        else:
            _compiled_graph = build_graph()
    return _compiled_graph
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_langgraph_orchestrator.py::test_multi_agent_flag_selects_supervisor_path -v
```

Expected: PASS.

- [ ] **Step 5: Run full orchestrator test suite**

```bash
cd backend && pytest tests/test_langgraph_orchestrator.py tests/test_chat_stream.py tests/test_streaming.py -v
```

Expected: all pre-existing tests PASS (multi-agent flag is off by default).

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/graph.py backend/tests/test_langgraph_orchestrator.py
git commit -m "feat(agents): wire Supervisor into parent graph behind MULTI_AGENT flag"
```

---

## Task 10: AsyncPostgresSaver Checkpointing

**Files:**
- Modify: `backend/orchestrator/graph.py`
- Modify: `backend/tests/test_langgraph_orchestrator.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_langgraph_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_get_checkpointer_returns_memory_saver_in_test():
    """In test environment, get_checkpointer returns MemorySaver."""
    from orchestrator.graph import get_checkpointer
    from unittest.mock import patch
    with patch("orchestrator.graph.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "test"
        mock_settings.database_url = "postgresql://test:test@localhost/test"
        checkpointer = await get_checkpointer()
    from langgraph.checkpoint.memory import MemorySaver
    assert isinstance(checkpointer, MemorySaver)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_langgraph_orchestrator.py::test_get_checkpointer_returns_memory_saver_in_test -v
```

Expected: FAIL — `ImportError: cannot import name 'get_checkpointer'`

- [ ] **Step 3: Add get_checkpointer to graph.py**

Add this function to `backend/orchestrator/graph.py` (before `get_graph()`):

```python
async def get_checkpointer():
    """Return MemorySaver in test/development, AsyncPostgresSaver in production."""
    from langgraph.checkpoint.memory import MemorySaver
    if getattr(settings, "ENVIRONMENT", "development") in ("test", "development"):
        return MemorySaver()
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        return await AsyncPostgresSaver.from_conn_string(settings.database_url)
    except Exception as e:
        logger.warning(f"AsyncPostgresSaver unavailable, falling back to MemorySaver: {e}")
        return MemorySaver()
```

Add `from config import settings` to the top-level imports in `graph.py` if not already present.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_langgraph_orchestrator.py::test_get_checkpointer_returns_memory_saver_in_test -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && pytest tests/ -v --tb=short -q
```

Expected: all tests PASS. ESL tests must still pass (`pytest tests/test_esl.py -v`).

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/graph.py backend/tests/test_langgraph_orchestrator.py
git commit -m "feat(agents): add AsyncPostgresSaver checkpointing with env-aware fallback"
```

---

## Task 11: Enable Multi-Agent in Staging + Cleanup

> This task runs after the feature has been validated in staging for 48h.

**Files:**
- Delete: `backend/orchestrator/nodes/intent.py`
- Delete: `backend/orchestrator/nodes/tools.py`
- Delete: `backend/orchestrator/subgraphs/deep_research.py`
- Modify: `backend/orchestrator/graph.py` (remove old build_graph and flag)

- [ ] **Step 1: Set flag in staging**

In the staging Cloud Run environment (or `.env`):
```
MULTI_AGENT=true
```

- [ ] **Step 2: Monitor for 48h**

Watch Langfuse traces for ESL decision quality regressions. Check p95 latency in GCP Cloud Run metrics. If no regressions, proceed.

- [ ] **Step 3: Remove old nodes and make multi-agent the default**

In `backend/orchestrator/graph.py`:
- Delete the `build_graph()` function body.
- Delete the `import os` and flag check in `get_graph()`.
- Replace `get_graph()` with:

```python
def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_multi_agent_graph()
    return _compiled_graph
```

Remove the imports that were only used by the old graph:
```python
# Remove these lines:
from orchestrator.nodes.intent import intent_classifier_node
from orchestrator.nodes.tools import tool_planner_node, tool_execution_node
from orchestrator.subgraphs.deep_research import deep_research_node
```

- [ ] **Step 4: Delete old files**

```bash
rm backend/orchestrator/nodes/intent.py
rm backend/orchestrator/nodes/tools.py
rm backend/orchestrator/subgraphs/deep_research.py
```

- [ ] **Step 5: Run full test suite**

```bash
cd backend && pytest tests/ -v --tb=short -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(agents): promote multi-agent graph to default, remove single-agent nodes"
```
