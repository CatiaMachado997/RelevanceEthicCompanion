"""
Chat API Routes

Integrates: User Input → Orchestrator → ESL → LLM → Response
All chat interactions go through ESL for ethical protection.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from typing import Annotated, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, UTC

from services.context_manager import ContextManager
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from utils.rate_limit import limiter
from config import settings
from utils.weaviate_client import get_weaviate_client
from utils.db import get_db_connection
from services.embedding_service import EmbeddingService

# Router
router = APIRouter(prefix="/api/chat", tags=["Chat"])


# Request/Response models
class ChatMessage(BaseModel):
    """A chat message"""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to send a chat message"""

    message: str = Field(..., min_length=1, description="User's message")
    context: dict = Field(default_factory=lambda: {}, description="Additional context")


class ChatResponse(BaseModel):
    """Response from chat endpoint"""

    message: str = Field(..., description="User's message")
    response: Annotated[
        Optional[str], Field(description="AI response (if ESL approved)")
    ] = None
    executed: bool = Field(..., description="Whether response was delivered")
    esl_decision: dict = Field(..., description="ESL decision details")
    transparency: str = Field(..., description="Explanation of ESL decision")
    timestamp: str
    tool_executed: Annotated[
        Optional[bool], Field(description="Whether a tool was executed.")
    ] = None
    tool_name: Annotated[
        Optional[str], Field(description="Name of the tool executed.")
    ] = None
    tool_input: Annotated[
        Optional[Dict[str, Any]], Field(description="Input provided to the tool.")
    ] = None
    tool_output: Annotated[
        Optional[Dict[str, Any]], Field(description="Output received from the tool.")
    ] = None


class ConversationHistoryResponse(BaseModel):
    """Conversation history"""

    user_id: str
    messages: List[ChatMessage]
    total_count: int


class LLMModel(BaseModel):
    """Represents an available LLM model"""

    id: str = Field(
        ..., description="Unique identifier for the model (e.g., Groq API model name)."
    )
    display_name: str = Field(..., description="Human-readable name for the model.")
    provider: str = Field(
        ..., description="The provider of the model (e.g., 'Groq', 'OpenAI')."
    )
    context_window: Optional[int] = Field(
        None, description="Maximum context window in tokens."
    )


