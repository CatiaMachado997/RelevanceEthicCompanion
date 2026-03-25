"""
Chat API Routes

Integrates: User Input → Orchestrator → ESL → LLM → Response
All chat interactions go through ESL for ethical protection.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, UTC
import json

from services.orchestrator_v2 import OrchestratorV2
from services.context_manager import ContextManager
from esl.models import ActionType
from utils.supabase_auth import get_current_user_id, get_current_read_user_id
from utils.rate_limit import limiter
from tavily import TavilyClient
from services.relevance_scoring import RelevanceScoringEngine as RelevanceScoring
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
    context: Optional[dict] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    message: str = Field(..., description="User's message")
    response: Optional[str] = Field(None, description="AI response (if ESL approved)")
    executed: bool = Field(..., description="Whether response was delivered")
    esl_decision: dict = Field(..., description="ESL decision details")
    transparency: str = Field(..., description="Explanation of ESL decision")
    timestamp: str
    tool_executed: Optional[bool] = Field(None, description="Whether a tool was executed.")
    tool_name: Optional[str] = Field(None, description="Name of the tool executed.")
    tool_input: Optional[Dict[str, Any]] = Field(None, description="Input provided to the tool.")
    tool_output: Optional[Dict[str, Any]] = Field(None, description="Output received from the tool.")


class ConversationHistoryResponse(BaseModel):
    """Conversation history"""
    user_id: str
    messages: List[ChatMessage]
    total_count: int


class LLMModel(BaseModel):
    """Represents an available LLM model"""
    id: str = Field(..., description="Unique identifier for the model (e.g., Groq API model name).")
    display_name: str = Field(..., description="Human-readable name for the model.")
    provider: str = Field(..., description="The provider of the model (e.g., 'Groq', 'OpenAI').")
    context_window: Optional[int] = Field(None, description="Maximum context window in tokens.")


# Dependencies
def get_context_manager() -> ContextManager:
    """Get ContextManager instance with Weaviate and EmbeddingService when available"""
    try:
        weaviate_client = get_weaviate_client()
    except Exception:
        weaviate_client = None
    embedding_service = EmbeddingService(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    return ContextManager(weaviate_client=weaviate_client, embedding_service=embedding_service)

GROQ_MODELS = [
    # Production
    LLMModel(id="llama-3.3-70b-versatile",                    display_name="Llama 3.3 70B",       provider="Groq", context_window=131072),
    LLMModel(id="llama-3.1-8b-instant",                       display_name="Llama 3.1 8B",        provider="Groq", context_window=131072),
    LLMModel(id="openai/gpt-oss-120b",                        display_name="GPT OSS 120B",        provider="Groq", context_window=131072),
    LLMModel(id="openai/gpt-oss-20b",                         display_name="GPT OSS 20B",         provider="Groq", context_window=131072),
    LLMModel(id="groq/compound",                              display_name="Groq Compound",       provider="Groq", context_window=131072),
    LLMModel(id="groq/compound-mini",                         display_name="Groq Compound Mini",  provider="Groq", context_window=131072),
    # Preview
    LLMModel(id="meta-llama/llama-4-scout-17b-16e-instruct",  display_name="Llama 4 Scout 17B",   provider="Groq", context_window=131072),
    LLMModel(id="moonshotai/kimi-k2-instruct-0905",           display_name="Kimi K2",             provider="Groq", context_window=262144),
    LLMModel(id="qwen/qwen3-32b",                             display_name="Qwen3 32B",           provider="Groq", context_window=131072),
]
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_orchestrator(model: str = DEFAULT_MODEL) -> OrchestratorV2:
    """Get OrchestratorV2 instance with Tavily web search when API key is available"""
    context_manager = get_context_manager()
    tavily_client = None
    relevance_engine = None
    if settings.TAVILY_API_KEY:
        tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        relevance_engine = RelevanceScoring(context_manager)
    return OrchestratorV2(
        context_manager,
        relevance_engine=relevance_engine,
        tavily_client=tavily_client,
        model=model,
    )

@router.get("/stream")
async def stream_chat(
    message: str,
    model: str = DEFAULT_MODEL,
    conversation_id: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
):
    """Server-Sent Events endpoint for streaming chat responses."""
    orchestrator = get_orchestrator(model=model)

    async def event_generator():
        try:
            async for event in orchestrator.stream_message(user_id, message, conversation_id=conversation_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """List all conversations for the current user, most recently updated first."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 100
            """, (user_id,))
            rows = cur.fetchall()
    return {"conversations": [
        {"id": str(r["id"]), "title": r["title"],
         "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat()}
        for r in rows
    ]}


@router.post("/conversations")
async def create_conversation(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Create a new conversation thread."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversations (user_id, title)
                VALUES (%s, 'New conversation')
                RETURNING id, title, created_at, updated_at
            """, (user_id,))
            row = cur.fetchone()
    return {"id": str(row["id"]), "title": row["title"],
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()}


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
            cur.execute("""
                UPDATE conversations SET title = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING id, title, updated_at
            """, (title, conversation_id, user_id))
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
                (conversation_id, user_id)
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
    orchestrator: OrchestratorV2 = Depends(get_orchestrator)
):
    """
    Send a chat message with ESL protection
    
    Flow:
    1. User sends message
    2. Orchestrator generates response (via LLM in future)
    3. ESL evaluates response
    4. If approved, return response
    5. If vetoed, block and explain why
    
    Args:
        request: Chat request with message
        user_id: Current user ID
        orchestrator: Orchestrator instance
    
    Returns:
        Chat response with ESL decision
        
    Example:
        POST /api/chat
        {
            "message": "What's on my calendar today?",
            "context": {}
        }
        
        Response:
        {
            "message": "What's on my calendar today?",
            "response": "You have 3 meetings today...",
            "executed": true,
            "esl_decision": {...},
            "transparency": "Action executed: ...",
            "timestamp": "2025-11-04T20:00:00Z"
        }
    """
    try:
        # Handle message through orchestrator (includes ESL evaluation)
        result = await orchestrator.handle_user_message(
            user_id=user_id,
            message=body.message,
            context=body.context
        )

        default_reason = result.get("error", "Request failed before ESL decision")
        esl_decision = result.get("esl_decision") or {
            "status": "VETOED",
            "reason": default_reason,
            "violated_values": []
        }

        return ChatResponse(
            message=result.get("message", body.message),
            response=result.get("response"),
            executed=result.get("executed", False),
            esl_decision=esl_decision,
            transparency=result.get("transparency", default_reason),
            timestamp=datetime.now(UTC).isoformat(),
            tool_executed=result.get("tool_executed"),
            tool_name=result.get("tool_name"),
            tool_input=result.get("tool_input"),
            tool_output=result.get("tool_output")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    limit: int = 50,
    offset: int = 0,
    conversation_id: Optional[str] = None,
    user_id: str = Depends(get_current_read_user_id),
    context_manager: ContextManager = Depends(get_context_manager)
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
            timestamp=t["created_at"].isoformat() if t.get("created_at") and hasattr(t["created_at"], "isoformat") else (str(t["created_at"]) if t.get("created_at") else ""),
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
    orchestrator: OrchestratorV2 = Depends(get_orchestrator)
):
    """
    Suggest a proactive AI action (goes through ESL)
    
    This endpoint allows the system to proactively suggest actions,
    but ESL guards against manipulation.
    
    Args:
        suggestion_type: Type of suggestion (summary, reminder, etc.)
        suggestion_content: The suggested content
        rationale: Why the system is suggesting this
        user_id: Current user ID
        orchestrator: Orchestrator instance
    
    Returns:
        ESL decision and execution result
        
    Example:
        POST /api/chat/proactive
        {
            "suggestion_type": "daily_summary",
            "suggestion_content": "Here's your day summary...",
            "rationale": "End of work day detected"
        }
    """
    try:
        result = await orchestrator.suggest_proactive_action(
            user_id=user_id,
            suggestion_type=suggestion_type,
            suggestion_content=suggestion_content,
            rationale=rationale
        )
        
        return {
            "status": "success" if result["executed"] else "blocked",
            "executed": result["executed"],
            "esl_decision": result["decision"].model_dump(),
            "transparency": result["transparency"],
            "timestamp": result["timestamp"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing proactive suggestion: {str(e)}"
        )


@router.delete("/history", response_model=dict)
async def clear_conversation_history(
    user_id: str = Depends(get_current_user_id),
    confirm: bool = False,
    context_manager: ContextManager = Depends(get_context_manager)
):
    """
    Clear conversation history (in-memory)
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must confirm deletion by setting confirm=True"
        )
    
    try:
        deleted_count = await context_manager.clear_semantic_memory(str(user_id))
        
        return {
            "status": "success",
            "message": "Conversation history cleared",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing history: {str(e)}"
        )
