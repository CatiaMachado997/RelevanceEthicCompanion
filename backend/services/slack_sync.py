"""
Slack Sync Service — read-only using OAuth 2.0.
Requires a Slack app with: channels:history, channels:read scopes.
"""

import httpx
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
import logging

from config import settings

logger = logging.getLogger(__name__)

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_CHANNELS_URL = "https://slack.com/api/conversations.list"
SLACK_HISTORY_URL = "https://slack.com/api/conversations.history"


class SlackSync:
    """Slack integration with OAuth 2.0 (read-only)"""

    SCOPES = "channels:history,channels:read"

    def get_authorization_url(self, user_id: str, oauth_state: Optional[str] = None) -> str:
        params = {
            "client_id": settings.SLACK_CLIENT_ID,
            "scope": self.SCOPES,
            "redirect_uri": settings.SLACK_REDIRECT_URI,
            "state": oauth_state or user_id,
        }
        return f"{SLACK_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        response = httpx.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.SLACK_REDIRECT_URI,
            }
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ValueError(f"Slack token exchange failed: {data.get('error')}")
        return {
            "access_token": data["access_token"],
            "refresh_token": None,
            "expires_at": None,
            "team": data.get("team", {}).get("name", "")
        }

    def fetch_messages(
        self,
        access_token: str,
        max_channels: int = 5,
        max_messages_per_channel: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch recent messages from public channels"""
        headers = {"Authorization": f"Bearer {access_token}"}
        messages = []

        r = httpx.get(
            SLACK_CHANNELS_URL,
            headers=headers,
            params={"limit": max_channels, "exclude_archived": True, "types": "public_channel"}
        )
        r.raise_for_status()
        channels_data = r.json()
        if not channels_data.get("ok"):
            raise ValueError(f"Failed to fetch channels: {channels_data.get('error')}")

        for channel in channels_data.get("channels", []):
            hist = httpx.get(
                SLACK_HISTORY_URL,
                headers=headers,
                params={"channel": channel["id"], "limit": max_messages_per_channel}
            )
            hist.raise_for_status()
            hist_data = hist.json()
            if not hist_data.get("ok"):
                continue
            for msg in hist_data.get("messages", []):
                if msg.get("type") == "message" and msg.get("text"):
                    messages.append({
                        "channel": channel["name"],
                        "text": msg["text"],
                        "ts": msg["ts"],
                        "user": msg.get("user", ""),
                    })

        return messages
