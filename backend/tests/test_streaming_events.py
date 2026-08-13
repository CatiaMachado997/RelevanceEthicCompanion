"""Sprint J Task 15: assert the new SSE event types fire in expected order."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_streaming_events_emitted_in_order():
    """With STREAMING_REASONING_ENABLED, a turn that calls one tool emits:
    thought_token (>=1) → plan_step_actions → action_start → action_complete
    → done."""
    from orchestrator import graph as graph_mod

    # Patch the flag on the module-level alias
    with patch.object(graph_mod, "_settings") as mock_settings:
        mock_settings.STREAMING_REASONING_ENABLED = True

        fake_graph = MagicMock()

        async def fake_astream(state_or_cmd, config, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "tool_planner"},
                "data": {"chunk": MagicMock(content="Need to check calendar")},
            }
            yield {
                "event": "on_chain_end",
                "metadata": {"langgraph_node": "tool_planner"},
                "data": {
                    "output": {
                        "plan_steps": [
                            {
                                "step": 1,
                                "thought": "x",
                                "actions": [{"tool": "query_calendar", "params": {}}],
                                "observations": [],
                            }
                        ],
                        "planner_run_id": "run-1",
                    }
                },
            }
            yield {
                "event": "on_chain_end",
                "metadata": {"langgraph_node": "tool_execution"},
                "data": {
                    "output": {
                        "plan_steps": [
                            {
                                "step": 1,
                                "thought": "x",
                                "actions": [{"tool": "query_calendar", "params": {}}],
                                "observations": [{"status": "ok", "latency_ms": 42}],
                            }
                        ],
                        "planner_run_id": "run-1",
                        "response_events": [
                            {"event": "tool_use", "tool": "query_calendar"},
                            {"event": "tool_result", "tool": "query_calendar"},
                        ],
                        "citations": [],
                        "document_sources": [],
                    }
                },
            }
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "tool_execution"},
                "data": {"chunk": MagicMock(content="You have a meeting at 10.")},
            }
            yield {
                "event": "on_chain_end",
                "name": "LangGraph",
                "data": {"output": {"response_text": "You have a meeting at 10."}},
            }

        fake_graph.astream_events = fake_astream

        with patch(
            "orchestrator.graph.get_graph_async", AsyncMock(return_value=fake_graph)
        ), patch("orchestrator.graph._post_stream_store", AsyncMock(return_value=None)):
            events = []
            async for ev in graph_mod.stream_langgraph(
                user_id="u-1",
                message="what's on my calendar?",
                model="x",
                conversation_id="c-1",
            ):
                events.append(ev)

    event_types = [ev.get("event") for ev in events]
    assert "thought_token" in event_types, f"got: {event_types}"
    assert "plan_step_actions" in event_types
    assert "action_start" in event_types
    assert "action_complete" in event_types
    assert event_types.index("thought_token") < event_types.index("plan_step_actions")
    assert event_types.index("plan_step_actions") < event_types.index("action_start")
    assert event_types.index("action_start") < event_types.index("action_complete")
    assert "done" in event_types


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming_reasoning_enabled", [False, True])
async def test_saved_item_is_streamed_and_persisted_with_assistant_turn(
    streaming_reasoning_enabled,
):
    from orchestrator import graph as graph_mod

    saved_item = {
        "id": "goal-1",
        "kind": "goal",
        "label": "Ship release",
        "destination": "Goals",
        "duplicate": False,
    }
    fake_graph = MagicMock()

    async def fake_astream(_state, _config, **_kwargs):
        yield {
            "event": "on_chain_end",
            "metadata": {"langgraph_node": "tool_execution"},
            "data": {
                "output": {
                    "response_events": [
                        {
                            "event": "tool_result",
                            "tool": "create_goal",
                            "saved_item": saved_item,
                        }
                    ],
                    "tool_results": [{"tool": "create_goal", "result": "saved"}],
                    "citations": [],
                    "document_sources": [],
                    "plan_steps": [],
                }
            },
        }
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_node": "tool_execution"},
            "data": {"chunk": MagicMock(content="Created goal.")},
        }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {"response_text": "Created goal."}},
        }

    fake_graph.astream_events = fake_astream
    store = AsyncMock(
        return_value={"user_turn_id": "u-turn", "assistant_turn_id": "a-turn"}
    )
    with patch.object(
        graph_mod._settings,
        "STREAMING_REASONING_ENABLED",
        streaming_reasoning_enabled,
    ), patch.dict("os.environ", {"MULTI_AGENT": "false"}), patch(
        "orchestrator.graph.get_graph", return_value=fake_graph
    ), patch(
        "orchestrator.graph.get_graph_async", AsyncMock(return_value=fake_graph)
    ), patch(
        "orchestrator.graph._post_stream_store", store
    ):
        events = [
            event
            async for event in graph_mod.stream_langgraph(
                user_id="u-1", message="create a goal", model="x", conversation_id="c-1"
            )
        ]

    assert any(event.get("saved_item") == saved_item for event in events)
    assert next(event for event in events if event["event"] == "done")[
        "saved_items"
    ] == [saved_item]
    assert store.await_args.kwargs["saved_items"] == [saved_item]
