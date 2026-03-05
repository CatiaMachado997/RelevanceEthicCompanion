"""
Minimal auth routes for Supabase JWT identity introspection.
"""

from fastapi import APIRouter, Depends

from utils.supabase_auth import UserPrincipal, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.get("/me", response_model=dict)
async def get_me(user: UserPrincipal = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
    }
