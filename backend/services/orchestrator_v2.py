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
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from esl.models import ProposedAction, ESLDecision, ESLDecisionStatus
from esl.engine import EthicalSafeguardLayer
from esl.audit import ESLAuditLogger
from services.context_manager import ContextManager
from services.langchain_tools import create_langchain_tools
from services.feedback_processor import FeedbackProcessor
from models.context import SemanticMemoryEntry
from utils.db import get_db_connection
from config import settings

logger = logging.getLogger(__name__)

# ── Daily token tracker (in-memory, resets per day) ──────────────────────────
_DAILY_TOKEN_LIMIT = 100_000
_daily_tokens: Dict[str, Dict[str, Any]] = {}


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _check_token_warning(user_id: str, new_tokens: int) -> Optional[dict]:
    """Update daily counter and return a warning event dict if a threshold is crossed."""
    today = datetime.now().strftime("%Y-%m-%d")
    entry = _daily_tokens.get(user_id)
    if not entry or entry["date"] != today:
        _daily_tokens[user_id] = {"date": today, "used": 0, "warned_75": False, "warned_85": False}
        entry = _daily_tokens[user_id]
    entry["used"] += new_tokens
    used = entry["used"]
    remaining = max(0, _DAILY_TOKEN_LIMIT - used)
    pct = used / _DAILY_TOKEN_LIMIT
    if pct >= 0.85 and not entry["warned_85"]:
        entry["warned_85"] = True
        return {
            "event": "rate_limit_warning", "level": "high",
            "used_pct": int(pct * 100),
            "message": f"⚠️ ~15% of your daily token limit remaining (~{remaining:,} tokens). Switch to a faster model to save tokens.",
        }
    if pct >= 0.75 and not entry["warned_75"]:
        entry["warned_75"] = True
        return {
            "event": "rate_limit_warning", "level": "medium",
            "used_pct": int(pct * 100),
            "message": f"~25% of your daily token limit remaining (~{remaining:,} tokens).",
        }
    return None


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
        db_connection_factory=None,
        model: str = "llama-3.3-70b-versatile",
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

        # Initialize Groq LLM for agent (Gemini only used for embeddings)
        self.llm = ChatGroq(
            model=model,
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0.7
        )

        # ESL remains the mandatory gateway — pass llm so semantic manipulation check (E.2) works
        self.esl = EthicalSafeguardLayer(
            context_manager,
            audit_logger=ESLAuditLogger(db_connection_factory=db_connection_factory),
            llm=self.llm,
        )

        # Feedback-driven personalisation
        self.feedback_processor = FeedbackProcessor()

        # Simplified approach using direct LLM calls with context
        # (LangGraph agents would be added in future iterations)

    def _build_system_prompt(self, user_context: Dict[str, Any], adjustments: dict = None) -> str:
        """
        Create context-rich system prompt with user values and goals.

        This is where YOUR intelligence goes - not in the model.

        Args:
            user_context: Formatted user context dict from _get_user_context_text.
            adjustments: Optional feedback-derived signal multipliers
                         (e.g. {'goal_alignment': 1.3, 'query_match': 0.8}).
        """
        prompt = f"""You are an AI assistant helping {user_context['user_name']}.

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

Respond in a helpful, direct manner that aligns with the user's stated goals and values.

Tools available — only call a tool when it is clearly necessary:
- query_memory: ONLY if the user explicitly asks about a past conversation or you need specific prior context not already in this prompt
- query_calendar: ONLY if the user asks about their schedule or specific events
- web_search: ONLY if the user asks about current events, recent news, or live data after your training cutoff
- get_user_goals: ONLY if the user asks about their goals specifically
- create_note: ONLY if the user explicitly asks to save or remember something

For greetings, general questions, or anything answerable from the context above — respond directly WITHOUT calling any tools."""

        if adjustments:
            notes = []
            if adjustments.get("goal_alignment", 1.0) > 1.1:
                notes.append("User prefers responses highly aligned with their active goals.")
            if adjustments.get("query_match", 1.0) < 0.9:
                notes.append("User finds literal keyword matches less useful; prioritise goal relevance.")
            if notes:
                prompt += "\nPersonalisation signals from user feedback:\n" + "\n".join(f"- {n}" for n in notes)

        return prompt

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

    async def _get_conversation_history(
        self, user_id: str, limit: int = 20, conversation_id: str = None
    ) -> List:
        """
        Retrieve recent conversation turns from PostgreSQL (M1), sorted chronologically.

        Falls back to empty list if DB is unavailable.

        Returns a list of LangChain HumanMessage/AIMessage objects ready to pass
        to the LLM so it has full conversational context.
        If conversation_id is provided, only turns from that conversation are returned.
        """
        try:
            turns = await self.context_manager.get_conversation_history(
                user_id, limit=limit, conversation_id=conversation_id
            )
            history = []
            for turn in turns:
                content = turn.get('content') or ''
                if not content:
                    continue
                if turn['role'] == 'user':
                    history.append(HumanMessage(content=content))
                elif turn['role'] == 'assistant':
                    history.append(AIMessage(content=content))
            return history
        except Exception as e:
            logger.warning(f"Could not retrieve conversation history: {e}")
            return []

    def _get_llm_with_tools(self, user_id: str):
        """Return LLM bound to user-specific tools, plus a name→tool map."""
        tools = create_langchain_tools(
            context_manager=self.context_manager,
            user_id=user_id,
            tavily_client=self.tavily_client,
            relevance_engine=self.relevance_engine,
        )
        tool_map = {t.name: t for t in tools}
        if tools:
            return self.llm.bind_tools(tools), tool_map
        return self.llm, tool_map

    async def _execute_tool_call(self, tool_call: dict, user_id: str, tool_map: dict = None) -> str:
        """Execute a single tool call and return its string result.

        Args:
            tool_call: Dict with 'name', 'args', and 'id' keys from the LLM response.
            user_id: Current user ID (used as fallback if tool_map is not provided).
            tool_map: Pre-built name→tool mapping from _get_llm_with_tools.
                      If omitted, tools are re-created (legacy fallback).
        """
        if tool_map is None:
            # Fallback: rebuild tool map (avoids breaking any external callers)
            tools = create_langchain_tools(
                context_manager=self.context_manager,
                user_id=user_id,
                tavily_client=self.tavily_client,
                relevance_engine=self.relevance_engine,
            )
            tool_map = {t.name: t for t in tools}
        tool = tool_map.get(tool_call['name'])
        if not tool:
            return f"Unknown tool: {tool_call['name']}"
        try:
            result = await tool._arun(**tool_call['args'])
            return str(result)
        except Exception as e:
            logger.error(f"Tool {tool_call['name']} failed: {e}")
            return f"Tool error: {e}"

    async def handle_user_message(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
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
            try:
                adjustments = await self.feedback_processor.get_user_adjustments(user_id)
            except Exception:
                adjustments = {}
            system_prompt = self._build_system_prompt(user_context, adjustments=adjustments)

            # Step 2: Call Groq LLM (stateless text generation)
            logger.info(f"Generating response for user {user_id}: {message[:50]}...")

            # Retrieve recent conversation history so the LLM has full context
            conversation_history = await self._get_conversation_history(
                user_id, conversation_id=conversation_id
            )

            # Build messages: system prompt + prior turns + current user message
            messages = [
                SystemMessage(content=system_prompt),
                *conversation_history,
                HumanMessage(content=message)
            ]

            # Agent loop: allow up to 5 tool-call rounds before final text response
            llm_with_tools, tool_map = self._get_llm_with_tools(user_id)
            MAX_TOOL_ROUNDS = 5
            response = None
            for _ in range(MAX_TOOL_ROUNDS):
                response = await llm_with_tools.ainvoke(messages)
                if not getattr(response, 'tool_calls', None):
                    break
                messages.append(response)
                for tc in response.tool_calls:
                    tool_result = await self._execute_tool_call(tc, user_id, tool_map=tool_map)
                    messages.append(ToolMessage(content=tool_result, tool_call_id=tc['id']))

            generated_response = response.content if response else ""

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
            await self.context_manager.store_conversation_turn(
                user_id, 'user', message, conversation_id=conversation_id
            )

            # Auto-title conversation on first message
            if conversation_id:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT COUNT(*) as cnt FROM conversation_turns WHERE conversation_id = %s",
                                (conversation_id,)
                            )
                            row = cur.fetchone()
                            if row['cnt'] <= 1:  # first message
                                title = message[:60] + ("\u2026" if len(message) > 60 else "")
                                cur.execute(
                                    "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s",
                                    (title, conversation_id)
                                )
                except Exception as e:
                    logger.warning(f"Could not auto-title conversation: {e}")

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
                await self.context_manager.store_conversation_turn(
                    user_id, 'assistant', assistant_content, conversation_id=conversation_id
                )

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
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Yield SSE event dicts from the Groq LLM response.

        Emits tool_use / tool_result events before text tokens so the frontend
        can show activity indicators.  ESL runs in advisory mode after streaming
        completes — the user always receives a response.

        Yields dicts:
            {"event": "tool_use",    "tool": "web_search"}
            {"event": "tool_result", "tool": "web_search"}
            {"event": "token",       "token": "Hello"}
            {"event": "done"}
        """
        user_context = await self._get_user_context_text(user_id)
        try:
            adjustments = await self.feedback_processor.get_user_adjustments(user_id)
        except Exception:
            adjustments = {}
        system_prompt = self._build_system_prompt(user_context, adjustments=adjustments) or "You are a helpful assistant."
        conversation_history = await self._get_conversation_history(
            user_id, conversation_id=conversation_id
        )

        messages = [
            SystemMessage(content=system_prompt),
            *conversation_history,
            HumanMessage(content=message)
        ]

        llm_with_tools, tool_map = self._get_llm_with_tools(user_id)

        full_response = ""
        try:
            # Tool rounds (non-streaming; tool results must be complete before next call)
            tool_calls_made = False
            final_response = None
            for _ in range(5):
                response = await llm_with_tools.ainvoke(messages)
                if not getattr(response, 'tool_calls', None):
                    final_response = response  # save — avoids a second LLM call
                    break
                tool_calls_made = True
                messages.append(response)
                for tc in response.tool_calls:
                    yield {"event": "tool_use", "tool": tc['name']}
                    result = await self._execute_tool_call(tc, user_id, tool_map=tool_map)
                    yield {"event": "tool_result", "tool": tc['name']}
                    messages.append(ToolMessage(content=result, tool_call_id=tc['id']))

            # Produce the final textual response
            if final_response and final_response.content:
                # Use the response we already have — avoids a redundant second LLM call
                full_response = final_response.content
                yield {"event": "token", "token": full_response}
            else:
                # Either no tools were called and ainvoke returned empty content,
                # or 5 tool rounds exhausted without a text response.
                # Force a text reply using the unbound LLM (no tool_call chunks).
                async for chunk in self.llm.astream(messages):
                    if chunk.content:
                        full_response += chunk.content
                        yield {"event": "token", "token": chunk.content}

        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ("rate_limit_exceeded", "Rate limit", "429", "TPD", "tokens per day", "RateLimitError")):
                retry_match = re.search(r'try again in ([\w\d .]+?)\.?(?:\s|$)', err_str, re.IGNORECASE)
                raw = retry_match.group(1).strip() if retry_match else "a few minutes"
                # Format "22m43.391999999s" → "22m 43s"
                m = re.match(r'(\d+)m([\d.]+)s', raw)
                retry_after = f"{m.group(1)}m {int(float(m.group(2)))}s" if m else raw
                yield {
                    "event": "rate_limit_exceeded",
                    "retry_after": retry_after,
                    "message": f"Daily token limit reached. Try again in {retry_after}, or switch to a faster model like Llama 3.1 8B.",
                }
                yield {"event": "done"}
                return
            raise

        # Emit token warning if approaching daily limit
        estimated = _estimate_tokens(message) + _estimate_tokens(full_response)
        warning = _check_token_warning(user_id, estimated)
        if warning:
            yield warning

        yield {"event": "done"}

        # Post-stream: store conversation + run ESL advisory (non-blocking)
        await self._post_stream_store(user_id, message, full_response, conversation_id=conversation_id)

    async def _post_stream_store(
        self,
        user_id: str,
        user_msg: str,
        assistant_msg: str,
        conversation_id: str = None,
    ):
        """Store conversation turns in M1+M2 and run ESL in advisory mode."""
        try:
            await self.context_manager.store_conversation_turn(
                user_id, 'user', user_msg, conversation_id=conversation_id
            )
            # Auto-title conversation on first message
            if conversation_id:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT COUNT(*) as cnt FROM conversation_turns WHERE conversation_id = %s",
                                (conversation_id,)
                            )
                            row = cur.fetchone()
                            if row['cnt'] <= 1:  # first message
                                title = user_msg[:60] + ("\u2026" if len(user_msg) > 60 else "")
                                cur.execute(
                                    "UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s",
                                    (title, conversation_id)
                                )
                except Exception as e:
                    logger.warning(f"Could not auto-title conversation: {e}")
            await self.context_manager.store_conversation_turn(
                user_id, 'assistant', assistant_msg, conversation_id=conversation_id
            )
            for entry in [
                SemanticMemoryEntry(
                    user_id=user_id, content=user_msg,
                    source="conversation", metadata={"role": "user"}
                ),
                SemanticMemoryEntry(
                    user_id=user_id, content=assistant_msg,
                    source="conversation", metadata={"role": "assistant"}
                ),
            ]:
                await self.context_manager.store_semantic_memory(entry)
            # Advisory ESL — logs only, never blocks the already-delivered response
            await self.decide_action(
                user_id=user_id,
                action_type=ActionType.CHAT_RESPONSE,
                content=assistant_msg,
                urgency=UrgencyLevel.LOW,
                metadata={"advisory_only": True}
            )
        except Exception as e:
            logger.warning(f"Post-stream store failed: {e}")

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
