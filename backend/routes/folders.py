"""
Folders API Routes

Users can create, rename, recolour, and delete folders to organise their
chat conversations. A conversation with folder_id = NULL is "unfoldered".

Auth: all endpoints require an authenticated user. Users only see/modify
their own folders (enforced by user_id filter on every query).

No ESL gating: folder CRUD is a private, self-directed organisational
action that doesn't affect other people or push anything to the user.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from psycopg.errors import UniqueViolation
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from utils.db import get_db_connection
from utils.rate_limit import limiter

router = APIRouter(prefix="/api/folders", tags=["Folders"])


# ─── Request / Response models ──────────────────────────────────────────


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: Optional[str] = Field(None, max_length=16)
    position: Optional[int] = Field(None, ge=0)


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    color: Optional[str] = Field(None, max_length=16)
    position: Optional[int] = Field(None, ge=0)


class MoveConversationRequest(BaseModel):
    folder_id: Optional[str] = Field(
        None, description="Target folder UUID, or null to un-folder"
    )


# ─── Helpers ────────────────────────────────────────────────────────────


def _serialize_folder(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "color": row["color"],
        "position": row["position"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


# ─── Endpoints ──────────────────────────────────────────────────────────


@router.get("")
async def list_folders(
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """List all folders for the current user, ordered by position then created_at."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, color, position, created_at, updated_at
                FROM folders
                WHERE user_id = %s
                ORDER BY position ASC, created_at ASC
            """,
                (user_id,),
            )
            rows = cur.fetchall()
    return {"folders": [_serialize_folder(r) for r in rows]}


@router.post("")
@limiter.limit("30/minute")
async def create_folder(
    request: Request,
    body: FolderCreate,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Create a new folder owned by the current user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # If no explicit position, append to the end.
            if body.position is None:
                cur.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM folders WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                next_pos = row["next_pos"] if row else 0
            else:
                next_pos = body.position

            try:
                cur.execute(
                    """
                    INSERT INTO folders (user_id, name, color, position)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, color, position, created_at, updated_at
                """,
                    (user_id, body.name.strip(), body.color, next_pos),
                )
                row = cur.fetchone()
            except UniqueViolation:
                raise HTTPException(
                    status_code=409,
                    detail=f"A folder named '{body.name.strip()}' already exists",
                )
    return _serialize_folder(row)


@router.patch("/{folder_id}")
async def update_folder(
    folder_id: str,
    body: FolderUpdate,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Rename, recolour, or reorder a folder."""
    # Build dynamic SET clause from provided fields.
    updates: list[str] = []
    params: list = []
    if body.name is not None:
        updates.append("name = %s")
        params.append(body.name.strip())
    if body.color is not None:
        updates.append("color = %s")
        params.append(body.color)
    if body.position is not None:
        updates.append("position = %s")
        params.append(body.position)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    params.extend([folder_id, user_id])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""
                    UPDATE folders SET {", ".join(updates)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, name, color, position, created_at, updated_at
                    """,
                    params,
                )
                row = cur.fetchone()
            except UniqueViolation:
                raise HTTPException(
                    status_code=409,
                    detail="A folder with that name already exists",
                )
    if not row:
        raise HTTPException(status_code=404, detail="Folder not found")
    return _serialize_folder(row)


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Delete a folder. Conversations inside fall back to unfoldered (folder_id = NULL)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM folders WHERE id = %s AND user_id = %s",
                (folder_id, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Folder not found")
    return {"success": True}


# ─── Move conversation into / out of a folder ──────────────────────────


@router.patch("/conversations/{conversation_id}")
async def move_conversation(
    conversation_id: str,
    body: MoveConversationRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Move a conversation into a folder, or un-folder it by passing folder_id = null.
    Both the conversation and the target folder must belong to the caller.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verify target folder exists and is owned by user (if set).
            if body.folder_id is not None:
                cur.execute(
                    "SELECT 1 FROM folders WHERE id = %s AND user_id = %s",
                    (body.folder_id, user_id),
                )
                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404, detail="Target folder not found"
                    )

            cur.execute(
                """
                UPDATE conversations
                   SET folder_id = %s, updated_at = NOW()
                 WHERE id = %s AND user_id = %s
                RETURNING id, folder_id
                """,
                (body.folder_id, conversation_id, user_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": str(row["id"]),
        "folder_id": str(row["folder_id"]) if row["folder_id"] else None,
    }
