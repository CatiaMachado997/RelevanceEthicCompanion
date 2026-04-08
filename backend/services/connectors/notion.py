"""Notion connector — OAuth + read/write actions."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionConnector(BaseConnector):
    source_type = "notion"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        params = (
            f"client_id={settings.NOTION_CLIENT_ID}"
            f"&response_type=code"
            f"&owner=user"
            f"&redirect_uri={settings.BACKEND_URL}/api/tools/notion/oauth/callback"
            f"&state={state or ''}"
        )
        return f"{NOTION_AUTH_URL}?{params}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        import base64
        creds = base64.b64encode(
            f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()
        ).decode()
        resp = httpx.post(
            NOTION_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.BACKEND_URL}/api/tools/notion/oauth/callback",
            },
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,
            "workspace_id": data.get("workspace_id"),
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search recent pages."""
        async with httpx.AsyncClient(headers=_notion_headers(access_token)) as client:
            resp = await client.post(
                f"{NOTION_API}/search",
                json={"sort": {"direction": "descending", "timestamp": "last_edited_time"}, "page_size": 20},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        title = ""
        props = raw.get("properties", {})
        for key in ("title", "Name", "Title"):
            if key in props:
                rich = props[key].get("title", [])
                title = "".join(t.get("plain_text", "") for t in rich)
                break
        return SourceItem(
            user_id=user_id,
            source_type="notion",
            source_item_type="page",
            external_id=raw.get("id", ""),
            title=title or "(untitled)",
            body="",
            item_at=raw.get("last_edited_time"),
            metadata={"url": raw.get("url", "")},
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        token = credentials.get("access_token", "")
        if action_name == "search_pages":
            return await self._search_pages(token, params)
        if action_name == "create_page":
            return await self._create_page(token, params)
        if action_name == "append_block":
            return await self._append_block(token, params)
        return f"Unknown action: {action_name}"

    async def _search_pages(self, token: str, params: dict) -> str:
        query = params.get("query", "")
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.post(
                f"{NOTION_API}/search",
                json={"query": query, "page_size": 5},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        if not results:
            return f"No Notion pages found for '{query}'."
        lines = []
        for r in results:
            props = r.get("properties", {})
            title = ""
            for key in ("title", "Name", "Title"):
                if key in props:
                    rich = props[key].get("title", [])
                    title = "".join(t.get("plain_text", "") for t in rich)
                    break
            lines.append(f"- {title or '(untitled)'}: {r.get('url', '')}")
        return "Notion pages:\n" + "\n".join(lines)

    async def _create_page(self, token: str, params: dict) -> str:
        parent_id = params.get("parent_id", "")
        title = params.get("title", "New page")
        content = params.get("content", "")
        if not parent_id:
            return "Error: 'parent_id' is required (Notion page or database ID)"
        body: dict = {
            "parent": {"page_id": parent_id},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
        }
        if content:
            body["children"] = [
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": content}}]}}
            ]
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.post(f"{NOTION_API}/pages", json=body, timeout=10)
            resp.raise_for_status()
            page = resp.json()
        return f"✓ Notion page created: {page.get('url', '')}"

    async def _append_block(self, token: str, params: dict) -> str:
        page_id = params.get("page_id", "")
        content = params.get("content", "")
        if not page_id or not content:
            return "Error: 'page_id' and 'content' are required"
        block = {
            "children": [
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [{"text": {"content": content}}]}}
            ]
        }
        async with httpx.AsyncClient(headers=_notion_headers(token)) as client:
            resp = await client.patch(
                f"{NOTION_API}/blocks/{page_id}/children", json=block, timeout=10
            )
            resp.raise_for_status()
        return f"✓ Block appended to Notion page {page_id}"


def _notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
