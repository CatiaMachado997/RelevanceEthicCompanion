"""
Goals API Routes

User goals inform ESL about priorities and help AI provide relevant assistance.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, UTC

from utils.db import get_db
from utils.serialization import serialize_row, serialize_rows
from services.context_manager import ContextManager
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus
from utils.supabase_auth import get_current_user_id, get_current_read_user_id


def get_context_manager() -> ContextManager:
    """Get ContextManager instance"""
    return ContextManager()


def get_esl(
    context_manager: ContextManager = Depends(get_context_manager),
) -> EthicalSafeguardLayer:
    """Get ESL instance"""
    return EthicalSafeguardLayer(context_manager)


# Request/Response models
class CreateGoalRequest(BaseModel):
    """Request to create a goal"""

    title: str = Field(..., min_length=1, description="Goal title")
    description: Optional[str] = Field(None, description="Goal description")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1=highest)")
    target_date: Optional[str] = Field(
        None, description="Target completion date (ISO format)"
    )


class UpdateGoalRequest(BaseModel):
    """Request to update a goal"""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    target_date: Optional[str] = None


# Router
router = APIRouter(prefix="/api/goals", tags=["Goals"])


@router.post("/", response_model=dict, status_code=201)
async def create_goal(
    request: CreateGoalRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """
    Create a new goal

    Goals help ESL understand user priorities and enable AI to provide
    relevant, context-aware assistance.

    Args:
        request: Goal creation request
        user_id: Current user ID
        esl: ESL instance for action evaluation

    Returns:
        Created goal

    Example:
        POST /api/goals
        {
            "title": "Launch new product",
            "description": "Complete MVP by Q2",
            "priority": 1,
            "target_date": "2025-06-30T00:00:00Z"
        }
    """
    try:
        # ESL evaluation for goal creation
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="goal_creation",
            content=f"Creating goal: {request.title}",
            urgency=UrgencyLevel.LOW,
            metadata={"goal_title": request.title, "priority": request.priority},
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Goal creation blocked by ESL: {decision.reason}",
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO goals (user_id, title, description, status, priority, target_date, metadata)
                    VALUES (%s, %s, %s, 'active', %s, %s, %s)
                    RETURNING id, user_id, title, description, status, priority, target_date, created_at, completed_at, metadata  # noqa: E501
                    """,
                    (
                        str(user_id),
                        request.title,
                        request.description,
                        request.priority,
                        request.target_date,
                        "{}",
                    ),
                )
                new_goal = cur.fetchone()

        if new_goal:
            return {
                "status": "success",
                "message": "Goal created successfully",
                "data": serialize_row(new_goal),
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create goal")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating goal: {str(e)}")


@router.get("/", response_model=dict)
async def list_goals(
    user_id: str = Depends(get_current_read_user_id),
    status: Optional[str] = None,
    active_only: bool = True,
):
    """
    List user's goals

    Args:
        user_id: Current user ID
        status: Filter by status (active, completed, paused, archived)
        active_only: Only return active goals

    Returns:
        List of goals
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM goals WHERE user_id = %s"
                params = [str(user_id)]

                if status:
                    query += " AND status = %s"
                    params.append(status)
                elif active_only:
                    query += " AND status = 'active'"

                query += " ORDER BY priority"

                cur.execute(query, tuple(params))
                goals = cur.fetchall()

        return {"status": "success", "count": len(goals), "data": serialize_rows(goals)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching goals: {str(e)}")


@router.get("/{goal_id}", response_model=dict)
async def get_goal(goal_id: str, user_id: str = Depends(get_current_read_user_id)):
    """
    Get a specific goal by ID

    Args:
        goal_id: Goal ID
        user_id: Current user ID

    Returns:
        Goal data
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM goals WHERE id = %s AND user_id = %s",
                    (str(goal_id), str(user_id)),
                )
                goal = cur.fetchone()

        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        return {"status": "success", "data": serialize_row(goal)}

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Goal not found")
        raise HTTPException(status_code=500, detail=f"Error fetching goal: {str(e)}")


