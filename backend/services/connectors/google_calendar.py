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
        from datetime import datetime, timezone

        start = raw.get("start", {})
        end = raw.get("end", {})
        start_str = start.get("dateTime") or start.get("date") or ""
        end_str = end.get("dateTime") or end.get("date") or ""

        # Parse start datetime to UTC ISO string
        item_at: Optional[str] = None
        if start_str:
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                item_at = dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                item_at = start_str

        # Build attendee display names
        attendees = raw.get("attendees", [])
        attendee_names = [
            a.get("displayName") or a.get("email", "") for a in attendees
        ]
        attendee_str = ", ".join(attendee_names) if attendee_names else "none"

        # Rich body: description + attendees + time range
        desc = (raw.get("description") or "").strip()
        body_parts = []
        if desc:
            body_parts.append(desc)
        body_parts.append(f"Attendees: {attendee_str}")
        body_parts.append(f"{start_str} → {end_str}")
        body = "\n".join(body_parts)

        return SourceItem(
            user_id=user_id,
            source_type=self.source_type,
            source_item_type="calendar_event",
            external_id=raw["id"],
            title=raw.get("summary", "(no title)"),
            body=body,
            item_at=item_at,
            metadata={
                "location": raw.get("location"),
                "hangoutLink": raw.get("hangoutLink"),
                "organizer_email": raw.get("organizer", {}).get("email"),
            },
        )
