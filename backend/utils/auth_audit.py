"""
Auth Audit Logger

Records authentication events to auth_audit_log.
All writes are fire-and-forget (background thread) — never blocks the request path.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from utils.db import get_db_connection

logger = logging.getLogger(__name__)


def _write_audit_event(
    event: str,
    user_id: Optional[str],
    ip_address: Optional[str],
    user_agent: Optional[str],
    detail: Optional[Any],
) -> None:
    """Write one row to auth_audit_log. Called in a background thread."""
    try:
        detail_json = json.dumps(detail) if detail is not None else None
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO auth_audit_log (user_id, event, ip_address, user_agent, detail)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (user_id, event, ip_address, user_agent, detail_json),
                )
    except Exception as exc:
        logger.warning("auth_audit: failed to write event '%s': %s", event, exc)


def log_auth_event(
    event: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[Any] = None,
) -> None:
    """
    Log an auth event asynchronously. Returns immediately.

    event: one of login_success | logout | token_invalid | token_expired |
               rate_limited | session_exchanged
    """
    t = threading.Thread(
        target=_write_audit_event,
        kwargs={
            "event": event,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "detail": detail,
        },
        daemon=True,
    )
    t.start()
