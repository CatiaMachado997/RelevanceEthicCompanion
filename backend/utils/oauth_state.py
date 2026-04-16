"""
Signed OAuth state helpers.

Used to bind OAuth callbacks to a specific authenticated user without
trusting raw user identifiers from query params.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Dict

from fastapi import HTTPException, status

from config import settings

_MAX_AGE_SECONDS = 600  # 10 minutes
_PENDING_NONCES: Dict[str, datetime] = {}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def _state_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "invalid_oauth_state", "message": message},
    )


def _sign(payload_b64: str) -> str:
    return _b64url_encode(
        hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )


def _cleanup_nonces(now: datetime) -> None:
    expired = [
        nonce for nonce, expires_at in _PENDING_NONCES.items() if expires_at <= now
    ]
    for nonce in expired:
        _PENDING_NONCES.pop(nonce, None)


def create_signed_state(user_id: str, source_type: str) -> str:
    now = datetime.now(timezone.utc)
    nonce = secrets.token_urlsafe(16)
    exp = int((now + timedelta(seconds=_MAX_AGE_SECONDS)).timestamp())
    _PENDING_NONCES[nonce] = now + timedelta(seconds=_MAX_AGE_SECONDS)
    _cleanup_nonces(now)

    payload = {
        "uid": user_id,
        "src": source_type,
        "nonce": nonce,
        "exp": exp,
    }
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def validate_signed_state(state: str, expected_source_type: str) -> str:
    try:
        payload_b64, signature = state.split(".", 1)
    except ValueError as exc:
        raise _state_error("Malformed state token") from exc

    expected_signature = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected_signature):
        raise _state_error("Invalid state signature")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise _state_error("Invalid state payload") from exc

    now = datetime.now(timezone.utc)
    _cleanup_nonces(now)

    exp = payload.get("exp")
    if not isinstance(exp, int) or now.timestamp() > exp:
        raise _state_error("State token expired")

    if payload.get("src") != expected_source_type:
        raise _state_error("State source mismatch")

    nonce = payload.get("nonce")
    if not nonce or nonce not in _PENDING_NONCES:
        raise _state_error("Invalid or replayed state nonce")

    _PENDING_NONCES.pop(nonce, None)

    user_id = payload.get("uid")
    if not user_id:
        raise _state_error("State is missing user identifier")

    return str(user_id)
