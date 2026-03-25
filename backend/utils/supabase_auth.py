"""
Supabase JWT authentication helpers.

Phase 1 behavior:
- In strict mode, missing/invalid tokens return 401.
- In local dev with auth enforcement disabled, falls back to a mock user.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Any, Dict, Optional
from urllib import request as urlrequest

from fastapi import HTTPException, Request, status
from jose import jwt

from config import settings

logger = logging.getLogger(__name__)

MOCK_USER_ID = settings.DEV_USER_ID
_JWKS_CACHE: Dict[str, Any] = {"expires_at": None, "keys": []}
_JWKS_CACHE_TTL = timedelta(minutes=10)


@dataclass
class UserPrincipal:
    user_id: str
    email: Optional[str]
    claims: Dict[str, Any]


def _auth_error(message: str, code: str = "not_authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
    )


def _is_dev_fallback_enabled() -> bool:
    return (
        settings.ENVIRONMENT == "development"
        and not settings.AUTH_ENFORCEMENT_ENABLED
        and settings.AUTH_ENFORCE_WRITE_ROUTES
    )


def _build_issuer() -> str:
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    if not supabase_url:
        raise ValueError("SUPABASE_URL must be configured for strict auth enforcement")
    return f"{supabase_url}/auth/v1"


def _fetch_jwks() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    if _JWKS_CACHE["expires_at"] and _JWKS_CACHE["expires_at"] > now and _JWKS_CACHE["keys"]:
        return {"keys": _JWKS_CACHE["keys"]}

    issuer = _build_issuer()
    jwks_url = f"{issuer}/.well-known/jwks.json"
    with urlrequest.urlopen(jwks_url, timeout=5) as response:
        payload = response.read().decode("utf-8")
        parsed = json.loads(payload)

    keys = parsed.get("keys", [])
    if not keys:
        raise ValueError("No JWKS keys returned by Supabase")

    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["expires_at"] = now + _JWKS_CACHE_TTL
    return {"keys": keys}


def _decode_supabase_token(token: str) -> Dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    jwks = _fetch_jwks()
    key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
    if not key:
        raise ValueError("No matching JWKS key found")

    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=_build_issuer(),
    )
    return claims


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise _auth_error("Missing Authorization header")

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _auth_error("Authorization header must use Bearer scheme", code="invalid_token")

    token = parts[1].strip()
    if not token:
        raise _auth_error("Bearer token is empty", code="invalid_token")
    return token


async def get_current_user(request: Request) -> UserPrincipal:
    if _is_dev_fallback_enabled():
        logger.warning("Auth enforcement disabled in development, using mock user fallback")
        return UserPrincipal(user_id=MOCK_USER_ID, email=None, claims={"sub": MOCK_USER_ID})

    try:
        token = _extract_bearer_token(request)
        claims = _decode_supabase_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise _auth_error("Invalid or expired token", code="invalid_token")

    user_id = claims.get("sub")
    if not user_id:
        raise _auth_error("Token missing subject claim", code="invalid_token")

    return UserPrincipal(
        user_id=str(user_id),
        email=claims.get("email"),
        claims=claims,
    )


async def get_current_user_id(request: Request) -> str:
    principal = await get_current_user(request)
    return principal.user_id


def _read_routes_enforced() -> bool:
    return settings.AUTH_ENFORCEMENT_ENABLED and settings.AUTH_ENFORCE_READ_ROUTES


async def get_current_read_user_id(request: Request) -> str:
    if not _read_routes_enforced():
        logger.warning("Read route auth enforcement disabled, using mock user fallback")
        return MOCK_USER_ID
    principal = await get_current_user(request)
    return principal.user_id
