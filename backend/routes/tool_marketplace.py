"""Tool Marketplace API routes."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import AnyHttpUrl, BaseModel
from urllib.parse import quote

from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from esl.tool_gate import ESLToolGate
from config import settings
from services.composio_tools import TOOL_ID_TO_COMPOSIO_TOOLKIT
from services import composio_sync

try:
    from composio import Composio
    from composio_langchain import LangchainProvider
except ImportError:  # composio not installed in this environment
    Composio = None  # type: ignore[assignment,misc]
    LangchainProvider = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tool-marketplace"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class PermissionRequest(BaseModel):
    action_name: str
    trust_level: str  # 'ask' | 'allow' | 'deny'


class MCPConnectRequest(BaseModel):
    mcp_url: AnyHttpUrl
    name: Optional[str] = "Custom MCP"


class ConnectRequest(BaseModel):
    api_key: Optional[str] = None  # for auth_type='apikey' tools


class ComposioConnectRequest(BaseModel):
    toolkit: str  # our tool_id: "github" | "notion" | "slack" | "gmail_write" | "google_calendar_write"


# ─── Catalogue ────────────────────────────────────────────────────────────────


@router.get("")
async def get_catalogue(
    user_id: str = Depends(get_current_read_user_id),
) -> list:
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
) -> list:
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


# ─── Composio connect flow ────────────────────────────────────────────────────
# NOTE: These routes must be registered BEFORE /{tool_id}/connect and
# /{tool_id}/oauth/callback so that FastAPI's path matching prefers the
# exact literal paths over the parameterised ones.


@router.post("/composio/connect")
async def composio_connect(
    body: ComposioConnectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Initiate Composio OAuth for a catalogue tool.

    Returns a Composio-hosted OAuth URL. Frontend redirects the user there.
    Composio handles token exchange and redirects to /api/tools/composio/callback.
    """
    if not settings.COMPOSIO_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Composio integration not configured. Set COMPOSIO_API_KEY in .env.",
        )

    composio_toolkit_slug = TOOL_ID_TO_COMPOSIO_TOOLKIT.get(body.toolkit)
    if not composio_toolkit_slug:
        raise HTTPException(status_code=404, detail=f"Unknown toolkit: {body.toolkit}")

    state = _build_oauth_state(user_id=user_id, tool_id=f"composio_{body.toolkit}")
    callback_url = (
        f"{settings.BACKEND_URL}/api/tools/composio/callback"
        f"?toolkit={quote(body.toolkit, safe='')}&state={quote(state, safe='')}"
    )

    try:
        client = Composio(
            provider=LangchainProvider(), api_key=settings.COMPOSIO_API_KEY
        )
        session = client.create(user_id=user_id, manage_connections=False)
        req = session.authorize(composio_toolkit_slug, callback_url=callback_url)
        return {"connect_url": req.redirect_url}
    except Exception as exc:
        logger.error(
            f"Composio connect failed for {body.toolkit}: {exc}", exc_info=True
        )
        raise HTTPException(status_code=502, detail=f"Composio error: {exc}")


@router.get("/composio/callback")
async def composio_callback(
    toolkit: Optional[str] = None,
    state: Optional[str] = None,
    status: Optional[str] = None,
    connected_account_id: Optional[str] = None,
    # Composio sometimes uses these alternate param names
    connectedAccountId: Optional[str] = None,
    error: Optional[str] = None,
) -> Response:
    """Receive redirect from Composio after user completes OAuth.

    On success: record connection in user_tool_connections, redirect to frontend.
    On failure: redirect to frontend with error param.

    Composio may send status='success' | 'connected' | None (when error param present).
    We treat any non-error response with a connected_account_id as success.
    """
    account_id = connected_account_id or connectedAccountId or ""
    tool_key = toolkit or "unknown"

    # Treat as failure only when there's an explicit error or no account established
    is_success = (
        status in ("success", "connected", "active")
        or (account_id and not error)
    )

    if not is_success or error:
        logger.warning(
            "Composio callback non-success: toolkit=%s status=%s error=%s",
            tool_key, status, error,
        )
        _err = f"{tool_key}_composio_failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )
    try:
        user_id = _extract_user_from_state(state, f"composio_{tool_key}")
        credentials = json.dumps({"composio_account_id": account_id})
        _store_connection(user_id=user_id, tool_id=tool_key, credentials=credentials)
        logger.info("Composio connected: toolkit=%s user=%s account=%s", tool_key, user_id, account_id)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={quote(tool_key, safe='')}",
            status_code=302,
        )
    except Exception as exc:
        logger.error(f"Composio callback failed for {tool_key}: {exc}", exc_info=True)
        _err = f"{tool_key}_composio_failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )


# ─── Connect (initiate OAuth or save API key) ─────────────────────────────────


