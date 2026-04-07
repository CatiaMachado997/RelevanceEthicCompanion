# backend/tests/test_connectors.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.connectors.base import BaseConnector, SourceItem
from services.connectors.google_calendar import GoogleCalendarConnector
from services.connectors.gmail import GmailConnector
from services.connectors.slack import SlackConnector


class ConcreteConnector(BaseConnector):
    """Minimal concrete subclass for testing the ABC."""
    source_type = "test_source"

    def get_authorization_url(self, user_id: str, state=None) -> str:
        return "https://example.com/auth"

    def exchange_code_for_tokens(self, code: str):
        return {"access_token": "tok", "refresh_token": "ref", "expires_at": None}

    async def fetch_raw_items(self, access_token: str, refresh_token=None):
        return [{"id": "1", "title": "Test Item", "content": "body"}]

    def normalize_to_source_item(self, raw: dict, user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="test",
            external_id=raw["id"],
            title=raw["title"],
            body=raw.get("content"),
        )


def test_base_connector_interface():
    conn = ConcreteConnector()
    assert conn.source_type == "test_source"
    url = conn.get_authorization_url("user-123")
    assert url.startswith("https://")


def test_normalize_to_source_item():
    conn = ConcreteConnector()
    item = conn.normalize_to_source_item({"id": "x1", "title": "Hello", "content": "World"}, "user-1")
    assert item.external_id == "x1"
    assert item.title == "Hello"
    assert item.source_type == "test_source"


def test_source_item_has_required_fields():
    item = SourceItem(
        user_id="u",
        source_type="google_calendar",
        source_item_type="event",
        external_id="evt_123",
        title="Meeting",
    )
    assert item.embedding_status == "pending"
    assert item.sensitivity == 0


# --- GoogleCalendarConnector tests ---

def test_google_calendar_connector_source_type():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    assert conn.source_type == "google_calendar"


def test_google_calendar_normalize_event():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "evt_abc",
        "summary": "Standup",
        "description": "Daily sync",
        "start": {"dateTime": "2026-03-28T09:00:00Z"},
        "end": {"dateTime": "2026-03-28T09:30:00Z"},
        "location": "Zoom",
        "attendees": [{"email": "a@b.com"}],
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "evt_abc"
    assert item.title == "Standup"
    assert item.source_item_type == "calendar_event"
    assert item.source_type == "google_calendar"
    assert item.item_at is not None and "2026-03-28" in item.item_at
    assert "location" in item.metadata


def test_google_calendar_normalize_all_day_event():
    conn = GoogleCalendarConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "evt_allday",
        "summary": "Holiday",
        "start": {"date": "2026-03-28"},
        "end": {"date": "2026-03-29"},
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "evt_allday"
    assert item.item_at == "2026-03-28T00:00:00+00:00"


# --- GmailConnector tests ---

def test_gmail_connector_source_type():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    assert conn.source_type == "gmail"


def test_gmail_normalize_message():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    raw = {
        "id": "msg_abc",
        "subject": "Sprint review notes",
        "from": "alice@example.com",
        "date": "Fri, 28 Mar 2026 10:00:00 +0000",
        "snippet": "Here are the notes from today...",
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "msg_abc"
    assert item.title == "Sprint review notes"
    assert item.source_item_type == "email"
    assert item.source_type == "gmail"
    assert "alice@example.com" in item.body
    assert item.metadata["from_email"] == "alice@example.com"


def test_gmail_normalize_no_subject():
    conn = GmailConnector(redirect_uri="https://example.com/callback")
    raw = {"id": "msg_1", "subject": "", "from": "b@c.com", "date": "", "snippet": "hi"}
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.title == "(no subject)"


# --- SlackConnector tests ---

def test_slack_connector_source_type():
    conn = SlackConnector()
    assert conn.source_type == "slack"


def test_slack_normalize_message():
    conn = SlackConnector()
    raw = {
        "channel": "general",
        "text": "Deployment done",
        "ts": "1743160800.000000",
        "user": "U01ABCDEF",
    }
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.external_id == "general_1743160800.000000"
    assert item.title == "#general"
    assert item.body == "Deployment done"
    assert item.source_item_type == "message"
    assert item.source_type == "slack"
    assert item.metadata["channel"] == "general"
    assert item.metadata["ts"] == "1743160800.000000"


def test_slack_normalize_empty_text():
    conn = SlackConnector()
    raw = {"channel": "dev", "text": "", "ts": "111.0", "user": "U123"}
    item = conn.normalize_to_source_item(raw, "user-1")
    assert item.title == "#dev"
    assert item.body == ""


@pytest.mark.asyncio
async def test_sync_writes_to_source_items():
    """Sync should write normalized items via _store_normalized_item."""
    from services.data_ingestion import DataIngestionService
    from services.connectors.base import SourceItem

    mock_cm = MagicMock()
    mock_cm.weaviate = None  # Weaviate offline — should not block sync

    service = DataIngestionService(mock_cm)

    fake_item = SourceItem(
        user_id="user-1",
        source_type="google_calendar",
        source_item_type="event",
        external_id="evt_1",
        title="Standup",
    )
    mock_connector = MagicMock()
    mock_connector.fetch_raw_items = AsyncMock(return_value=[{"id": "evt_1", "summary": "Standup", "start": {}, "end": {}}])
    mock_connector.normalize_to_source_item.return_value = fake_item

    written_items = []

    async def fake_store(item):
        written_items.append(item)

    with patch("services.data_ingestion.get_connector", return_value=mock_connector), \
         patch.object(service, "_get_valid_token", new_callable=AsyncMock,
                      return_value="tok"), \
         patch.object(service, "_store_normalized_item", side_effect=fake_store), \
         patch.object(service, "_update_last_sync", new_callable=AsyncMock), \
         patch.object(service, "_clear_sync_error", new_callable=AsyncMock):
        result = await service.sync_data_source("user-1", "google_calendar")

    assert result["success"] is True
    assert result["items_synced"] == 1
    assert len(written_items) == 1
    assert written_items[0].external_id == "evt_1"
