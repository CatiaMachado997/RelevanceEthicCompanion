"""
Daily Insight Route

Generates (or returns cached) a single daily proactive insight for the user.
The LLM creates a personalised suggestion based on goals, upcoming events, and values.
Result is cached per user per day in the daily_insights table.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import SecretStr

from config import settings
from utils.db import get_db
from utils.supabase_auth import get_current_read_user_id
from services.context_manager import ContextManager
from utils.weaviate_client import get_weaviate_client
from services.embedding_service import EmbeddingService

router = APIRouter(prefix="/api/insight", tags=["Insight"])
logger = logging.getLogger(__name__)


def _get_context_manager() -> ContextManager:
    try:
        wc = get_weaviate_client()
    except Exception:
        wc = None
    es = EmbeddingService(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
    return ContextManager(weaviate_client=wc, embedding_service=es)


@router.get("/daily", response_model=dict)
async def get_daily_insight(
    user_id: str = Depends(get_current_read_user_id),
):
    """
    Return today's proactive insight for the user.
    Generates a new one if none exists for today; caches for the rest of the day.
    """
    # 1. Check cache
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content FROM daily_insights WHERE user_id = %s AND date = CURRENT_DATE",
                    (str(user_id),),
                )
                row = cur.fetchone()
        if row:
            return {"insight": row["content"], "cached": True}
    except Exception as e:
        logger.warning(f"Could not read daily_insights cache: {e}")

    # 2. Generate using LLM
    if not settings.GROQ_API_KEY:
        return {
            "insight": "Set up your goals and values to receive personalised daily insights.",
            "cached": False,
        }

    try:
        ctx = _get_context_manager()

        goals = []
        events = []
        values = []

        try:
            goals = await ctx.get_active_goals(str(user_id))
        except Exception as e:
            logger.warning(f"Could not fetch goals for insight: {e}")

        try:
            events = await ctx.get_upcoming_events(str(user_id), hours_ahead=24)
        except Exception as e:
            logger.warning(f"Could not fetch events for insight: {e}")

        try:
            values = await ctx.get_user_values(str(user_id))
        except Exception as e:
            logger.warning(f"Could not fetch values for insight: {e}")

        goal_text = "\n".join(f"- {g.title}" for g in goals[:5]) or "None set yet."
        event_text = (
            "\n".join(f"- {e.title}" for e in events[:3]) or "Nothing scheduled."
        )
        value_text = "\n".join(f"- {v.value}" for v in values[:5]) or "None set yet."

        prompt = f"""You are Ethic Companion, an AI assistant that helps users act on their goals with integrity.

User's active goals:
{goal_text}

Upcoming events (next 24 h):
{event_text}

User's stated values:
{value_text}

Write one specific, actionable insight or suggestion for today. Reference concrete goals or events where possible. Be warm, direct, and under 3 sentences. Do not start with "I" or "As your"."""  # noqa: E501

        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=SecretStr(settings.GROQ_API_KEY),
            temperature=0.7,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content or ""
        content = (raw if isinstance(raw, str) else str(raw)).strip()

        if not content:
            content = "Review your active goals today and identify one small next step you can take right now."

        # 3. Cache it
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO daily_insights (user_id, content, date)
                        VALUES (%s, %s, CURRENT_DATE)
                        ON CONFLICT (user_id, date) DO UPDATE SET
                            content = EXCLUDED.content,
                            generated_at = NOW()
                        """,
                        (str(user_id), content),
                    )
        except Exception as e:
            logger.warning(f"Could not cache daily insight: {e}")

        return {"insight": content, "cached": False}

    except Exception as e:
        logger.error(f"Daily insight generation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Could not generate insight: {str(e)}"
        )