# Dependencies
def get_context_manager() -> ContextManager:
    """Get ContextManager instance with Weaviate and EmbeddingService when available"""
    try:
        weaviate_client = get_weaviate_client()
    except Exception:
        weaviate_client = None
    embedding_service = (
        EmbeddingService(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    )
    return ContextManager(
        weaviate_client=weaviate_client, embedding_service=embedding_service
    )


GROQ_MODELS = [
    # Production
    LLMModel(
        id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="openai/gpt-oss-120b",
        display_name="GPT OSS 120B",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="openai/gpt-oss-20b",
        display_name="GPT OSS 20B",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="groq/compound",
        display_name="Groq Compound",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="groq/compound-mini",
        display_name="Groq Compound Mini",
        provider="Groq",
        context_window=131072,
    ),
    # Preview
    LLMModel(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        display_name="Llama 4 Scout 17B",
        provider="Groq",
        context_window=131072,
    ),
    LLMModel(
        id="moonshotai/kimi-k2-instruct-0905",
        display_name="Kimi K2",
        provider="Groq",
        context_window=262144,
    ),
    LLMModel(
        id="qwen/qwen3-32b",
        display_name="Qwen3 32B",
        provider="Groq",
        context_window=131072,
    ),
]
DEFAULT_MODEL = "llama-3.3-70b-versatile"


@router.get("/stream")
async def stream_chat(
    message: str,
    model: str = DEFAULT_MODEL,
    conversation_id: Optional[str] = None,
    active_sources: str = "",  # comma-separated: "calendar,web,goals,memory" — empty = all
    user_id: str = Depends(get_current_read_user_id),
):
    """Server-Sent Events endpoint for streaming chat responses via LangGraph."""
    import json as _json
    from orchestrator.graph import stream_langgraph

    sources = (
        [s.strip() for s in active_sources.split(",") if s.strip()]
        if active_sources
        else []
    )

    async def _lg_stream():
        async for event in stream_langgraph(
            user_id, message, model, conversation_id, active_sources=sources
        ):
            yield f"data: {_json.dumps(event)}\n\n"

    return StreamingResponse(_lg_stream(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """List all conversations for the current user, most recently updated first."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, folder_id, created_at, updated_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 100
            """,
                (user_id,),
            )
            rows = cur.fetchall()
    return {
        "conversations": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "folder_id": str(r["folder_id"]) if r.get("folder_id") else None,
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """Fetch a single conversation's metadata (no messages)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, folder_id, created_at, updated_at
                FROM conversations
                WHERE id = %s AND user_id = %s
            """,
                (conversation_id, user_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "folder_id": str(row["folder_id"]) if row.get("folder_id") else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@router.post("/conversations")
async def create_conversation(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Create a new conversation thread."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (user_id, title)
                VALUES (%s, 'New conversation')
                RETURNING id, title, created_at, updated_at
            """,
                (user_id,),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=500, detail="Conversation insert returned no row"
        )
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    body: dict,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Rename an existing conversation."""
    title = body.get("title", "").strip()[:100]
    if not title:
        raise HTTPException(status_code=400, detail="Title required")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations SET title = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING id, title, updated_at
            """,
                (title, conversation_id, user_id),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": str(row["id"]), "title": row["title"]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Delete a conversation and all its turns (cascade)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id),
            )
    return {"success": True}


@router.get("/models", response_model=List[LLMModel])
async def get_available_llm_models():
    """
    Returns a list of available LLM models.
    OrchestratorV2 uses Groq (Llama) for chat, Gemini only for embeddings.
    """
    return GROQ_MODELS


@router.post("/", response_model=ChatResponse)
@limiter.limit("30/minute")
async def send_message(
    request: Request,
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Non-streaming chat endpoint — collects LangGraph events and returns the full response.
    Prefer GET /api/chat/stream for real-time streaming.
    """
    from orchestrator.graph import stream_langgraph

    response_text = ""
    esl_decision_raw = None

    try:
        async for event in stream_langgraph(user_id, body.message, DEFAULT_MODEL):
            if event.get("event") == "token":
                response_text += event.get("token", "")
            elif event.get("event") == "done":
                esl_decision_raw = event.get("esl_decision")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing message: {str(e)}"
        )

    # Normalise ESL decision to a plain dict
    if esl_decision_raw and hasattr(esl_decision_raw, "status"):
        esl_decision: dict = {
            "status": str(
                esl_decision_raw.status.value
                if hasattr(esl_decision_raw.status, "value")
                else esl_decision_raw.status
            ),
            "reason": getattr(esl_decision_raw, "reason", ""),
            "violated_values": getattr(esl_decision_raw, "violated_values", []),
        }
    elif isinstance(esl_decision_raw, dict):
        esl_decision = esl_decision_raw
    else:
        esl_decision = {
            "status": "APPROVED",
            "reason": "Processed by LangGraph",
            "violated_values": [],
        }

    return ChatResponse(
        message=body.message,
        response=response_text or None,
        executed=bool(response_text),
        esl_decision=esl_decision,
        transparency=esl_decision.get("reason", ""),
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    limit: int = 50,
    offset: int = 0,
    conversation_id: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
    context_manager: ContextManager = Depends(get_context_manager),
):
    """
    Get conversation history from PostgreSQL (conversation_turns table).
    Filters by conversation_id when provided.
    """
    try:
        turns = await context_manager.get_conversation_history(
            user_id=str(user_id),
            limit=limit,
            conversation_id=conversation_id,
        )
    except Exception:
        turns = []

    messages = [
        ChatMessage(
            role=t["role"],
            content=t["content"],
            timestamp=(
                t["created_at"].isoformat()
                if t.get("created_at") and hasattr(t["created_at"], "isoformat")
                else (str(t["created_at"]) if t.get("created_at") else "")
            ),
        )
        for t in turns
    ]

    return {
        "user_id": str(user_id),
        "messages": messages,
        "total_count": len(messages),
    }


@router.post("/proactive", response_model=dict)
async def suggest_proactive_action(
    suggestion_type: str,
    suggestion_content: str,
    rationale: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Proactive AI action suggestion endpoint.
    Proactive suggestions are now handled by the background scheduler (Sprint 2b).
    This endpoint is retained for API compatibility and returns a stub response.
    """
    return {
        "status": "acknowledged",
        "executed": False,
        "esl_decision": {
            "status": "PENDING",
            "reason": "Proactive scheduler handles this in background",
            "violated_values": [],
        },
        "transparency": "Proactive actions are evaluated asynchronously by the background scheduler",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.delete("/history", response_model=dict)
async def clear_conversation_history(
    user_id: str = Depends(get_current_user_id),
    confirm: bool = False,
    context_manager: ContextManager = Depends(get_context_manager),
):
    """
    Clear conversation history (in-memory)
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must confirm deletion by setting confirm=True"
        )

    try:
        deleted_count = await context_manager.clear_semantic_memory(str(user_id))

        return {
            "status": "success",
            "message": "Conversation history cleared",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")
