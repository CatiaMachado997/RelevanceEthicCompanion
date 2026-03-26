"""Health check helpers — non-fatal probes for DB and Weaviate."""
import logging
from utils.db import get_db_connection

logger = logging.getLogger(__name__)


def check_db() -> dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")
        return {"status": "error", "detail": str(e)}


def check_weaviate() -> dict:
    try:
        # Import here to avoid circular imports and to allow graceful failure
        from utils.weaviate_client import get_weaviate_client
        client = get_weaviate_client()
        if client is None:
            return {"status": "unavailable"}
        # WeaviateClient wraps the v4 client — check if the inner client is ready
        inner = getattr(client, "client", None)
        if inner is None:
            return {"status": "unavailable"}
        ready = inner.is_ready() if hasattr(inner, "is_ready") else True
        if ready:
            return {"status": "ok"}
        return {"status": "unavailable"}
    except Exception as e:
        logger.warning(f"Weaviate health check failed: {e}")
        return {"status": "unavailable", "detail": str(e)}
