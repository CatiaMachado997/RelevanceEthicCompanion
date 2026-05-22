"""Sprint J Task 10 — /api/settings/safety/* REST surface.

Four endpoints power the Settings → Safety page:

  GET    /api/settings/safety                     — full state
  PUT    /api/settings/safety/safe-mode           — master toggle
  PUT    /api/settings/safety/categories/{cat}    — per-category upsert
  PUT    /api/settings/safety/tools/{name}        — per-tool upsert
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.safety_preferences import SafetyPreferencesService
from utils.supabase_auth import get_current_user_id, get_current_read_user_id


router = APIRouter(prefix="/api/settings/safety", tags=["safety"])


_VALID_CATEGORIES = {
    "read-personal", "read-external", "write-personal", "write-external",
}


class SafeModeBody(BaseModel):
    enabled: bool


class RequiresConfirmationBody(BaseModel):
    requires_confirmation: bool


def _list_available_tools() -> List[Dict[str, str]]:
    """Return [{name, category}] for every registered tool.

    Imported lazily because services.langchain_tools touches the LLM
    stack which we don't want to pull in for route module import time.
    """
    from services.langchain_tools import (
        MemoryQueryTool, CalendarQueryTool, UserGoalsTool,
        SearchDocumentsTool, WebSearchTool, NoteCreateTool,
    )
    out: List[Dict[str, str]] = []
    for cls in (
        MemoryQueryTool, CalendarQueryTool, UserGoalsTool,
        SearchDocumentsTool, WebSearchTool, NoteCreateTool,
    ):
        # BaseTool is a Pydantic v2 model; read field defaults via model_fields.
        fields = getattr(cls, "model_fields", {}) or {}
        name = fields.get("name").default if "name" in fields else cls.__name__.lower()
        category = fields.get("category").default if "category" in fields else "write-external"
        out.append({"name": name, "category": category})
    return out


@router.get("")
async def get_safety(
    user_id: str = Depends(get_current_read_user_id),
) -> Dict[str, Any]:
    """Return the user's full safety state in one call.

    Frontend uses this on settings page mount; one round-trip is enough.
    """
    prefs = SafetyPreferencesService().load_for_user(user_id)
    return {
        "safe_mode_enabled": prefs.safe_mode_enabled,
        "categories": sorted(prefs.categories),
        "tools": sorted(prefs.tools),
        "available_tools": _list_available_tools(),
    }


@router.put("/safe-mode")
async def put_safe_mode(
    body: SafeModeBody,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    SafetyPreferencesService().set_safe_mode(user_id, enabled=body.enabled)
    return {"safe_mode_enabled": body.enabled}


@router.put("/categories/{category}")
async def put_category(
    category: str,
    body: RequiresConfirmationBody,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    if category not in _VALID_CATEGORIES:
        raise HTTPException(
            status_code=422, detail=f"unknown category: {category}"
        )
    SafetyPreferencesService().set_category(
        user_id,
        category=category,
        requires_confirmation=body.requires_confirmation,
    )
    return {"category": category, "requires_confirmation": body.requires_confirmation}


@router.put("/tools/{tool_name}")
async def put_tool(
    tool_name: str,
    body: RequiresConfirmationBody,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    SafetyPreferencesService().set_tool(
        user_id,
        tool_name=tool_name,
        requires_confirmation=body.requires_confirmation,
    )
    return {"tool_name": tool_name, "requires_confirmation": body.requires_confirmation}
