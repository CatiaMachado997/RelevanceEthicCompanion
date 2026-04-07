"""ESLGateway — mandatory ESL evaluation node. Every graph path passes through this."""
import logging
from typing import Optional
from orchestrator.state import AgentState
from esl.engine import EthicalSafeguardLayer
from esl.models import ProposedAction, ActionType, UrgencyLevel
from orchestrator.nodes.context import get_context_manager
from config import settings

logger = logging.getLogger(__name__)

# Langfuse client — singleton, only created if keys are configured
_langfuse = None

# ESL singleton — cached to avoid recreating on every call
_esl: Optional[EthicalSafeguardLayer] = None


def _get_langfuse():
    global _langfuse
    if _langfuse is None and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=getattr(settings, 'LANGFUSE_HOST', 'https://cloud.langfuse.com'),
        )
    return _langfuse


def get_esl() -> EthicalSafeguardLayer:
    global _esl
    if _esl is None:
        cm = get_context_manager()
        _esl = EthicalSafeguardLayer(cm)
    return _esl


async def esl_gateway_node(state: AgentState) -> dict:
    """Evaluate proposed response through ESL. Returns updated esl_decision."""
    user_id = state.get("user_id")
    if not user_id:
        raise ValueError("esl_gateway_node: user_id missing from AgentState — cannot evaluate ESL")
    esl = get_esl()
    # content_type is required by ProposedAction — use intent as the content type
    proposed = ProposedAction(
        action_type=ActionType.CHAT_RESPONSE,
        content_type=state.get("intent", "chat_response"),  # REQUIRED field
        content=state.get("proposed_content", ""),
        urgency=UrgencyLevel.LOW,
        metadata={"advisory_only": True, "intent": state.get("intent", "chat")},
    )
    decision = await esl.evaluate_action(proposed, user_id)

    # Trace to Langfuse (non-blocking)
    try:
        lf = _get_langfuse()
        if lf:
            lf.trace(
                name="esl_decision",
                user_id=user_id,
                metadata={
                    "status": decision.status.value,
                    "reason": decision.reason,
                    "confidence": getattr(decision, "confidence", None),
                    "violated_values": decision.violated_values,
                }
            )
    except Exception as e:
        logger.warning(f"Langfuse trace failed (non-blocking): {e}")

    return {"esl_decision": decision}
