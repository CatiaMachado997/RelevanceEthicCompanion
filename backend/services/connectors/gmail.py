# backend/services/connectors/gmail.py
"""Gmail connector — wraps GmailSync, implements BaseConnector."""
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.gmail_sync import GmailSync


def _parse_email_date(date_str: str) -> Optional[str]:
    """Parse RFC-2822 email date string to UTC ISO string.

    Example input: 'Tue, 08 Apr 2026 10:00:00 +0000'
    Example output: '2026-04-08T10:00:00+00:00'
    """
    if not date_str or not date_str.strip():
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return date_str  # fallback: store as-is


class GmailConnector(BaseConnector):
    source_type = "gmail"

    def __init__(self, redirect_uri: str):
        self._sync = GmailSync(redirect_uri=redirect_uri)

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._sync.fetch_messages(
            access_token=access_token,
            refresh_token=refresh_token or "",
        )

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        sender = raw.get("from", "")
        subject = raw.get("subject") or "(no subject)"
        snippet = raw.get("snippet", "")
        body = f"From: {sender}\n{snippet}" if snippet else f"From: {sender}"

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="email",
            external_id=raw["id"],
            title=subject,
            body=body,
            item_at=_parse_email_date(raw.get("date", "")),
            metadata={
                "thread_id": raw.get("thread_id", ""),
                "from_email": sender,
                "label_ids": raw.get("label_ids", []),
            },
        )

    async def execute_action(self, action_name: str, params: dict, credentials: dict) -> str:
        return f"Action {action_name} not yet implemented for this connector"
