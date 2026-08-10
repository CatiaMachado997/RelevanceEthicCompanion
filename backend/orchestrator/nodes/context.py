"""ContextBuilder — loads M1 + M2 user context into AgentState."""

from orchestrator.state import AgentState
from services.context_manager import ContextManager
from utils.weaviate_client import get_weaviate_client


def bound_conversation_history(history: list[dict], max_chars: int = 12000) -> list[dict]:
    """Keep the newest complete turns within a predictable prompt budget."""
    selected: list[dict] = []
    used = 0
    for turn in reversed(history):
        content = str(turn.get("content") or "")
        cost = len(content) + 32
        if selected and used + cost > max_chars:
            break
        if cost > max_chars:
            turn = {**turn, "content": content[-max_chars:]}
            cost = max_chars
        selected.append(turn)
        used += cost
    return list(reversed(selected))


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

            embedding = EmbeddingService(api_key=settings.GEMINI_API_KEY)
        except Exception:
            embedding = None

    return ContextManager(weaviate_client=weaviate, embedding_service=embedding)


async def context_builder_node(state: AgentState) -> dict:
    """Populate user_context, conversation_history, and source_context from M1 + M2."""
    cm = get_context_manager()
    ctx = await cm.get_user_context(state["user_id"])
    history_override = state.get("conversation_history_override")
    history = (
        history_override
        if history_override is not None
        else await cm.get_conversation_history(
            state["user_id"], limit=20, conversation_id=state.get("conversation_id")
        )
    )
    history = bound_conversation_history(history or [])

    approved_memories: list = []
    try:
        from services.controlled_memory import ControlledMemoryService

        approved_memories = ControlledMemoryService().list(
            state["user_id"], active_only=True, limit=20
        )
    except Exception:
        pass

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
            "approved_memories": approved_memories,
        },
        "conversation_history": history,
        "source_context": source_context,
        # Reset any stale confirmation from the previous turn before routing begins.
        "pending_tool_confirmation": None,
    }
