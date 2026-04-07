"""
User Values API Routes

CRITICAL: These endpoints allow users to set their boundaries.
User values are SACRED - they define what ESL protects.

Philosophy: User empowerment first. No hidden defaults, no dark patterns.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Optional
from pydantic import BaseModel, Field

from services.context_manager import ContextManager
from esl.models import UserValue, ValueType, ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus
from esl.engine import EthicalSafeguardLayer
from utils.db import get_db
from utils.serialization import serialize_row, serialize_rows
from utils.supabase_auth import get_current_user_id, get_current_read_user_id


# Request/Response models
class CreateValueRequest(BaseModel):
    """Request to create a user value/boundary"""
    type: ValueType
    value: str = Field(..., description="The value/boundary content (e.g., 'no_work_after_19h')")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1=highest, 10=lowest)")
    metadata: Optional[dict] = Field(default_factory=dict)


class UpdateValueRequest(BaseModel):
    """Request to update a user value"""
    value: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    active: Optional[bool] = None
    metadata: Optional[dict] = None


class ValueResponse(BaseModel):
    """Response model for a user value"""
    id: str
    user_id: str
    type: str
    value: str
    priority: int
    active: bool
    metadata: dict
    created_at: str
    updated_at: str


# Router
router = APIRouter(prefix="/api/values", tags=["User Values"])

# Dependencies
def get_context_manager() -> ContextManager:
    """Get ContextManager instance"""
    return ContextManager()


def get_esl(context_manager: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    """Get ESL instance"""
    return EthicalSafeguardLayer(context_manager)


@router.post("/", response_model=dict, status_code=201)
async def create_value(
    request: CreateValueRequest,
    user_id: str = Depends(get_current_user_id),
    context_manager: ContextManager = Depends(get_context_manager),
    esl: EthicalSafeguardLayer = Depends(get_esl)
):
    """
    Create a new user value/boundary

    This is a CRITICAL endpoint - it defines what ESL protects.

    Example boundaries:
    - "no_work_after_19h" (time-based)
    - "no_politics_topics" (content filter)
    - "focus_mode_9am_11am" (deep work protection)

    Args:
        request: Value creation request
        user_id: Current user ID (from auth)
        context_manager: Context manager dependency
        esl: ESL instance for action evaluation

    Returns:
        Created value with ID
    """
    try:
        # ESL evaluation for value/boundary creation
        # Note: Creating boundaries is generally safe, but we still log it
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="value_creation",
            content=f"Creating {request.type.value}: {request.value}",
            urgency=UrgencyLevel.LOW,
            metadata={"value_type": request.type.value, "value": request.value}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Value creation blocked by ESL: {decision.reason}"
            )

        import json
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_values (user_id, type, value, priority, active, metadata)
                    VALUES (%s, %s, %s, %s, TRUE, %s)
                    RETURNING id, user_id, type, value, priority, active, metadata, created_at, updated_at
                    """,
                    (
                        str(user_id),
                        request.type.value,
                        request.value,
                        request.priority,
                        json.dumps(request.metadata),
                    ),
                )
                new_value = cur.fetchone()

        if new_value:
            return {
                "status": "success",
                "message": "Value created successfully",
                "data": serialize_row(new_value)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create value")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating value: {str(e)}")


@router.get("/", response_model=dict)
async def list_values(
    user_id: str = Depends(get_current_read_user_id),
    active_only: bool = True,
    value_type: Optional[str] = None
):
    """
    List user's values/boundaries
    
    Args:
        user_id: Current user ID
        active_only: Only return active values
        value_type: Filter by type (boundary, preference, etc.)
    
    Returns:
        List of user values
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM user_values WHERE user_id = %s"
                params = [str(user_id)]

                if active_only:
                    query += " AND active = TRUE"
                
                if value_type:
                    query += " AND type = %s"
                    params.append(value_type)

                query += " ORDER BY priority ASC, created_at ASC"
                
                cur.execute(query, tuple(params))
                values = cur.fetchall()

        return {
            "status": "success",
            "count": len(values),
            "data": serialize_rows(values)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching values: {str(e)}")


@router.get("/{value_id}", response_model=dict)
async def get_value(
    value_id: str,
    user_id: str = Depends(get_current_read_user_id)
):
    """
    Get a specific user value by ID
    
    Args:
        value_id: Value ID
        user_id: Current user ID
    
    Returns:
        User value
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM user_values WHERE id = %s AND user_id = %s",
                    (str(value_id), str(user_id)),
                )
                value = cur.fetchone()

        if not value:
            raise HTTPException(status_code=404, detail="Value not found")

        return {
            "status": "success",
            "data": serialize_row(value)
        }
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Value not found")
        raise HTTPException(status_code=500, detail=f"Error fetching value: {str(e)}")