@router.post("/{tool_id}/connect")
async def connect_tool(
    tool_id: str,
    body: ConnectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Initiate connect for a catalogue tool.

    - OAuth tools: returns authorization URL (caller redirects user)
    - API-key tools: saves key and returns success
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT auth_type FROM tool_definitions WHERE id = %s AND enabled = TRUE",
                (tool_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    auth_type = row["auth_type"]
    if auth_type == "apikey":
        if not body.api_key:
            raise HTTPException(
                status_code=422, detail="api_key required for this tool"
            )
        credentials = _encrypt_credentials({"api_key": body.api_key})
        _store_connection(user_id=user_id, tool_id=tool_id, credentials=credentials)
        return {"success": True}
    elif auth_type in ("oauth", "mcp"):
        # For OAuth, return the authorization URL; frontend handles redirect
        connector = _get_connector(tool_id)
        state = _build_oauth_state(user_id=user_id, tool_id=tool_id)
        auth_url = connector.get_authorization_url(user_id=user_id, state=state)
        return {"auth_url": auth_url}
    raise HTTPException(status_code=500, detail=f"Unsupported auth_type: {auth_type}")


# ─── OAuth connect flow ───────────────────────────────────────────────────────


@router.get("/{tool_id}/oauth/callback")
async def oauth_callback(
    tool_id: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
) -> Response:
    """Handle OAuth callback — exchange code and store tokens."""
    if error or not code:
        _err = f"{tool_id}_{error or 'denied'}"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )
    try:
        connector = _get_connector(tool_id)
        user_id = _extract_user_from_state(state, tool_id)
        tokens = connector.exchange_code_for_tokens(code)
        credentials = _encrypt_credentials(tokens)
        _store_connection(user_id=user_id, tool_id=tool_id, credentials=credentials)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?connected={quote(tool_id, safe='')}",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"OAuth callback failed for {tool_id}: {e}", exc_info=True)
        _err = f"{tool_id}_failed"
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/integrations?error={quote(_err, safe='')}",
            status_code=302,
        )


# ─── Sync ────────────────────────────────────────────────────────────────────


@router.post("/{tool_id}/sync")
async def sync_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Fetch recent data from a connected integration and store it in source_items.

    Returns the number of new items synced. Requires COMPOSIO_API_KEY to be set
    and the tool to already be connected by the user.
    """
    if not settings.COMPOSIO_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Composio integration not configured. Set COMPOSIO_API_KEY in .env.",
        )

    # Verify the tool is actually connected for this user
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM user_tool_connections WHERE user_id = %s AND tool_id = %s AND enabled = TRUE",
                (user_id, tool_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=404, detail=f"Tool not connected: {tool_id}"
        )

    count = await composio_sync.sync_tool_data(user_id=user_id, tool_id=tool_id)
    return {"synced": count, "tool_id": tool_id}


# ─── Disconnect ───────────────────────────────────────────────────────────────


@router.delete("/{tool_id}/disconnect")
async def disconnect_tool(
    tool_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Remove a tool connection and its permissions."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_tool_connections WHERE user_id = %s AND tool_id = %s",
                (user_id, tool_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"Tool connection not found: {tool_id}"
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
) -> dict:
    """Set trust level for a specific action on a tool."""
    if body.trust_level not in ("ask", "allow", "deny"):
        raise HTTPException(
            status_code=422, detail="trust_level must be ask|allow|deny"
        )
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
) -> dict:
    """Revoke stored trust for a specific action (resets to 'ask')."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tool_permissions WHERE user_id=%s AND tool_id=%s AND action_name=%s",
                (user_id, tool_id, action_name),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"Permission not found: {action_name}"
                )
    return {"success": True}


# ─── MCP ─────────────────────────────────────────────────────────────────────


@router.post("/mcp")
async def connect_mcp(
    body: MCPConnectRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Register an MCP server URL as a custom tool connection."""
    _store_connection(
        user_id=user_id,
        tool_id="mcp_custom",
        credentials={},
        mcp_url=str(body.mcp_url),
    )
    return {"success": True, "mcp_url": str(body.mcp_url)}


@router.delete("/mcp/{connection_id}")
async def disconnect_mcp(
    connection_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Remove an MCP server connection by its UUID."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_tool_connections WHERE id = %s AND user_id = %s",
                (connection_id, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(
                    status_code=404, detail=f"MCP connection not found: {connection_id}"
                )
    return {"success": True}


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials with Fernet before storage."""
    from utils.encryption import encrypt_credentials

    return encrypt_credentials(credentials)


def _store_connection(
    user_id: str,
    tool_id: str,
    credentials: Any,
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


def _build_oauth_state(user_id: str, tool_id: str) -> str:
    """Generate a signed OAuth state parameter."""
    from utils.oauth_state import create_signed_state

    return create_signed_state(user_id=user_id, source_type=f"tool_{tool_id}")


def _extract_user_from_state(state: Optional[str], tool_id: str) -> str:
    """Extract and verify user_id from signed OAuth state parameter."""
    if not state:
        raise ValueError("Missing OAuth state")
    from utils.oauth_state import validate_signed_state

    return validate_signed_state(state=state, expected_source_type=f"tool_{tool_id}")


def _get_connector(tool_id: str):
    """Return the connector instance for a catalogue tool."""
    if tool_id == "google_calendar_write":
        from services.connectors.google_calendar import GoogleCalendarConnector

        return GoogleCalendarConnector(redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI)
    if tool_id == "gmail_write":
        from services.connectors.gmail import GmailConnector

        return GmailConnector(redirect_uri=settings.GMAIL_OAUTH_REDIRECT_URI)
    logger.warning(f"_get_connector: unknown tool_id '{tool_id}'")
    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_id}")
