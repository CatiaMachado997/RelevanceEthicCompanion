"""ContextBuilder — loads M1 + M2 user context into AgentState."""

from orchestrator.state import AgentState
from services.context_manager import ContextManager
from utils.weaviate_client import get_weaviate_client


def get_context_manager() -> ContextManager:
    try:
        weaviate = get_weaviate_client()
    except Exception:
        weaviate = None

    embedding = None
    if weaviate:
        try:
            from config import settings
            from services.embedding_service import EmbeddingService

            if settings.GEMINI_API_KEY:
                embedding = EmbeddingService(api_key=settings.GEMINI_API_KEY)
        except Exception:
            embedding = None

    return ContextManager(weaviate_client=weaviate, embedding_service=embedding)


async def context_builder_node(state: AgentState) -> dict:
    """Populate user_context, conversation_history, and source_context from M1 + M2."""
    cm = get_context_manager()
    ctx = await cm.get_user_context(state["user_id"])
    history = await cm.get_conversation_history(
        state["user_id"], limit=20, conversation_id=state.get("conversation_id")
    )

    # Compute 360° snapshot (tasks, projects, events) — non-blocking on failure
    snapshot: dict = {}
    try:
        from services.context_snapshot import ContextSnapshotService

        snapshot = ContextSnapshotService().compute(state["user_id"])
    except Exception:
        pass

    # Fetch recent source items (calendar + email) — non-blocking on failure
    source_context: list = []
    try:
        source_context = await cm.get_recent_source_items(state["user_id"], limit=20)
    except Exception:
        pass

    return {
        "user_context": {
            "active_goals": [
                g.__dict__ if hasattr(g, "__dict__") else g
                for g in (ctx.active_goals or [])
            ],
            "user_values": [
                v.__dict__ if hasattr(v, "__dict__") else v
                for v in (ctx.user_values or [])
            ],
            "focus_mode": getattr(ctx, "focus_mode", False),
            "additional_context": getattr(ctx, "additional_context", {}),
            "snapshot": snapshot,
            "source_context": source_context,
        },
        "conversation_history": history or [],
        "source_context": source_context,
        # Reset any stale confirmation from the previous turn before routing begins.
        "pending_tool_confirmation": None,
    }
