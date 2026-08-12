"""CRUD endpoints for explicit, user-controlled chatbot memory."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.controlled_memory import ControlledMemoryService
from utils.serialization import serialize_row, serialize_rows
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

router = APIRouter(prefix="/api/memories", tags=["Memories"])


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    kind: Literal["fact", "preference", "summary"] = "fact"
    source_turn_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    kind: Optional[Literal["fact", "preference", "summary"]] = None
    active: Optional[bool] = None


@router.get("")
def list_memories(user_id: str = Depends(get_current_read_user_id)):
    return {"memories": serialize_rows(ControlledMemoryService().list(str(user_id)))}


@router.post("", status_code=201)
def create_memory(request: MemoryCreate, user_id: str = Depends(get_current_user_id)):
    row = ControlledMemoryService().create(str(user_id), **request.model_dump())
    return serialize_row(row)


@router.patch("/{memory_id}")
def update_memory(
    memory_id: str, request: MemoryUpdate, user_id: str = Depends(get_current_user_id)
):
    row = ControlledMemoryService().update(
        str(user_id), memory_id, **request.model_dump()
    )
    if not row:
        raise HTTPException(
            status_code=404, detail="Memory not found or no changes provided"
        )
    return serialize_row(row)


@router.delete("/{memory_id}", status_code=204)
def forget_memory(memory_id: str, user_id: str = Depends(get_current_user_id)):
    if not ControlledMemoryService().forget(str(user_id), memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
