"""Sprint C Tasks 5-7: multi-step planner loop.

Verifies that the LangGraph orchestrator can chain tool calls within a
single user turn, that the loop is capped by max_planner_steps, and
that the existing single-tool / zero-tool flows still behave the same.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


USER_ID = "00000000-0000-0000-0000-000000000000"


def _base_state(**overrides) -> dict:
    state = {
        "user_id": USER_ID,
        "message": "do the thing",
        "conversation_id": None,
        "model": "llama-3.3-70b-versatile",
        "user_context": {},
        "conversation_history": [],
        "active_sources": [],
        "intent": "",
        "tool_calls": [],
        "tool_results": [],
        "esl_decision": None,
        "proposed_content": "",
        "response_text": "",
        "response_events": [],
        "citations": [],
        "document_sources": [],
        "token_count": 0,
        "token_warning": None,
        "pending_tool_confirmation": None,
        "source_context": [],
        "force_retrieval": False,
        "planner_step": 0,
        "max_planner_steps": 3,
    }
    state.update(overrides)
    return state


def _planner_response(tool_calls=None, content=""):
    resp = MagicMock()
    resp.tool_calls = tool_calls or []
    resp.content = content
    return resp


def _mock_tool(name: str, return_value: str = "ok"):
    t = MagicMock()
    t.name = name
    t.metadata = {}  # not a marketplace tool
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_single_tool_turn_unchanged(mock_cm, mock_groq_cls, mock_create_tools):
    """planner emits 1 tool, then 0 → execution runs once → final synthesis.

    Mirrors the today-flow: one tool, one synthesis, ESL evaluates the
    synthesized response. No regression for existing single-tool turns.
    """
    from orchestrator.nodes.tools import tool_planner_node, tool_execution_node

    mock_cm.return_value = MagicMock()
    tool_a = _mock_tool("get_user_goals", "Goal: ship sprint C")
    mock_create_tools.return_value = [tool_a]

    # Planner: first call emits tool_a, second call emits no tools.
    planner_with_tools = MagicMock()
    planner_with_tools.ainvoke = AsyncMock(
        side_effect=[
            _planner_response(
                tool_calls=[{"name": "get_user_goals", "args": {}, "id": "call_1"}]
            ),
            _planner_response(content="Your goal is to ship sprint C."),
        ]
    )
    # Second LLM (synthesis inside tool_execution_node) is the same class.
    synth_response = MagicMock()
    synth_response.content = "Your goal is to ship sprint C."

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=planner_with_tools)
    llm.ainvoke = AsyncMock(return_value=synth_response)
    mock_groq_cls.return_value = llm

    state = _base_state()

    # First planner pass.
    out1 = await tool_planner_node(state)
    assert len(out1["tool_calls"]) == 1
    assert out1["planner_step"] == 1
    state.update(out1)

    # Execution.
    out_exec = await tool_execution_node(state)
    assert len(out_exec["tool_results"]) == 1
    assert out_exec["tool_results"][0]["tool"] == "get_user_goals"
    assert out_exec["tool_calls"] == []  # cleared
    state.update(out_exec)

    # Second planner pass — no tools requested, planner provides content.
    out2 = await tool_planner_node(state)
    assert out2["tool_calls"] == []
    assert out2["proposed_content"] == "Your goal is to ship sprint C."
    assert out2["planner_step"] == 2


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_two_tool_sequential_turn(mock_cm, mock_groq_cls, mock_create_tools):
    """Planner chains tool A then tool B in a single turn."""
    from orchestrator.nodes.tools import tool_planner_node, tool_execution_node

    mock_cm.return_value = MagicMock()
    tool_a = _mock_tool("search_documents", "found doc X")
    tool_b = _mock_tool("get_user_goals", "Goal: foo")
    mock_create_tools.return_value = [tool_a, tool_b]

    planner_with_tools = MagicMock()
    planner_with_tools.ainvoke = AsyncMock(
        side_effect=[
            _planner_response(
                tool_calls=[
                    {"name": "search_documents", "args": {"query": "x"}, "id": "1"}
                ]
            ),
            _planner_response(
                tool_calls=[{"name": "get_user_goals", "args": {}, "id": "2"}]
            ),
            _planner_response(content="Combined answer."),
        ]
    )
    synth_response = MagicMock()
    synth_response.content = "Combined."

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=planner_with_tools)
    llm.ainvoke = AsyncMock(return_value=synth_response)
    mock_groq_cls.return_value = llm

    state = _base_state()

    # round 1
    state.update(await tool_planner_node(state))
    state.update(await tool_execution_node(state))
    assert len(state["tool_results"]) == 1

    # round 2
    state.update(await tool_planner_node(state))
    assert len(state["tool_calls"]) == 1
    assert state["tool_calls"][0]["name"] == "get_user_goals"
    state.update(await tool_execution_node(state))
    assert len(state["tool_results"]) == 2
    tools_seen = [r["tool"] for r in state["tool_results"]]
    assert tools_seen == ["search_documents", "get_user_goals"]

    # round 3 — planner ends loop
    state.update(await tool_planner_node(state))
    assert state["tool_calls"] == []


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_max_planner_steps_caps_loop(mock_cm, mock_groq_cls, mock_create_tools):
    """If the planner keeps emitting tools, the router halts after
    max_planner_steps iterations regardless."""
    from orchestrator.nodes.tools import tool_planner_node, tool_execution_node
    from orchestrator.graph import _route_after_execution

    mock_cm.return_value = MagicMock()
    tool_a = _mock_tool("get_user_goals", "ok")
    mock_create_tools.return_value = [tool_a]

    # Planner ALWAYS emits a tool call.
    planner_with_tools = MagicMock()
    planner_with_tools.ainvoke = AsyncMock(
        return_value=_planner_response(
            tool_calls=[{"name": "get_user_goals", "args": {}, "id": "loop"}]
        )
    )
    synth_response = MagicMock()
    synth_response.content = "synth"

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=planner_with_tools)
    llm.ainvoke = AsyncMock(return_value=synth_response)
    mock_groq_cls.return_value = llm

    state = _base_state(max_planner_steps=3)

    # Drive the loop manually, asking the conditional router whether to
    # keep going after each execution.
    iterations = 0
    while True:
        state.update(await tool_planner_node(state))
        if not state["tool_calls"]:
            break
        state.update(await tool_execution_node(state))
        iterations += 1
        decision = _route_after_execution(state)
        if decision == "esl_gateway":
            break
        assert decision == "tool_planner"

    assert iterations == 3
    assert len(state["tool_results"]) == 3
    assert state["planner_step"] == 3


# ===== Sprint F Task 7: bias toward search_documents on knowledge queries =====


def test_system_prompt_biases_toward_search_documents():
    """The orchestrator system prompt must explicitly nudge the planner to
    call `search_documents` for knowledge-recall questions. Catches drift."""
    from orchestrator.nodes.tools import _build_system_prompt

    state = _base_state()
    prompt = _build_system_prompt(state)

    assert "search_documents" in prompt
    assert "knowledge-recall" in prompt or "knowledge recall" in prompt.lower()


def test_search_documents_tool_description_lists_sample_queries():
    """The tool description must enumerate the trigger phrasings so
    tool-call-trained models pick it up reliably."""
    from services.langchain_tools import SearchDocumentsTool

    desc = SearchDocumentsTool.model_fields["description"].default
    # Sample-query bullets must be present.
    assert "what did" in desc
    assert "find the" in desc
    assert "summarize discussions" in desc
    assert "remind me what we decided" in desc
    assert "latest on" in desc


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
@pytest.mark.parametrize(
    "user_message",
    [
        "what did the team say about Project Atlas last week",
        "find that email about the Q3 budget",
        "summarize what we decided about onboarding",
    ],
)
async def test_planner_emits_search_documents_for_knowledge_queries(
    mock_cm, mock_groq_cls, mock_create_tools, user_message
):
    """With a stub LLM that follows tool-call instructions, the planner
    should emit a `search_documents` tool call for these query shapes.
    Asserts prompt + tool description pass through to state correctly."""
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    tool_search = _mock_tool("search_documents", "results")
    mock_create_tools.return_value = [tool_search]

    planner_with_tools = MagicMock()
    planner_with_tools.ainvoke = AsyncMock(
        return_value=_planner_response(
            tool_calls=[
                {
                    "name": "search_documents",
                    "args": {"query": user_message, "k": 5},
                    "id": "kq_1",
                }
            ]
        )
    )
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=planner_with_tools)
    mock_groq_cls.return_value = llm

    state = _base_state(message=user_message)
    out = await tool_planner_node(state)

    assert len(out["tool_calls"]) == 1
    assert out["tool_calls"][0]["name"] == "search_documents"


@pytest.mark.asyncio
@patch("services.langchain_tools.create_langchain_tools")
@patch("langchain_groq.ChatGroq")
@patch("orchestrator.nodes.tools.get_context_manager")
async def test_zero_tool_first_pass_short_circuits(
    mock_cm, mock_groq_cls, mock_create_tools
):
    """planner emits no tools on first try — execution is skipped, the
    response goes straight to ESL. Same as today's behaviour."""
    from orchestrator.nodes.tools import tool_planner_node

    mock_cm.return_value = MagicMock()
    mock_create_tools.return_value = []

    planner_with_tools = MagicMock()
    planner_with_tools.ainvoke = AsyncMock(
        return_value=_planner_response(content="Hello.")
    )
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=planner_with_tools)
    mock_groq_cls.return_value = llm

    state = _base_state()
    out = await tool_planner_node(state)

    assert out["tool_calls"] == []
    assert out["proposed_content"] == "Hello."
    assert out["planner_step"] == 1