@router.put("/{goal_id}", response_model=dict)
async def update_goal(
    goal_id: str,
    request: UpdateGoalRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """
    Update a goal

    Args:
        goal_id: Goal ID
        request: Update request
        user_id: Current user ID
        esl: ESL instance for action evaluation

    Returns:
        Updated goal
    """
    try:
        # ESL evaluation for goal update
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="goal_update",
            content=f"Updating goal: {goal_id}",
            urgency=UrgencyLevel.LOW,
            metadata={
                "goal_id": goal_id,
                "updates": request.model_dump(exclude_none=True),
            },
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403, detail=f"Goal update blocked by ESL: {decision.reason}"
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                update_data = {}
                if request.title is not None:
                    update_data["title"] = request.title
                if request.description is not None:
                    update_data["description"] = request.description
                if request.status is not None:
                    update_data["status"] = request.status
                    if request.status == "completed":
                        update_data["completed_at"] = datetime.now(UTC).isoformat()
                if request.priority is not None:
                    update_data["priority"] = request.priority
                if request.target_date is not None:
                    update_data["target_date"] = request.target_date

                if not update_data:
                    raise HTTPException(status_code=400, detail="No fields to update")

                set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
                params = list(update_data.values())
                params.extend([str(goal_id), str(user_id)])

                cur.execute(
                    f"UPDATE goals SET {set_clause} WHERE id = %s AND user_id = %s RETURNING *",
                    tuple(params),
                )
                updated_goal = cur.fetchone()

        if not updated_goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        return {
            "status": "success",
            "message": "Goal updated successfully",
            "data": serialize_row(updated_goal),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating goal: {str(e)}")


@router.post("/{goal_id}/complete", response_model=dict)
async def complete_goal(
    goal_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
):
    """
    Mark a goal as completed

    Args:
        goal_id: Goal ID
        user_id: Current user ID
        esl: ESL instance for action evaluation

    Returns:
        Updated goal
    """
    try:
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="goal_completion",
            content=f"Completing goal: {goal_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"goal_id": goal_id},
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Goal completion blocked by ESL: {decision.reason}",
            )

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE goals SET status = 'completed', completed_at = %s WHERE id = %s AND user_id = %s RETURNING *",  # noqa: E501
                    (datetime.now(UTC).isoformat(), goal_id, user_id),
                )
                updated_goal = cur.fetchone()

        if not updated_goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        # Insert notification
        try:
            from routes.notifications import create_notification

            goal_title = updated_goal.get("title", goal_id)
            with get_db() as notif_conn:
                create_notification(
                    notif_conn,
                    user_id,
                    type="goal_completed",
                    title="Goal Completed",
                    message=f'You completed "{goal_title}"',
                )
        except Exception:
            pass  # Notification failure must never break goal completion

        return {
            "status": "success",
            "message": "Goal completed! 🎉",
            "data": serialize_row(updated_goal),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error completing goal: {str(e)}")


class ReorderGoalsRequest(BaseModel):
    goalIds: List[str]


@router.patch("/reorder", response_model=dict)
async def reorder_goals(
    request: ReorderGoalsRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Reorder goals by updating their priority based on provided order.

    Args:
        request: ReorderGoalsRequest with 'goalIds' list in desired order
        user_id: Current user ID

    Returns:
        Success message
    """
    goal_ids = request.goalIds
    if not goal_ids:
        raise HTTPException(status_code=400, detail="No goalIds provided")

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for index, goal_id in enumerate(goal_ids, start=1):
                    cur.execute(
                        "UPDATE goals SET priority = %s WHERE id = %s AND user_id = %s",
                        (index, str(goal_id), str(user_id)),
                    )

        return {"status": "success", "message": "Goals reordered successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reordering goals: {str(e)}")


@router.delete("/{goal_id}", response_model=dict)
async def delete_goal(goal_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete (archive) a goal

    Args:
        goal_id: Goal ID
        user_id: Current user ID

    Returns:
        Success message
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE goals SET status = 'archived' WHERE id = %s AND user_id = %s RETURNING *",
                    (str(goal_id), str(user_id)),
                )
                archived_goal = cur.fetchone()

        if not archived_goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        return {
            "status": "success",
            "message": "Goal archived successfully",
            "data": serialize_row(archived_goal),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting goal: {str(e)}")


# ==================== Milestones ====================


class MilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.get("/{goal_id}/milestones", response_model=dict)
async def list_milestones(
    goal_id: str,
    user_id: str = Depends(get_current_read_user_id),
):
    """List all milestones for a goal."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, goal_id, title, completed, created_at
                    FROM goal_milestones
                    WHERE goal_id = %s AND user_id = %s
                    ORDER BY created_at ASC
                    """,
                    (goal_id, str(user_id)),
                )
                rows = cur.fetchall()
        return {"milestones": [serialize_row(r) for r in rows]}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching milestones: {str(e)}"
        )


@router.post("/{goal_id}/milestones", response_model=dict)
async def create_milestone(
    goal_id: str,
    body: MilestoneCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a milestone for a goal."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO goal_milestones (goal_id, user_id, title)
                    VALUES (%s, %s, %s)
                    RETURNING id, goal_id, title, completed, created_at
                    """,
                    (goal_id, str(user_id), body.title),
                )
                row = cur.fetchone()
        return {"milestone": serialize_row(row)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating milestone: {str(e)}"
        )


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=dict)
async def toggle_milestone(
    goal_id: str,
    milestone_id: str,
    body: dict,
    user_id: str = Depends(get_current_user_id),
):
    """Toggle completion or rename a milestone."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                updates = []
                params = []
                if "completed" in body:
                    updates.append("completed = %s")
                    params.append(bool(body["completed"]))
                if "title" in body:
                    updates.append("title = %s")
                    params.append(str(body["title"])[:200])
                if not updates:
                    raise HTTPException(status_code=400, detail="Nothing to update")
                updates.append("updated_at = NOW()")
                params.extend([milestone_id, str(user_id)])
                cur.execute(
                    f"""
                    UPDATE goal_milestones SET {', '.join(updates)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, goal_id, title, completed, created_at
                    """,
                    params,
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Milestone not found")
        return {"milestone": serialize_row(row)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating milestone: {str(e)}"
        )


@router.delete("/{goal_id}/milestones/{milestone_id}", response_model=dict)
async def delete_milestone(
    goal_id: str,
    milestone_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a milestone."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM goal_milestones WHERE id = %s AND user_id = %s",
                    (milestone_id, str(user_id)),
                )
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting milestone: {str(e)}"
        )
