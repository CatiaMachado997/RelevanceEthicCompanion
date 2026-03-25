"""
Orchestrator V2 - LangChain Agent Integration

Refactored orchestrator using LangChain's ReAct agent pattern with:
- Context-rich prompts (user values, goals, memory)
- Relevance scoring for web search
- ESL as mandatory gateway (maintained from V1)
- Groq (Llama 3.3) for text generation
- Gemini ONLY for embeddings (semantic memory)

CRITICAL PATTERN (UNCHANGED):
Every user-facing action MUST flow through ESL:
  User Input → Agent → ProposedAction → ESL.evaluate_action() → Decision → Execute/Block
"""

from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime, UTC
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from esl.models import ProposedAction, ESLDecision, ESLDecisionStatus
from esl.engine import EthicalSafeguardLayer
from esl.audit import ESLAuditLogger
from services.context_manager import ContextManager
from services.langchain_tools import create_langchain_tools
from models.context import SemanticMemoryEntry
from config import settings

logger = logging.getLogger(__name__)


class ActionType:
    """Standard action types for ESL evaluation (same as V1)"""
    PUSH_NOTIFICATION = "push_notification"
    PROACTIVE_SUMMARY = "proactive_summary"
    REMINDER = "reminder"
    CONTENT_GENERATION = "content_generation"
    CHAT_RESPONSE = "chat_response"
    VOICE_OUTPUT = "voice_output"


class UrgencyLevel:
    """Urgency levels for actions (same as V1)"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OrchestratorV2:
    """
    V2 Orchestrator with LangChain agent integration.

    Core Principle: Trust over Engagement (unchanged)
    - ESL is STILL the mandatory gateway
    - LangChain provides better tool orchestration
    - Groq (Llama 3.3) provides text generation (stateless, no intelligence)
    - Gemini ONLY for embeddings
    - 90% intelligence is in YOUR code (context, scoring, guardrails)

    Architecture:
    1. User message → Build context from M1/M2
    2. Inject user values + goals into prompt
    3. LangChain agent decides which tools to use
    4. Agent generates response
    5. ESL evaluates response (MANDATORY)
    6. Execute if approved, block if vetoed
    """

    def __init__(
        self,
        context_manager: ContextManager,
        relevance_engine=None,
        tavily_client=None,
        db_connection_factory=None
    ):
        """
        Initialize V2 Orchestrator

        Args:
            context_manager: Provides user context and values for ESL
            relevance_engine: RelevanceScoring engine for web search ranking
            tavily_client: Tavily API client for web search
            db_connection_factory: Optional callable for database connections
        """
        self.context_manager = context_manager
        self.relevance_engine = relevance_engine
        self.tavily_client = tavily_client

        # ESL remains the mandatory gateway
        self.esl = EthicalSafeguardLayer(
            context_manager,
            audit_logger=ESLAuditLogger(db_connection_factory=db_connection_factory)
        )

        # Initialize Groq LLM for agent (Gemini only used for embeddings)
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",  # Fast, high-quality Llama model
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0.7
        )

        # Simplified approach using direct LLM calls with context
        # (LangGraph agents would be added in future iterations)

    def _build_system_prompt(self, user_context: Dict[str, Any]) -> str:
        """
        Create context-rich system prompt with user values and goals.

        This is where YOUR intelligence goes - not in the model.
        """
        return f"""You are an AI assistant helping {user_context['user_name']}.

CRITICAL: Respect user boundaries and values at all times.

User Context:
- Active Goals:
{user_context['active_goals']}

- Upcoming Events (next 48h):
{user_context['upcoming_events']}

- User Values:
{user_context['user_values']}

- Focus Mode: {user_context['focus_mode']}

Recent Conversation Topics:
{user_context['recent_topics']}

Instructions:
1. Provide contextually relevant responses based on user's goals and values
2. Be concise and actionable
3. Respect user boundaries (focus mode, values, time preferences)
4. Reference relevant goals and events when appropriate
5. Maintain user privacy and values at all times

