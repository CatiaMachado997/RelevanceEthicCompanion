# backend/services/connectors/slack.py
"""Slack connector — wraps SlackSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.slack_sync import SlackSync


class SlackConnector(BaseConnector):
    source_type = "slack"

    def __init__(self):
        self._sync = SlackSync()

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._sync.fetch_messages(access_token=access_token)

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        channel = raw.get("channel", "")
        ts = raw.get("ts", "")

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="message",
            external_id=f"{channel}_{ts}",
            title=f"#{channel}",
            body=raw.get("text", ""),
            metadata={
                "channel": channel,
                "ts": ts,
                "user": raw.get("user"),
            },
        )
