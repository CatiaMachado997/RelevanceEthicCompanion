"""GitHub connector — OAuth + read/write actions."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from services.connectors.base import BaseConnector, SourceItem
from config import settings

logger = logging.getLogger(__name__)

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


class GitHubConnector(BaseConnector):
    source_type = "github"

    def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> str:
        params = urlencode({
            "client_id": settings.GITHUB_CLIENT_ID,
            "scope": "repo,read:user",
            "state": state or "",
        })
        return f"{GITHUB_AUTH_URL}?{params}"

    # NOTE: blocking call — callers should use asyncio.to_thread
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        resp = httpx.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_at": None,
        }

    async def fetch_raw_items(
        self, access_token: str, refresh_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch assigned open issues."""
        async with httpx.AsyncClient(headers=_gh_headers(access_token)) as client:
            resp = await client.get(
                f"{GITHUB_API}/issues",
                params={"filter": "assigned", "state": "open", "per_page": 30},
                timeout=10,
            )
            try:
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"fetch_raw_items failed: {e.response.status_code}")
                return []

    def normalize_to_source_item(self, raw: Dict[str, Any], user_id: str) -> SourceItem:
        return SourceItem(
            user_id=user_id,
            source_type="github",
            source_item_type="issue",
            external_id=str(raw.get("id", "")),
            title=raw.get("title", ""),
            body=raw.get("body", ""),
            item_at=raw.get("created_at"),
            metadata={
                "url": raw.get("html_url", ""),
                "repo": raw.get("repository_url", "").split("/")[-1],
                "number": raw.get("number"),
                "state": raw.get("state", "open"),
            },
        )

    async def execute_action(
        self, action_name: str, params: dict, credentials: dict
    ) -> str:
        token = credentials.get("access_token", "")
        if not token:
            return "Error: no access token — reconnect this tool in Settings → Integrations"
        if action_name == "list_issues":
            return await self._list_issues(token, params)
        if action_name == "create_issue":
            return await self._create_issue(token, params)
        if action_name == "add_comment":
            return await self._add_comment(token, params)
        return f"Unknown action: {action_name}"

    async def _list_issues(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        if not repo:
            return "Error: 'repo' parameter required (e.g. 'owner/repo')"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/issues",
                params={"state": "open", "per_page": 10},
                timeout=10,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return f"GitHub API error {e.response.status_code}: {e.response.text[:200]}"
            issues = resp.json()
        if not issues:
            return f"No open issues in {repo}."
        lines = [f"#{i['number']}: {i['title']} ({i['html_url']})" for i in issues]
        return f"Open issues in {repo}:\n" + "\n".join(lines)

    async def _create_issue(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        title = params.get("title", "")
        body = params.get("body", "")
        labels = params.get("labels", [])
        if not repo or not title:
            return "Error: 'repo' and 'title' parameters required"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo}/issues",
                json={"title": title, "body": body, "labels": labels},
                timeout=10,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return f"GitHub API error {e.response.status_code}: {e.response.text[:200]}"
            issue = resp.json()
        return f"✓ Issue #{issue['number']} created: {issue['html_url']}"

    async def _add_comment(self, token: str, params: dict) -> str:
        repo = params.get("repo", "")
        issue_number = params.get("issue_number")
        comment = params.get("comment", "")
        if not repo or not issue_number or not comment:
            return "Error: 'repo', 'issue_number', and 'comment' are required"
        async with httpx.AsyncClient(headers=_gh_headers(token)) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{issue_number}/comments",
                json={"body": comment},
                timeout=10,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return f"GitHub API error {e.response.status_code}: {e.response.text[:200]}"
        return f"✓ Comment added to issue #{issue_number}"


def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
