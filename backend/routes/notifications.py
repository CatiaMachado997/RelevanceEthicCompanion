"""Notifications API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from utils.db import get_db
from utils.serialization import serialize_rows, serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(
    context_manager: ContextManager = Depends(get_context_manager),
) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(context_manager)


def create_notification(
    conn, user_id: str, type: str, title: str, message: str, metadata: dict = None
):
    """Insert a notification row. Call inside an existing open DB connection."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_notifications (user_id, type, title, message, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(user_id), type, title, message, metadata or {}),
        )


@router.get("/", response_model=dict)
async def list_notifications(
    unread_only: bool = False,
    user_id: str = Depends(get_current_read_user_id),
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # True unread count (not capped)
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = %s AND read = FALSE",
                    (str(user_id),),
                )
                row = cur.fetchone()
                true_unread_count = row["cnt"] if row else 0

                # Paged list
                query = "SELECT * FROM user_notifications WHERE user_id = %s"
                params = [str(user_id)]
                if unread_only:
                    query += " AND read = FALSE"
                query += " ORDER BY created_at DESC LIMIT 50"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        notifications = serialize_rows(rows)
        return {
            "status": "success",
            "count": len(notifications),
            "unread_count": true_unread_count,
            "notifications": notifications,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching notifications: {str(e)}"
        )


@router.get("/count", response_model=dict)
async def get_unread_count(
    user_id: str = Depends(get_current_read_user_id),
):
    """Lightweight endpoint returning only the unread notification count."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_notifications WHERE user_id = %s AND read = FALSE",
                    (str(user_id),),
                )
                row = cur.fetchone()
        return {"unread_count": int(row["cnt"]) if row else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching count: {str(e)}")


@router.patch("/read-all", response_model=dict)
async def mark_all_read(
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    proposed = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="notification_read",
        content="Marking all notifications as read",
        urgency=UrgencyLevel.LOW,
        metadata={"user_id": str(user_id)},
    )
    decision = await esl.evaluate_action(proposed, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Action blocked by ESL: {decision.reason}"
        )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_notifications SET read = TRUE WHERE user_id = %s AND read = FALSE",
                    (str(user_id),),
                )
        return {"status": "success", "message": "All notifications marked as read"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating notifications: {str(e)}"
        )


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_one_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    proposed = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="notification_read",
        content=f"Marking notification {notification_id} as read",
        urgency=UrgencyLevel.LOW,
        metadata={"notification_id": notification_id},
    )
    decision = await esl.evaluate_action(proposed, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Action blocked by ESL: {decision.reason}"
        )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_notifications SET read = TRUE WHERE id = %s AND user_id = %s RETURNING *",
                    (str(notification_id), str(user_id)),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="Notification not found")

        return {"status": "success", "data": serialize_row(updated)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating notification: {str(e)}"
        )
