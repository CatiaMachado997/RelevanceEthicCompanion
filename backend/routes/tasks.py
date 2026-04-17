# backend/routes/tasks.py
"""Tasks API routes — CRUD + AI extraction."""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, SecretStr

from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel, ESLDecisionStatus
from utils.db import get_db_connection
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from services.context_manager import ContextManager
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_context_manager() -> ContextManager:
    return ContextManager()


def get_esl(cm: ContextManager = Depends(get_context_manager)) -> EthicalSafeguardLayer:
    return EthicalSafeguardLayer(cm)


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    project_id: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    due_date: Optional[str] = None
    source_origin: str = "manual"
    ai_confidence: Optional[float] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    due_date: Optional[str] = None
    project_id: Optional[str] = None


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


_EXTRACT_PROMPT = """\
Extract actionable tasks from the following text. Return valid JSON only, no other text.
Format: {{"tasks": [{{"title": "short action title", "description": "optional detail", "priority": 5}}]}}
Priority scale: 1=highest urgency, 10=lowest. Only include concrete actionable items.

Text:
{text}"""


def _serialize_task(row: dict) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "project_id": str(row["project_id"]) if row["project_id"] else None,
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"].isoformat() if row["due_date"] else None,
        "source_origin": row["source_origin"],
        "ai_confidence": row["ai_confidence"],
        "user_confirmed": row["user_confirmed"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def get_user_tasks(
    user_id: str, project_id: Optional[str] = None, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT * FROM tasks WHERE user_id = %s"
            params: list = [user_id]
            if project_id:
                query += " AND project_id = %s"
                params.append(project_id)
            if status:
                query += " AND status = %s"
                params.append(status)
            query += " ORDER BY priority ASC, created_at DESC"
            cur.execute(query, params)
            rows = cur.fetchall()
    return [_serialize_task(r) for r in rows]


@router.post("/extract", response_model=Dict[str, Any])
async def extract_tasks(
    request: ExtractRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    """
    Extract task suggestions from free text using Groq LLM.
    Returns suggestions only — does NOT create tasks.
    User must confirm and call POST /api/tasks to create each.
    """
    proposed_action = ProposedAction(
        action_type=ActionType.CONTENT_GENERATION,
        content_type="task_extraction",
        content="Extracting tasks from user-provided text",
        urgency=UrgencyLevel.LOW,
        metadata={},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Extraction blocked by ESL: {decision.reason}"
        )

    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="AI extraction not configured")

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=SecretStr(settings.GROQ_API_KEY),
            temperature=0,
        )
        prompt = _EXTRACT_PROMPT.format(text=request.text)
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_content = response.content
        if isinstance(raw_content, list):
            # ChatGroq may return list-of-parts for some models; join text parts.
            raw_content = "".join(
                p if isinstance(p, str) else str(p.get("text", "")) for p in raw_content
            )
        raw = raw_content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        suggestions = parsed.get("tasks", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning(f"Task extraction parse failed: {e}")
        suggestions = []

    return {"suggestions": suggestions}


@router.get("/", response_model=List[Dict[str, Any]])
async def list_tasks(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
) -> List[Dict[str, Any]]:
    try:
        return get_user_tasks(user_id, project_id, status)
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tasks")


@router.get("/{task_id}", response_model=Dict[str, Any])
async def get_task(
    task_id: str,
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
                    (task_id, user_id),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return _serialize_task(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve task")


@router.post("/", response_model=Dict[str, Any], status_code=201)
async def create_task(
    request: CreateTaskRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="task_creation",
        content=f"Creating task: {request.title}",
        urgency=UrgencyLevel.LOW,
        metadata={"title": request.title},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Blocked by ESL: {decision.reason}"
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tasks
                        (user_id, project_id, title, description, priority, due_date,
                         source_origin, ai_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        user_id,
                        request.project_id,
                        request.title,
                        request.description,
                        request.priority,
                        request.due_date,
                        request.source_origin,
                        request.ai_confidence,
                    ),
                )
                row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Task insert returned no row")
        return _serialize_task(row)
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.patch("/{task_id}", response_model=Dict[str, Any])
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="task_update",
        content=f"Updating task: {task_id}",
        urgency=UrgencyLevel.LOW,
        metadata={"task_id": task_id},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Update blocked by ESL: {decision.reason}"
        )

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        set_clause += ", updated_at = NOW()"
        params = list(updates.values()) + [task_id, user_id]
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE tasks SET {set_clause} WHERE id = %s AND user_id = %s RETURNING *",
                    params,
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return _serialize_task(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        raise HTTPException(status_code=500, detail="Failed to update task")


@router.delete("/{task_id}", response_model=Dict[str, Any])
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    esl: EthicalSafeguardLayer = Depends(get_esl),
) -> Dict[str, Any]:
    proposed_action = ProposedAction(
        action_type=ActionType.DATA_COLLECTION,
        content_type="task_delete",
        content=f"Deleting task: {task_id}",
        urgency=UrgencyLevel.LOW,
        metadata={"task_id": task_id},
    )
    decision = await esl.evaluate_action(proposed_action, user_id)
    if decision.status == ESLDecisionStatus.VETOED:
        raise HTTPException(
            status_code=403, detail=f"Delete blocked by ESL: {decision.reason}"
        )

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tasks WHERE id = %s AND user_id = %s RETURNING id",
                    (task_id, user_id),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"success": True, "id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete task")
