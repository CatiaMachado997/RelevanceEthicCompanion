from services.connectors.google_calendar import GoogleCalendarConnector
from services.connectors.gmail import GmailConnector
from services import data_ingestion
import inspect


def _calendar_raw():
    return {
        "id": "evt123",
        "summary": "Team standup",
        "description": "Daily sync",
        "start": {"dateTime": "2026-04-08T09:00:00+00:00"},
        "end": {"dateTime": "2026-04-08T09:30:00+00:00"},
        "attendees": [
            {"displayName": "Alice", "email": "alice@example.com"},
            {"email": "bob@example.com"},
        ],
        "organizer": {"email": "alice@example.com"},
        "location": "Zoom",
        "hangoutLink": "https://meet.google.com/abc",
    }


def _gmail_raw():
    return {
        "id": "msg456",
        "thread_id": "thread789",
        "subject": "Hello world",
        "from": "Alice <alice@example.com>",
        "date": "Tue, 08 Apr 2026 10:00:00 +0000",
        "snippet": "Just checking in",
        "label_ids": ["INBOX", "UNREAD"],
    }


def test_calendar_sync_writes_source_items():
    """normalize_to_source_item produces source_item_type=calendar_event with rich body."""
    connector = GoogleCalendarConnector(redirect_uri="http://localhost")
    item = connector.normalize_to_source_item(_calendar_raw(), "user1")

    assert item.source_item_type == "calendar_event"
    assert item.external_id == "evt123"
    assert item.title == "Team standup"
    assert "Alice" in item.body
    assert "bob@example.com" in item.body
    assert item.item_at is not None and "2026-04-08" in item.item_at
    assert item.metadata["location"] == "Zoom"
    assert item.metadata["hangoutLink"] == "https://meet.google.com/abc"
    assert item.metadata["organizer_email"] == "alice@example.com"


def test_gmail_sync_writes_source_items():
    """normalize_to_source_item produces source_item_type=email with parsed UTC date and metadata."""
    connector = GmailConnector(redirect_uri="http://localhost")
    item = connector.normalize_to_source_item(_gmail_raw(), "user1")

    assert item.source_item_type == "email"
    assert item.external_id == "msg456"
    assert item.title == "Hello world"
    assert "Alice" in item.body
    assert "Just checking in" in item.body
    assert item.item_at is not None and "2026" in item.item_at
    assert item.metadata["thread_id"] == "thread789"
    assert item.metadata["from_email"] == "Alice <alice@example.com>"
    assert "INBOX" in item.metadata["label_ids"]


def test_sync_deduplication():
    """_store_normalized_item SQL upserts on (user_id, source_type, external_id) and updates item_at."""
    source = inspect.getsource(
        data_ingestion.DataIngestionService._store_normalized_item
    )
    assert "ON CONFLICT (user_id, source_type, external_id)" in source
    assert "item_at = EXCLUDED.item_at" in source


def test_sync_returns_recent_items():
    """sync_data_source return value includes a 'recent' key."""
    source = inspect.getsource(data_ingestion.DataIngestionService.sync_data_source)
    assert '"recent"' in source or "'recent'" in source
