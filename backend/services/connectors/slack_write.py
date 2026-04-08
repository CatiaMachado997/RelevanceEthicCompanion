"""Slack connector with write actions (send_message + read_channel)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API = "https://slack.com/api"


class SlackWriteConnector(BaseConnector):
    source_type = "slack"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        params = urlencode({
            "client_id": settings.SLACK_CLIENT_ID,
            "scope": "channels:read,chat:write,channels:history",
            "state": state or "",
        })
        return f"{SLACK_AUTH_URL}?{params}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        # NOTE: blocking call — callers should use asyncio.to_thread
        resp = httpx.post(
            SLACK_TOKEN_URL,
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,
            "team_id": data.get("team", {}).get("id"),
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch recent messages from joined channels."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{SLACK_API}/conversations.list",
                    headers=_slack_headers(access_token),
                    params={"types": "public_channel,private_channel", "limit": 10},
                    timeout=10,
                )
                resp.raise_for_status()
                channels = resp.json().get("channels", [])[:3]
        except httpx.HTTPStatusError as e:
            logger.warning(f"fetch_raw_items (channels) failed: {e.response.status_code}")
            return []

        messages: List[Dict[str, Any]] = []
        for ch in channels:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{SLACK_API}/conversations.history",
                        headers=_slack_headers(access_token),
                        params={"channel": ch["id"], "limit": 5},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    for m in resp.json().get("messages", []):
                        m["_channel_name"] = ch.get("name", "")
                        messages.append(m)
            except httpx.HTTPStatusError as e:
                logger.warning("conversations.history failed for channel %s: %s", ch.get("id"), e.response.status_code)
        return messages

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type="slack",
            source_item_type="message",
            external_id=raw.get("ts", ""),
            title=raw.get("text", "")[:120],
            body=raw.get("text", ""),
            item_at=None,
            metadata={"channel": raw.get("_channel_name", ""), "ts": raw.get("ts", "")},
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        token = credentials.get("access_token", "")
        if not token:
            return "Error: no access token — reconnect this tool in Settings → Integrations"
        if action_name == "read_channel":
            return await self._read_channel(token, params)
        if action_name == "send_message":
            return await self._send_message(token, params)
        return f"Unknown action: {action_name}"

    async def _read_channel(self, token: str, params: dict) -> str:
        channel = params.get("channel", "")
        if not channel:
            return "Error: 'channel' parameter required (e.g. 'general')"
        limit = min(int(params.get("limit", 10)), 20)
        try:
            async with httpx.AsyncClient(headers=_slack_headers(token)) as client:
                resp = await client.get(
                    f"{SLACK_API}/conversations.history",
                    params={"channel": channel, "limit": limit},
                    timeout=10,
                )
                resp.raise_for_status()
                messages = resp.json().get("messages", [])
        except httpx.HTTPStatusError as e:
            return f"Slack API error {e.response.status_code}: {e.response.text[:200]}"
        if not messages:
            return f"No recent messages in #{channel}."
        lines = [f"- {m.get('text', '')[:100]}" for m in messages]
        return f"Recent messages in #{channel}:\n" + "\n".join(lines)

    async def _send_message(self, token: str, params: dict) -> str:
        channel = params.get("channel", "")
        text = params.get("text", "")
        if not channel or not text:
            return "Error: 'channel' and 'text' are required"
        try:
            async with httpx.AsyncClient(headers=_slack_headers(token)) as client:
                resp = await client.post(
                    f"{SLACK_API}/chat.postMessage",
                    json={"channel": channel, "text": text},
                    timeout=10,
                )
                resp.raise_for_status()
                result = resp.json()
        except httpx.HTTPStatusError as e:
            return f"Slack API error {e.response.status_code}: {e.response.text[:200]}"
        if not result.get("ok"):
            return f"Slack error: {result.get('error', 'unknown')}"
        return f"✓ Message sent to #{channel}"


def _slack_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
