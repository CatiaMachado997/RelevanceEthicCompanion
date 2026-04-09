"""
Minimal auth routes for Supabase JWT identity introspection.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from jose import jwt as jose_jwt
from pydantic import BaseModel

from config import settings
from utils.auth_audit import log_auth_event
from utils.db import get_db_connection
from utils.rate_limit import limiter
from utils.supabase_auth import UserPrincipal, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SessionCreate(BaseModel):
    access_token: str
    remember_me: bool = False


def _provision_user(access_token: str) -> None:
    """Upsert the Supabase user into the local users table (idempotent)."""
    try:
        claims = jose_jwt.get_unverified_claims(access_token)
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
    return {
        "user_id": user.user_id,
        "email": user.email,
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
        event="session_exchanged",
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
