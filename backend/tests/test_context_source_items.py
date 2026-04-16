import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ─── ContextManager tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_context_builder_populates_source_context():
    """context_builder_node calls get_recent_source_items and stores result in state."""
    from orchestrator.nodes.context import context_builder_node

    fake_items = [
        {
            "source_type": "google_calendar",
            "source_item_type": "calendar_event",
            "title": "Standup",
            "body": "",
            "item_at": "2026-04-08T09:00:00+00:00",
        },
    ]

    with patch("orchestrator.nodes.context.get_context_manager") as mock_gcm:
        cm = MagicMock()
        cm.get_user_context = AsyncMock(
            return_value=MagicMock(
                active_goals=[], user_values=[], focus_mode=False, additional_context={}
            )
        )
        cm.get_conversation_history = AsyncMock(return_value=[])
        cm.get_recent_source_items = AsyncMock(return_value=fake_items)
        mock_gcm.return_value = cm

        state = {
            "user_id": "u1",
            "conversation_id": None,
            "source_context": [],
        }
        result = await context_builder_node(state)

    assert "source_context" in result
    assert result["source_context"] == fake_items
    assert result["user_context"]["source_context"] == fake_items


@pytest.mark.asyncio
async def test_context_builder_empty_when_no_items():
    """`source_context` is [] when get_recent_source_items returns empty."""
    from orchestrator.nodes.context import context_builder_node

    with patch("orchestrator.nodes.context.get_context_manager") as mock_gcm:
        cm = MagicMock()
        cm.get_user_context = AsyncMock(
            return_value=MagicMock(
                active_goals=[], user_values=[], focus_mode=False, additional_context={}
            )
        )
        cm.get_conversation_history = AsyncMock(return_value=[])
        cm.get_recent_source_items = AsyncMock(return_value=[])
        mock_gcm.return_value = cm

        result = await context_builder_node({"user_id": "u1", "conversation_id": None})

    assert result["source_context"] == []


def test_system_prompt_includes_context_section():
    """Non-empty source_context → system prompt contains '## Your current context'."""
    from orchestrator.nodes.tools import _build_system_prompt

    state = {
        "user_context": {
            "active_goals": [],
            "user_values": [],
            "snapshot": {},
            "source_context": [
                {
                    "source_type": "google_calendar",
                    "source_item_type": "calendar_event",
                    "title": "Team standup",
                    "body": "",
                    "item_at": "2026-04-08T09:00:00+00:00",
                },
                {
                    "source_type": "gmail",
                    "source_item_type": "email",
                    "title": "Hello world",
                    "body": "From: alice",
                    "item_at": "2026-04-07T10:00:00+00:00",
                },
            ],
        },
    }
    prompt = _build_system_prompt(state)
    assert "## Your current context" in prompt
    assert "Team standup" in prompt
    assert "Hello world" in prompt


def test_system_prompt_omits_section_when_empty():
    """Empty source_context → no '## Your current context' section in prompt."""
    from orchestrator.nodes.tools import _build_system_prompt

    state = {
        "user_context": {
            "active_goals": [],
            "user_values": [],
            "snapshot": {},
            "source_context": [],
        },
    }
    prompt = _build_system_prompt(state)
    assert "## Your current context" not in prompt
