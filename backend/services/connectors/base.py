# backend/services/connectors/base.py
"""
BaseConnector — abstract interface for all data source connectors.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceItem:
    """Normalized representation of an item from any external source."""
    user_id: str
    source_type: str
    source_item_type: str
    external_id: str
    title: str
    body: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    item_at: Optional[str] = None  # ISO-8601 timestamp
    embedding_status: str = "pending"
    sensitivity: int = 0


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    source_type: str  # must be set on subclass

    @abstractmethod
    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        """Return the OAuth authorization URL for this source."""
        ...

    @abstractmethod
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange an auth code for tokens. Return dict with access_token, refresh_token, expires_at."""
        ...

    @abstractmethod
    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw items from the external API using the provided tokens."""
        ...

    @abstractmethod
    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        """Convert a raw item dict into a normalized SourceItem."""
        ...

    @abstractmethod
    async def execute_action(self, action_name: str, params: dict, credentials: dict) -> str:
        """Execute a write or read action by name. Return a human-readable result string."""
        ...
