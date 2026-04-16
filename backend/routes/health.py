"""GET /health — returns status of all backend dependencies."""

from fastapi import APIRouter
from utils.health import check_db, check_weaviate

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    db = check_db()
    weaviate = check_weaviate()
    overall = "ok" if db["status"] == "ok" else "degraded"
    return {
        "status": overall,
        "components": {
            "database": db,
            "weaviate": weaviate,
        },
    }