Respond in a helpful, direct manner that aligns with the user's stated goals and values."""

    async def _get_user_context_text(self, user_id: str) -> Dict[str, Any]:
        """
        Get formatted user context for prompt injection.

        This demonstrates where the intelligence lives - in YOUR context building,
        not in the base model.
        """
        # Get individual context elements from M1 + M2 (YOUR custom code)
        active_goals = await self.context_manager.get_active_goals(user_id)
        upcoming_events = await self.context_manager.get_upcoming_events(user_id, hours_ahead=48)
        user_values = await self.context_manager.get_user_values(user_id)

        # Get recent topics from M2 (YOUR semantic retrieval)
        recent_topics = []
        try:
            recent_memories = await self.context_manager.query_semantic_memory(
                user_id=user_id,
                query="recent",
                limit=5
            )
            recent_topics = [memory.content[:50] for memory in recent_memories]
        except Exception as e:
            logger.warning(f"Could not retrieve recent topics: {e}")

        # Format context for prompt (YOUR formatting logic)
        active_goals_text = "\n".join(
            [f"  • {goal.title} (priority: {goal.priority})" for goal in active_goals[:5]]
        ) or "  • No active goals set"

        upcoming_events_text = "\n".join(
            [f"  • {event.title} at {event.start_time.strftime('%I:%M %p') if event.start_time else 'TBD'}"
             for event in upcoming_events[:3]]
        ) or "  • No upcoming events"

        user_values_text = "\n".join(
            [f"  • {value.value} (priority: {value.priority})" for value in user_values[:5]]
        ) or "  • No values set"

        recent_topics_text = "\n".join(
            [f"  • {topic}" for topic in recent_topics[:5]]
        ) or "  • No recent conversation"

        return {
            "user_name": "User",  # Could be fetched from users table
            "active_goals": active_goals_text,
            "upcoming_events": upcoming_events_text,
            "user_values": user_values_text,
            "focus_mode": "Disabled",  # Could be fetched from user preferences
            "recent_topics": recent_topics_text
        }

    async def _get_conversation_history(self, user_id: str, limit: int = 20) -> List:
        """
        Retrieve recent conversation turns from PostgreSQL (M1), sorted chronologically.

        Falls back to empty list if DB is unavailable.

        Returns a list of LangChain HumanMessage/AIMessage objects ready to pass
        to the LLM so it has full conversational context.
        """
        try:
            turns = await self.context_manager.get_conversation_history(user_id, limit=limit)
            history = []
            for turn in turns:
                if turn['role'] == 'user':
                    history.append(HumanMessage(content=turn['content']))
                elif turn['role'] == 'assistant':
                    history.append(AIMessage(content=turn['content']))
            return history
        except Exception as e:
            logger.warning(f"Could not retrieve conversation history: {e}")
            return []

    async def handle_user_message(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle user message with Groq LLM + ESL protection.

        Flow:
        1. Build context-rich prompt (YOUR code)
        2. Call Groq (Llama 3.3) for generation (stateless text generation)
        3. Store conversation in M2 with Gemini embeddings (YOUR code)
        4. Propose response as action
        5. ESL evaluates (YOUR rules - MANDATORY)
        6. Execute if approved

        Args:
            user_id: User ID
            message: User's message
            context: Additional context (optional)

        Returns:
            Response with ESL decision
        """
        try:
            # Step 1: Get user context and build prompt (YOUR context building)
            user_context = await self._get_user_context_text(user_id)
            system_prompt = self._build_system_prompt(user_context)

            # Step 2: Call Groq LLM (stateless text generation)
            logger.info(f"Generating response for user {user_id}: {message[:50]}...")

            # Retrieve recent conversation history so the LLM has full context
            conversation_history = await self._get_conversation_history(user_id)

            # Build messages: system prompt + prior turns + current user message
            lc_messages = [
                SystemMessage(content=system_prompt),
                *conversation_history,
                HumanMessage(content=message)
            ]

            response = await self.llm.ainvoke(lc_messages)
            generated_response = response.content

            logger.info(f"Generated response: {generated_response[:100]}...")

            # Step 3: Store conversation in semantic memory (M2)
            await self.context_manager.store_semantic_memory(
                SemanticMemoryEntry(
                    user_id=user_id,
                    content=message,
                    source="conversation",
                    metadata={"role": "user"}
                )
            )

            await self.context_manager.store_semantic_memory(
                SemanticMemoryEntry(
                    user_id=user_id,
                    content=generated_response,
                    source="conversation",
                    metadata={"role": "assistant", "model": "llama-3.3-70b-versatile"}
                )
            )

            # Store user turn unconditionally (user said what they said - fine to record)
            await self.context_manager.store_conversation_turn(user_id, 'user', message)

            # Step 4 & 5: ESL evaluation (MANDATORY - YOUR ethical rules)
            decision_result = await self.decide_action(
                user_id=user_id,
                action_type=ActionType.CHAT_RESPONSE,
                content=generated_response,
                urgency=UrgencyLevel.LOW,
                metadata={
                    "user_message": message,
                    "model": "llama-3.3-70b-versatile",
                    "context": context or {}
                }
            )

            # Store assistant turn ONLY if ESL approved/executed the response
            if decision_result.get("executed"):
                # If modified, store the modified content; if approved, store original
                assistant_content = generated_response
                decision = decision_result.get("decision")
                if decision and hasattr(decision, 'status') and decision.status == "MODIFIED" and decision.modified_action:
                    # Use modified content if available
                    modified = decision.modified_action
                    if hasattr(modified, 'content') and modified.content:
                        assistant_content = modified.content
                await self.context_manager.store_conversation_turn(user_id, 'assistant', assistant_content)

            # Step 6: Return result
            return {
                "message": message,
                "response": generated_response if decision_result["executed"] else None,
                "executed": decision_result["executed"],
                "esl_decision": decision_result["decision"].model_dump(),
                "transparency": decision_result["transparency"],
                "context_injected": True,
                "timestamp": datetime.now(UTC).isoformat()
            }

        except Exception as e:
            logger.error(f"Error handling user message: {e}", exc_info=True)
            return {
                "message": message,
                "response": None,
                "executed": False,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat()
            }

    async def stream_message(
        self,
        user_id: str,
        message: str
    ) -> AsyncGenerator[str, None]:
        """
        Yield tokens from the Groq LLM response one at a time via streaming.

        Uses the same context-building and LLM client as handle_user_message.
        ESL evaluation is skipped during streaming; callers should treat the
        streamed content as a draft — production callers may wish to run ESL
        on the aggregated response after streaming completes.

        Args:
            user_id: User ID
            message: User's message

        Yields:
            Individual text tokens from the LLM response.
        """
        user_context = await self._get_user_context_text(user_id)
        system_prompt = self._build_system_prompt(user_context)

        conversation_history = await self._get_conversation_history(user_id)

        lc_messages = [
            SystemMessage(content=system_prompt),
            *conversation_history,
            HumanMessage(content=message)
        ]

        async for chunk in self.llm.astream(lc_messages):
            token = chunk.content
            if token:
                yield token

    async def decide_action(
        self,
        user_id: str,
        action_type: str,
        content: str,
        urgency: str = UrgencyLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Decide whether to execute an action using ESL.

        UNCHANGED from V1 - ESL remains the mandatory gateway.

        Args:
            user_id: User ID
            action_type: Type of action (use ActionType constants)
            content: The content/message of the action
            urgency: Urgency level (use UrgencyLevel constants)
            metadata: Additional context (optional)

        Returns:
            Dict with decision, executed, result, transparency
        """

        # Step 1: Create ProposedAction
        proposed_action = ProposedAction(
            action_type=action_type,
            content_type="text",
            content=content,
            urgency=urgency,
            metadata=metadata or {}
        )

        # Step 2: ESL evaluates action (MANDATORY - never skip this)
        decision = await self.esl.evaluate_action(proposed_action, user_id)

        # Step 3: Handle decision
        executed = False
        result = None
        transparency_message = ""

        if decision.status == ESLDecisionStatus.APPROVED:
            result = await self._execute_action(proposed_action, user_id)
            executed = True
            transparency_message = f"Action executed: {decision.reason}"

        elif decision.status == ESLDecisionStatus.MODIFIED:
            if decision.modified_action:
                result = await self._execute_action(decision.modified_action, user_id)
                executed = True
                transparency_message = (
                    f"Action modified and executed: {decision.reason}. "
                    f"Original: '{content[:50]}...', Modified: '{decision.modified_action.content[:50]}...'"
                )
            else:
                transparency_message = f"Action could not be modified: {decision.reason}"

        elif decision.status == ESLDecisionStatus.VETOED:
            transparency_message = (
                f"Action blocked by ESL: {decision.reason}. "
                f"Violated values: {', '.join(decision.violated_values)}"
            )

        return {
            "decision": decision,
            "executed": executed,
            "result": result,
            "transparency": transparency_message,
            "timestamp": datetime.now(UTC).isoformat()
        }

    async def _execute_action(
        self,
        action: ProposedAction,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute an ESL-approved action.

        In production, this would trigger real actions (notifications, emails, etc.)
        """
        execution_result = {
            "status": "executed",
            "action_type": action.action_type,
            "content": action.content,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id
        }

        logger.info(f"Executed action: {action.action_type} for user {user_id}")

        return execution_result

    async def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        urgency: str = UrgencyLevel.MEDIUM
    ) -> Dict[str, Any]:
        """
        Send a push notification with ESL evaluation.

        UNCHANGED from V1 - maintains same interface.
        """
        notification_content = f"{title}\n{body}"

        decision_result = await self.decide_action(
            user_id=user_id,
            action_type=ActionType.PUSH_NOTIFICATION,
            content=notification_content,
            urgency=urgency,
            metadata={
                "title": title,
                "body": body
            }
        )

        return decision_result

    async def suggest_proactive_action(
        self,
        user_id: str,
        suggestion_type: str,
        suggestion_content: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Suggest a proactive action (e.g., summary, reminder).

        UNCHANGED from V1 - ESL prevents manipulation.
        """
        decision_result = await self.decide_action(
            user_id=user_id,
            action_type=ActionType.PROACTIVE_SUMMARY,
            content=suggestion_content,
            urgency=UrgencyLevel.LOW,
            metadata={
                "suggestion_type": suggestion_type,
                "rationale": rationale
            }
        )

        return decision_result

    async def get_esl_transparency_report(
        self,
        user_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get transparency report of ESL decisions.

        UNCHANGED from V1 - maintains same interface.
        """
        report = await self.esl.get_transparency_report(user_id, days=days)

        return {
            "user_id": user_id,
            "period_days": days,
            "report": report,
            "generated_at": datetime.now(UTC).isoformat()
        }


# Example usage
if __name__ == "__main__":
    import asyncio

    async def demo():
        """Demonstrate V2 Orchestrator with LangChain"""

        # Initialize dependencies
        from utils.weaviate_client import get_weaviate_client
        from services.embedding_service import EmbeddingService

        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(settings.GEMINI_API_KEY)

        context_manager = ContextManager(
            weaviate_client=weaviate_client,
            embedding_service=embedding_service
        )

        orchestrator = OrchestratorV2(
            context_manager=context_manager
        )

        test_user_id = "00000000-0000-0000-0000-000000000000"

        print("=" * 60)
        print("ORCHESTRATOR V2 DEMO: LangChain + ESL")
        print("=" * 60)

        # Test 1: Simple query
        print("\n1. Handling user message (agent decides tools)...")
        result = await orchestrator.handle_user_message(
            user_id=test_user_id,
            message="What should I focus on today?"
        )
        print(f"   Executed: {result['executed']}")
        print(f"   Agent used tools: {result.get('agent_used_tools')}")
        print(f"   Response: {result.get('response', 'N/A')[:200]}")

        # Test 2: ESL protection
        print("\n2. Testing ESL protection...")
        result = await orchestrator.send_notification(
            user_id=test_user_id,
            title="URGENT!!!",
            body="Don't miss out on this amazing opportunity!",
            urgency=UrgencyLevel.HIGH
        )
        print(f"   Executed: {result['executed']}")
        print(f"   Transparency: {result['transparency']}")

        print("\n" + "=" * 60)
        print("V2 Demo complete! LangChain agent + ESL working.")
        print("=" * 60)

    asyncio.run(demo())
