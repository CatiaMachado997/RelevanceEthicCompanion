# backend/routes/projects.py
"""Projects API routes — CRUD for the projects domain."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus
from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(cm: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(cm)


class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    goal_id: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    goal_id: Optional[str] = None


def get_user_projects(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query projects table for a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT id, user_id, title, description, status, goal_id, created_at, updated_at "
                    "FROM projects WHERE user_id = %s AND status = %s ORDER BY created_at DESC",
                    (user_id, status),
                )
            else:
                cur.execute(
                    "SELECT id, user_id, title, description, status, goal_id, created_at, updated_at "
                    "FROM projects WHERE user_id = %s AND status != 'archived' ORDER BY created_at DESC",
                    (user_id,),
                )
            rows = cur.fetchall()
    return [
        {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "goal_id": str(row["goal_id"]) if row["goal_id"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    ]


@router.get("/", response_model=List[Dict[str, Any]])
async def list_projects(
    status: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
) -> List[Dict[str, Any]]:
    """List active projects for the current user."""
    try:
        return get_user_projects(user_id, status)
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve projects")


@router.get("/{project_id}", response_model=Dict[str, Any])
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Get a single project by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, title, description, status, goal_id, created_at, updated_at "
                    "FROM projects WHERE id = %s AND user_id = %s",
                    (project_id, user_id),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        return {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "goal_id": str(row["goal_id"]) if row["goal_id"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve project")


@router.post("/", response_model=Dict[str, Any], status_code=201)
async def create_project(
    request: CreateProjectRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    """Create a new project."""
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="project_creation",
        content=f"Creating project: {request.title}",
        urgency=UrgencyLevel.LOW,
        metadata={"title": request.title},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(status_code=403, detail=f"Blocked by ESL: {decision.reason}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO projects (user_id, title, description, goal_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, user_id, title, description, status, goal_id, created_at, updated_at
                    """,
                    (user_id, request.title, request.description, request.goal_id),
                )
                row = cur.fetchone()
        return {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "goal_id": str(row["goal_id"]) if row["goal_id"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")


@router.patch("/{project_id}", response_model=Dict[str, Any])
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    """Update a project's fields."""
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="project_update",
        content=f"Updating project: {project_id}",
        urgency=UrgencyLevel.LOW,
        metadata={"project_id": project_id},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(status_code=403, detail=f"Update blocked by ESL: {decision.reason}")

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        set_clause += ", updated_at = NOW()"
        params = list(updates.values()) + [project_id, user_id]
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE projects SET {set_clause} WHERE id = %s AND user_id = %s "
                    "RETURNING id, user_id, title, description, status, goal_id, created_at, updated_at",
                    params,
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        return {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "goal_id": str(row["goal_id"]) if row["goal_id"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=500, detail="Failed to update project")


@router.delete("/{project_id}", response_model=Dict[str, Any])
async def archive_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    """Archive a project (soft delete)."""
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="project_archive",
        content=f"Archiving project: {project_id}",
        urgency=UrgencyLevel.LOW,
        metadata={"project_id": project_id},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(status_code=403, detail=f"Archive blocked by ESL: {decision.reason}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE projects SET status = 'archived', updated_at = NOW() "
                    "WHERE id = %s AND user_id = %s RETURNING id",
                    (project_id, user_id),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"success": True, "id": project_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive project: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive project")
