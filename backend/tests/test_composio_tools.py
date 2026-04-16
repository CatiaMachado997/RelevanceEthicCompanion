"""
Tests for services/composio_tools.py

Mocks _get_composio_client — never calls the real Composio API.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from services.composio_tools import (
    TOOL_ID_TO_COMPOSIO_TOOLKIT,
    _ACTION_METADATA,
    _TOOLKIT_ACTIONS,
    get_composio_tools_for_user,
)


class TestGetComposioToolsForUser:

    def test_returns_empty_list_when_no_tools_connected(self):
        """Empty connected_tool_ids → [] without touching the Composio client."""
        result = asyncio.run(get_composio_tools_for_user("user-123", set()))
        assert result == []

    def test_returns_empty_when_api_key_missing(self):
        """If COMPOSIO_API_KEY is not set, return [] and log a warning."""
        with patch("services.composio_tools.settings") as mock_settings:
            mock_settings.COMPOSIO_API_KEY = ""
            result = asyncio.run(get_composio_tools_for_user("user-123", {"github"}))
        assert result == []

    def test_tags_tool_with_esl_metadata(self):
        """Tools returned from Composio are stamped with ESL metadata."""
        mock_tool = MagicMock()
        mock_tool.name = "GITHUB_CREATE_AN_ISSUE"
        mock_tool.metadata = {}

        mock_session = MagicMock()
        mock_session.tools.return_value = [mock_tool]

        mock_client = MagicMock()
        mock_client.create.return_value = mock_session

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                result = asyncio.run(
                    get_composio_tools_for_user("user-abc", {"github"})
                )

        assert len(result) == 1
        tagged = result[0]
        assert tagged.metadata["tool_id"] == "github"
        assert tagged.metadata["action_name"] == "create_issue"
        assert tagged.metadata["risk_level"] == "medium"

    def test_skips_toolkits_not_in_connected_ids(self):
        """Only toolkits that map to connected_tool_ids are passed to Composio."""
        mock_session = MagicMock()
        mock_session.tools.return_value = []

        mock_client = MagicMock()
        mock_client.create.return_value = mock_session

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                asyncio.run(get_composio_tools_for_user("user-xyz", {"notion"}))

        toolkits_passed = mock_client.create.call_args.kwargs["toolkits"]
        assert "github" not in toolkits_passed
        assert "notion" in toolkits_passed

    def test_graceful_failure_returns_empty_list(self):
        """If client.create() raises, return [] instead of propagating."""
        mock_client = MagicMock()
        mock_client.create.side_effect = RuntimeError("Composio network error")

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                result = asyncio.run(
                    get_composio_tools_for_user("user-fail", {"github"})
                )

        assert result == []

    def test_tool_id_to_composio_toolkit_covers_all_known_tools(self):
        """Mapping covers the five tool IDs the rest of the system expects."""
        expected = {"github", "notion", "slack", "gmail_write", "google_calendar_write"}
        assert set(TOOL_ID_TO_COMPOSIO_TOOLKIT.keys()) == expected

    def test_fallback_metadata_for_unknown_action(self):
        """Unknown action slugs get a safe fallback instead of raising."""
        mock_tool = MagicMock()
        mock_tool.name = "GITHUB_SOMETHING_UNKNOWN"
        mock_tool.metadata = {}

        mock_session = MagicMock()
        mock_session.tools.return_value = [mock_tool]

        mock_client = MagicMock()
        mock_client.create.return_value = mock_session

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                result = asyncio.run(
                    get_composio_tools_for_user("user-abc", {"github"})
                )

        assert len(result) == 1
        tagged = result[0]
        assert tagged.metadata["tool_id"] == "composio"
        assert tagged.metadata["action_name"] == "GITHUB_SOMETHING_UNKNOWN"
        assert tagged.metadata["risk_level"] == "medium"

    def test_existing_metadata_is_preserved(self):
        """ESL fields are merged into any pre-existing metadata on the tool object."""
        mock_tool = MagicMock()
        mock_tool.name = "NOTION_SEARCH"
        mock_tool.metadata = {"provider": "composio", "version": "1"}

        mock_session = MagicMock()
        mock_session.tools.return_value = [mock_tool]

        mock_client = MagicMock()
        mock_client.create.return_value = mock_session

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                result = asyncio.run(
                    get_composio_tools_for_user("user-abc", {"notion"})
                )

        tagged = result[0]
        # ESL fields present
        assert tagged.metadata["tool_id"] == "notion"
        assert tagged.metadata["action_name"] == "search_pages"
        assert tagged.metadata["risk_level"] == "low"
        # pre-existing field preserved
        assert tagged.metadata["provider"] == "composio"
        assert tagged.metadata["version"] == "1"

    def test_action_metadata_covers_all_toolkit_actions(self):
        """Every slug in _TOOLKIT_ACTIONS has a corresponding entry in _ACTION_METADATA."""
        missing = []
        for toolkit, actions in _TOOLKIT_ACTIONS.items():
            for action_slug in actions:
                if action_slug not in _ACTION_METADATA:
                    missing.append(action_slug)
        assert missing == [], f"Missing _ACTION_METADATA entries: {missing}"

    def test_multiple_connected_toolkits(self):
        """Two connected tool IDs → both toolkits included in create() call."""
        mock_session = MagicMock()
        mock_session.tools.return_value = []

        mock_client = MagicMock()
        mock_client.create.return_value = mock_session

        with patch(
            "services.composio_tools._get_composio_client", return_value=mock_client
        ):
            with patch("services.composio_tools.settings") as mock_settings:
                mock_settings.COMPOSIO_API_KEY = "test-key"
                asyncio.run(
                    get_composio_tools_for_user("user-multi", {"github", "notion"})
                )

        call_kwargs = mock_client.create.call_args.kwargs
        toolkits_passed = call_kwargs["toolkits"]
        assert "github" in toolkits_passed
        assert "notion" in toolkits_passed
