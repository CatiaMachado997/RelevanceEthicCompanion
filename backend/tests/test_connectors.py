# backend/tests/test_connectors.py
import pytest
from services.connectors.base import BaseConnector, SourceItem


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
