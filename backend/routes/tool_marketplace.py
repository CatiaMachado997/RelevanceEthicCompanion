"""Tool Marketplace API routes."""
from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.tool_gate import ESLToolGate
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tool-marketplace"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PermissionRequest(BaseModel):
    action_name: str
    trust_level: str  # 'ask' | 'allow' | 'deny'


class MCPConnectRequest(BaseModel):
    mcp_url: str
    name: Optional[str] = "Custom MCP"


# ─── Catalogue ────────────────────────────────────────────────────────────────

@router.get("")
async def get_catalogue(
    user_id: str = Depends(get_current_read_user_id),
):
    """Return all enabled tool definitions (the marketplace catalogue)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, auth_type, actions, icon_url, enabled "
                "FROM tool_definitions WHERE enabled = TRUE ORDER BY name"
            )
            rows = cur.fetchall()
    return rows


@router.get("/connected")
async def get_connected_tools(
    user_id: str = Depends(get_current_read_user_id),
):
    """Return tools the user has connected with their status."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT utc.tool_id, utc.enabled, utc.connected_at, utc.last_used_at, utc.mcp_url,
                       td.name, td.description, td.auth_type, td.actions, td.icon_url
                FROM user_tool_connections utc
                JOIN tool_definitions td ON td.id = utc.tool_id
                WHERE utc.user_id = %s
                ORDER BY utc.connected_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return rows


# ─── OAuth connect flow ───────────────────────────────────────────────────────

@router.get("/oauth/{tool_id}/authorize")
async def authorize_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Generate OAuth authorization URL for a catalogue tool."""
    connector = _get_connector(tool_id)
    auth_url = connector.get_authorization_url(user_id=user_id)
    return {"auth_url": auth_url}


@router.get("/oauth/{tool_id}/callback")
async def oauth_callback(
    tool_id: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Handle OAuth callback — exchange code and store tokens."""
    if error or not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={tool_id}_{error or 'denied'}",
            status_code=302,
        )
    try:
        connector = _get_connector(tool_id)
        # Extract user_id from state param (connector-specific or decode from state)
        user_id = _extract_user_from_state(state)
        tokens = connector.exchange_code_for_tokens(code)
        _store_connection(user_id=user_id, tool_id=tool_id, credentials=tokens)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={tool_id}",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"OAuth callback failed for {tool_id}: {e}", exc_info=True)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={tool_id}_failed",
            status_code=302,
        )


# ─── Disconnect ───────────────────────────────────────────────────────────────

@router.delete("/{tool_id}")
async def disconnect_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Remove a tool connection and its permissions."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_tool_connections WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id),
            )
            cur.execute(
                "DELETE FROM tool_permissions WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id),
            )
    return {"success": True}


# ─── Permissions (trust management) ──────────────────────────────────────────

@router.post("/{tool_id}/permissions")
async def set_permission(
    tool_id: str,
    body: PermissionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Set trust level for a specific action on a tool."""
    if body.trust_level not in ("ask", "allow", "deny"):
        raise HTTPException(status_code=422, detail="trust_level must be ask|allow|deny")
    gate = ESLToolGate()
    await gate.set_trust(
        user_id=user_id,
        tool_id=tool_id,
        action_name=body.action_name,
        trust_level=body.trust_level,
    )
    return {"success": True}


@router.delete("/{tool_id}/permissions/{action_name}")
async def revoke_permission(
    tool_id: str,
    action_name: str,
    user_id: str = Depends(get_current_user_id),
):
    """Revoke stored trust for a specific action (resets to 'ask')."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tool_permissions WHERE user_id=%s AND tool_id=%s AND action_name=%s",
                (user_id, tool_id, action_name),
            )
    return {"success": True}


# ─── MCP ─────────────────────────────────────────────────────────────────────

@router.post("/mcp")
async def connect_mcp(
    body: MCPConnectRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Register an MCP server URL as a custom tool connection."""
    _store_connection(
        user_id=user_id,
        tool_id="mcp_custom",
        credentials={},
        mcp_url=body.mcp_url,
    )
    return {"success": True, "mcp_url": body.mcp_url}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _store_connection(
    user_id: str,
    tool_id: str,
    credentials: dict,
    mcp_url: str | None = None,
) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_tool_connections (user_id, tool_id, enabled, credentials, mcp_url)
                VALUES (%s, %s, TRUE, %s, %s)
                ON CONFLICT (user_id, tool_id)
                DO UPDATE SET enabled=TRUE, credentials=EXCLUDED.credentials,
                              mcp_url=EXCLUDED.mcp_url
                """,
                (user_id, tool_id, credentials, mcp_url),
            )


def _extract_user_from_state(state: Optional[str]) -> str:
    """Extract user_id from OAuth state parameter.

    Uses utils.oauth_state.validate_signed_state if available,
    otherwise falls back to treating state directly as user_id
    (for development/testing).
    """
    if not state:
        raise ValueError("Missing OAuth state")
    try:
        from utils.oauth_state import validate_signed_state
        return validate_signed_state(state=state, expected_source_type="tool_oauth")
    except ImportError:
        # oauth_state utility not yet implemented — state is user_id directly
        return state


def _get_connector(tool_id: str):
    """Return the connector instance for a catalogue tool."""
    if tool_id == "notion":
        from services.connectors.notion import NotionConnector
        return NotionConnector()
    if tool_id == "github":
        from services.connectors.github import GitHubConnector
        return GitHubConnector()
    if tool_id == "slack":
        from services.connectors.slack_write import SlackWriteConnector
        return SlackWriteConnector()
    if tool_id == "google_calendar_write":
        from services.connectors.google_calendar import GoogleCalendarConnector
        return GoogleCalendarConnector()
    if tool_id == "gmail_write":
        from services.connectors.gmail import GmailConnector
        return GmailConnector()
    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_id}")
