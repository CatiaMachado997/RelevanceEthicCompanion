"""Search API Route — semantic hybrid search across Weaviate collections"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Any

from utils.supabase_auth import get_current_user_id
from utils.weaviate_client import get_weaviate_client
from services.embedding_service import EmbeddingService
from config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Search"])

# Collections to search across and the label to surface in results
SEARCH_COLLECTIONS = [
    ("ConversationMemory", "memory"),
    ("ContextualEvents", "event"),
]


@router.get("/", response_model=List[Dict[str, Any]])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
):
    """
    Hybrid semantic + keyword search across the user's Weaviate memories.

    Returns a flat list of results ranked by relevance score, each with:
    - id: Weaviate UUID
    - type: collection label (memory, event)
    - content: primary text field
    - score: relevance score (0–1)
    - metadata: raw properties dict
    """
    try:
        embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
        query_vector = await embedding_service.generate_embedding(q)

        weaviate_client = get_weaviate_client()
        all_results: List[Dict[str, Any]] = []

        for collection_name, result_type in SEARCH_COLLECTIONS:
            try:
                raw = weaviate_client.hybrid_search(
                    collection=collection_name,
                    query=q,
                    query_vector=query_vector,
                    user_id=str(user_id),
                    limit=limit,
                    alpha=0.7,
                )
                for item in raw:
                    props = item.get("properties", {})
                    content = (
                        props.get("content")
                        or props.get("title")
                        or props.get("summary")
                        or ""
                    )
                    all_results.append({
                        "id": item.get("uuid"),
                        "type": result_type,
                        "content": content,
                        "score": item.get("score") or 0.0,
                        "metadata": props,
                    })
            except Exception as e:
                # If a collection doesn't exist yet, skip it gracefully
                logger.warning(f"Search in {collection_name} failed (may not exist yet): {e}")

        # Sort all results by score descending
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:limit]

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
