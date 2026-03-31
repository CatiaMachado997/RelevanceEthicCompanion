"""User status endpoint — PUT /api/status/"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/status", tags=["status"])


@router.put("/")
async def update_status():
    return {"ok": True}
