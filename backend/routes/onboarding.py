"""Sprint H Task 1 — first-run onboarding state.

The wizard at `/onboarding` walks the user through three small steps
(connect a source → declare values → seed a goal). The frontend needs two
things from this router:

  * `GET  /api/onboarding/state` — am I onboarded yet, and which steps still
    need doing? The three has_* flags are derived live from the underlying
    tables so we don't have to keep a separate state machine in sync.
  * `POST /api/onboarding/complete` — mark onboarding done (idempotent). The
    user hits this when they finish step 3 *or* when they explicitly skip
    the wizard from the intro screen.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/state")
async def get_state(
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Return the onboarded_at timestamp + per-step completion flags.

    The flags use EXISTS rather than COUNT to short-circuit on the first
    matching row — the only thing we need to know is "is there at least one
    of these for this user."
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT onboarded_at FROM users WHERE id = %s)               AS onboarded_at,
                    EXISTS (
                        SELECT 1 FROM data_sources
                        WHERE user_id = %s AND oauth_token_encrypted IS NOT NULL
                    )                                                             AS has_data_source,
                    EXISTS (
                        SELECT 1 FROM user_values
                        WHERE user_id = %s AND active = TRUE
                    )                                                             AS has_value,
                    EXISTS (
                        SELECT 1 FROM goals
                        WHERE user_id = %s
                    )                                                             AS has_goal
                """,
                (user_id, user_id, user_id, user_id),
            )
            row = cur.fetchone() or {}

    onboarded_at = row.get("onboarded_at")
    return {
        "onboarded_at": onboarded_at.isoformat() if onboarded_at else None,
        "has_data_source": bool(row.get("has_data_source")),
        "has_value": bool(row.get("has_value")),
        "has_goal": bool(row.get("has_goal")),
    }


@router.post("/complete")
async def complete(
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Set onboarded_at to NOW() if it isn't already set. Idempotent.

    Returns the resolved timestamp so the frontend can update its cache
    without a follow-up GET.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                   SET onboarded_at = COALESCE(onboarded_at, NOW())
                 WHERE id = %s
             RETURNING onboarded_at
                """,
                (user_id,),
            )
            row = cur.fetchone() or {}
        conn.commit()

    onboarded_at = row.get("onboarded_at")
    return {
        "onboarded_at": onboarded_at.isoformat() if onboarded_at else None,
    }
