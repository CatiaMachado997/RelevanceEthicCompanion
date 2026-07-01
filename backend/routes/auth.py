"""
Minimal auth routes for Supabase JWT identity introspection.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from config import settings
from utils.auth_audit import log_auth_event
from utils.db import get_db_connection
from utils.rate_limit import limiter
from utils.supabase_auth import UserPrincipal, _decode_supabase_token, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SessionCreate(BaseModel):
    access_token: str
    remember_me: bool = False


def _provision_user(access_token: str) -> None:
    """Upsert the Supabase user into the local users table (idempotent).

    Uses verified JWT claims to prevent unauthenticated user-row injection.
    If token verification fails for any reason, provisioning is skipped
    but login continues unblocked.
    """
    try:
        claims = _decode_supabase_token(access_token)
        user_id = claims.get("sub")
        email = claims.get("email", "")
        if not user_id:
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, email)
                    VALUES (%s, %s)
                    ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                    """,
                    (user_id, email),
                )
    except Exception as exc:
        logger.warning("User provisioning failed: %s", exc)
        # Do not block login if provisioning fails — log and continue


@router.get("/me", response_model=dict)
@limiter.limit("30/minute")
async def get_me(request: Request, user: UserPrincipal = Depends(get_current_user)):
    # Include onboarded_at so the frontend can route first-time users into the
    # wizard on first paint without waiting for a separate /api/onboarding/state
    # roundtrip. Best-effort: a missing row (test fixtures, mock auth) is fine.
    onboarded_at = None
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT onboarded_at FROM users WHERE id = %s",
                    (user.user_id,),
                )
                row = cur.fetchone() or {}
                ts = row.get("onboarded_at")
                onboarded_at = ts.isoformat() if ts else None
    except Exception as exc:
        logger.warning("Failed to load onboarded_at for /me: %s", exc)

    return {
        "user_id": user.user_id,
        "email": user.email,
        "onboarded_at": onboarded_at,
    }


@router.post("/session")
@limiter.limit("10/minute")
async def create_session(request: Request, body: SessionCreate, response: Response):
    """Exchange Supabase token for an HttpOnly cookie session."""
    # Auto-provision the user in the local DB on first login (idempotent).
    # This resolves FK violations when a real Supabase user_id is not yet
    # present in the local users table.
    _provision_user(body.access_token)

    max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
    response.set_cookie(
        key="ec_session",
        value=body.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=max_age,
    )
    log_auth_event(
        event="login_success",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}


@router.delete("/session")
@limiter.limit("30/minute")
async def delete_session(request: Request, response: Response):
    """Clear the session cookie on sign-out."""
    response.delete_cookie("ec_session")
    log_auth_event(
        event="logout",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"ok": True}
