"""
Chat API Routes

Integrates: User Input → Orchestrator → ESL → LLM → Response
All chat interactions go through ESL for ethical protection.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, UTC

from services.orchestrator_v2 import OrchestratorV2
from services.context_manager import ContextManager
from esl.models import ActionType
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

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
    """Get ContextManager instance"""
    return ContextManager()

def get_orchestrator() -> OrchestratorV2:
    """Get OrchestratorV2 instance"""
    context_manager = get_context_manager()
    return OrchestratorV2(context_manager)

@router.get("/models", response_model=List[LLMModel])
async def get_available_llm_models():
    """
    Returns a list of available LLM models.
    OrchestratorV2 uses Groq (Llama) for chat, Gemini only for embeddings.
    """
    # Return static list of Groq models used by OrchestratorV2
    return [
        LLMModel(
            id="llama-3.3-70b-versatile",
            display_name="Llama 3.3 70B Versatile",
            provider="Groq",
            context_window=32768
        )
    ]


@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
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
            message=request.message,
            context=request.context
        )

        default_reason = result.get("error", "Request failed before ESL decision")
        esl_decision = result.get("esl_decision") or {
            "status": "VETOED",
            "reason": default_reason,
            "violated_values": []
        }

        return ChatResponse(
            message=result.get("message", request.message),
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
    user_id: str = Depends(get_current_read_user_id),
    limit: int = 50,
    offset: int = 0,
    context_manager: ContextManager = Depends(get_context_manager)
):
    """
    Get conversation history from semantic memory (in-memory)
    """
    try:
        # Query in-memory semantic memory
        # semantic_memory entries store content, we need to convert them to ChatMessage
        semantic_memory_entries = await context_manager.query_semantic_memory(
            user_id=str(user_id), # semantic_memory takes str user_id
            query="", # Empty query to get all entries for user
            limit=limit,
            offset=offset
        )

        messages = []
        for entry in semantic_memory_entries:
            # Assuming semantic memory entry content is the message content
            # and metadata contains role. If not, this needs adjustment.
            role = entry.metadata.get("role", "user")
            # If the source is conversation, it usually means both user and assistant messages
            if entry.source == 'conversation':
                # For chat history, we might store user and assistant messages separately or combined
                # Here, we're assuming the semantic memory entry itself represents a chat message
                # and its metadata can tell us the role.
                # If only assistant responses are stored as 'conversation' source, this needs adjustment.
                
                # For simplicity, let's assume we store user messages directly too,
                # or that the 'query_semantic_memory' can retrieve both.
                # For now, if role is not in metadata, default to 'assistant' if it was a response
                messages.append(ChatMessage(
                    role=role,
                    content=entry.content,
                    timestamp=entry.timestamp.isoformat()
                ))
        
        # Sort messages by timestamp, as query_semantic_memory might not guarantee order
        messages.sort(key=lambda msg: msg.timestamp)
        
        return {
            "user_id": str(user_id),
            "messages": messages,
            "total_count": len(messages)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching conversation history: {str(e)}"
        )


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
