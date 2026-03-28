# backend/services/connectors/google_calendar.py
"""Google Calendar connector — wraps GoogleCalendarSync, implements BaseConnector."""
from typing import Any, Dict, List, Optional

from services.connectors.base import BaseConnector, SourceItem
from services.google_calendar_sync import GoogleCalendarSync


class GoogleCalendarConnector(BaseConnector):
    source_type = "google_calendar"

    def __init__(self, redirect_uri: str):
        self._sync = GoogleCalendarSync(redirect_uri=redirect_uri)

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        return self._sync.get_authorization_url(user_id, oauth_state=state)

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        return self._sync.exchange_code_for_tokens(code)

    async def fetch_raw_items(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._sync.fetch_events(
            access_token=access_token,
            refresh_token=refresh_token or "",
        )

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        start = raw.get("start", {})
        item_at = start.get("dateTime") or start.get("date")

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="event",
            external_id=raw["id"],
            title=raw.get("summary", "(no title)"),
            body=raw.get("description"),
            item_at=item_at,
            metadata={
                "location": raw.get("location"),
                "end": raw.get("end", {}),
                "attendee_count": len(raw.get("attendees", [])),
                "organizer": raw.get("organizer", {}).get("email"),
            },
        )