@router.put("/{value_id}", response_model=dict)
async def update_value(
    value_id: str,
    request: UpdateValueRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl)
):
    """
    Update a user value

    Args:
        value_id: Value ID
        request: Update request
        user_id: Current user ID
        esl: ESL instance for action evaluation

    Returns:
        Updated value
    """
    try:
        # ESL evaluation for value update
        proposed_action = ProposedAction(
            action_type=ActionType.DATA_COLLECTION,
            content_type="value_update",
            content=f"Updating value: {value_id}",
            urgency=UrgencyLevel.LOW,
            metadata={"value_id": value_id, "updates": request.model_dump(exclude_none=True)}
        )
        decision = await esl.evaluate_action(proposed_action, user_id)

        if decision.status == ESLDecisionStatus.VETOED:
            raise HTTPException(
                status_code=403,
                detail=f"Value update blocked by ESL: {decision.reason}"
            )

        import json
        with get_db() as conn:
            with conn.cursor() as cur:
                update_data = {}
                if request.value is not None:
                    update_data["value"] = request.value
                if request.priority is not None:
                    update_data["priority"] = request.priority
                if request.active is not None:
                    update_data["active"] = request.active
                if request.metadata is not None:
                    update_data["metadata"] = json.dumps(request.metadata)

                if not update_data:
                    raise HTTPException(status_code=400, detail="No fields to update")

                set_clause = ", ".join([f"{key} = %s" for key in update_data.keys()])
                params = list(update_data.values())
                params.extend([str(value_id), str(user_id)])

                cur.execute(
                    f"UPDATE user_values SET {set_clause} WHERE id = %s AND user_id = %s RETURNING *",
                    tuple(params),
                )
                updated_value = cur.fetchone()

        if not updated_value:
            raise HTTPException(status_code=404, detail="Value not found")

        return {
            "status": "success",
            "message": "Value updated successfully",
            "data": serialize_row(updated_value)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating value: {str(e)}")


@router.delete("/{value_id}", response_model=dict)
async def delete_value(
    value_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Delete a user value
    
    Note: Consider soft-delete (setting active=False) instead of hard delete
    to maintain audit trail.
    
    Args:
        value_id: Value ID
        user_id: Current user ID
    
    Returns:
        Success message
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_values SET active = FALSE WHERE id = %s AND user_id = %s RETURNING *",
                    (str(value_id), str(user_id)),
                )
                deleted_value = cur.fetchone()

        if not deleted_value:
            raise HTTPException(status_code=404, detail="Value not found")

        return {
            "status": "success",
            "message": "Value deleted successfully (soft delete)",
            "data": serialize_row(deleted_value)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting value: {str(e)}")


class ReorderValuesRequest(BaseModel):
    valueIds: List[str]


@router.patch("/reorder", response_model=dict)
async def reorder_values(
    request: ReorderValuesRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Reorder values by updating their priority based on provided order.

    Args:
        request: ReorderValuesRequest with 'valueIds' list in desired order
        user_id: Current user ID

    Returns:
        Success message
    """
    value_ids = request.valueIds
    if not value_ids:
        raise HTTPException(status_code=400, detail="No valueIds provided")

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for index, value_id in enumerate(value_ids, start=1):
                    cur.execute(
                        "UPDATE user_values SET priority = %s WHERE id = %s AND user_id = %s",
                        (index, str(value_id), str(user_id)),
                    )

        return {"status": "success", "message": "Values reordered successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reordering values: {str(e)}")


@router.post("/{value_id}/activate", response_model=dict)
async def activate_value(
    value_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Reactivate a previously deactivated value
    
    Args:
        value_id: Value ID
        user_id: Current user ID
    
    Returns:
        Activated value
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_values SET active = TRUE WHERE id = %s AND user_id = %s RETURNING *",
                    (str(value_id), str(user_id)),
                )
                activated_value = cur.fetchone()

        if not activated_value:
            raise HTTPException(status_code=404, detail="Value not found")

        return {
            "status": "success",
            "message": "Value activated successfully",
            "data": serialize_row(activated_value)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error activating value: {str(e)}")
