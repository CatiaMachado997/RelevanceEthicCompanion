"""
Minimal auth routes for Supabase JWT identity introspection.
"""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from utils.supabase_auth import UserPrincipal, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class SessionCreate(BaseModel):
    access_token: str
    remember_me: bool = False


@router.get("/me", response_model=dict)
async def get_me(user: UserPrincipal = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
    }


@router.post("/session")
async def create_session(body: SessionCreate, response: Response):
    """Exchange Supabase token for an HttpOnly cookie session."""
    max_age = 60 * 60 * 24 * 30 if body.remember_me else 60 * 60 * 24  # 30d or 24h
    response.set_cookie(
        key="ec_session",
        value=body.access_token,
        httponly=True,
        secure=False,    # False for local dev; set True in production via env var
        samesite="lax",  # lax allows navigation from external links
        max_age=max_age,
    )
    return {"ok": True}


@router.delete("/session")
async def delete_session(response: Response):
    """Clear the session cookie on sign-out."""
    response.delete_cookie("ec_session")
    return {"ok": True}
