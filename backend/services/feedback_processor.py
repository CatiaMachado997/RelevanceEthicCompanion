"""
Feedback Processing Service

Collects and processes user feedback on AI responses and relevance scoring.
This data is stored for future analysis and model tuning.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4
from psycopg.types.json import Json

from utils.db import get_db_connection
from models.feedback import (
    FeedbackType,
    ItemType,
    FeedbackAnalytics,
)

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """
    Processes user feedback on content and AI responses

    Feedback Types:
    - thumbs_up: User found content helpful
    - thumbs_down: User found content unhelpful
    - not_relevant: Content didn't match user's needs
    - value_conflict: Content violated user values
    - inaccurate: Content was factually incorrect

    Item Types:
    - chat_response: AI-generated chat message
    - search_result: Web search result
    - calendar_event: Calendar event summary
    - proactive_insight: Proactive suggestion from system
    - memory_recall: Retrieved conversation history
    """

    def __init__(self):
        """Initialize feedback processor"""
        logger.info("✅ FeedbackProcessor initialized")

    async def submit_feedback(
        self,
        user_id: str,
        item_id: str,
        item_type: str,
        feedback_type: str,
        context_snapshot: Optional[Dict[str, Any]] = None,
        additional_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit user feedback on an item

        Args:
            user_id: User ID providing feedback
            item_id: ID of the item being rated
            item_type: Type of item (chat_response, search_result, etc.)
            feedback_type: Type of feedback (thumbs_up, thumbs_down, etc.)
            context_snapshot: Optional context at time of feedback
            additional_notes: Optional user notes

        Returns:
            Dict with success status and feedback ID

        Example:
            await processor.submit_feedback(
                user_id="user-123",
                item_id="response-456",
                item_type="chat_response",
                feedback_type="thumbs_up",
                context_snapshot={"active_goals": ["learn Python"]},
                additional_notes="Very helpful summary!"
            )
        """
        try:
            # Validate feedback type
            if feedback_type not in [ft.value for ft in FeedbackType]:
                raise ValueError(f"Invalid feedback_type: {feedback_type}")

            # Validate item type
            if item_type not in [it.value for it in ItemType]:
                raise ValueError(f"Invalid item_type: {item_type}")

            feedback_id = str(uuid4())

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO relevance_feedback (
                            id,
                            user_id,
                            item_type,
                            item_id,
                            feedback_type,
                            context_snapshot,
                            additional_notes,
                            timestamp
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
                        (
                            feedback_id,
                            user_id,
                            item_type,
                            item_id,
                            feedback_type,
                            Json(context_snapshot or {}),
                            additional_notes,
                            datetime.utcnow(),
                        ),
                    )

                    conn.commit()

            logger.info(
                f"✅ Feedback submitted: {feedback_type} for {item_type} "
                f"by user {user_id}"
            )

            return {
                "success": True,
                "feedback_id": feedback_id,
                "message": "Feedback recorded successfully",
            }

        except ValueError as e:
            logger.error(f"❌ Invalid feedback submission: {e}")
            return {"success": False, "error": str(e)}

        except Exception as e:
            logger.error(f"❌ Failed to submit feedback: {e}", exc_info=True)
            return {"success": False, "error": "Failed to record feedback"}

    async def get_user_feedback_history(
        self, user_id: str, limit: int = 50, item_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get feedback history for a user

        Args:
            user_id: User ID
            limit: Maximum number of records to return
            item_type: Optional filter by item type

        Returns:
            List of feedback records
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if item_type:
                        cur.execute(
                            """
                            SELECT
                                id,
                                item_type,
                                item_id,
                                feedback_type,
                                additional_notes,
                                timestamp
                            FROM relevance_feedback
                            WHERE user_id = %s AND item_type = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """,
                            (user_id, item_type, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT
                                id,
                                item_type,
                                item_id,
                                feedback_type,
                                additional_notes,
                                timestamp
                            FROM relevance_feedback
                            WHERE user_id = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """,
                            (user_id, limit),
                        )

                    rows = cur.fetchall()

                    return [
                        {
                            "id": row[0],
                            "item_type": row[1],
                            "item_id": row[2],
                            "feedback_type": row[3],
                            "additional_notes": row[4],
                            "timestamp": row[5].isoformat(),
                        }
                        for row in rows
                    ]

        except Exception as e:
            logger.error(f"❌ Failed to get feedback history: {e}")
            return []

    async def get_feedback_analytics(
        self, user_id: Optional[str] = None, days: int = 30
    ) -> FeedbackAnalytics:
        """
        Get feedback analytics (for admin or user)

        Args:
            user_id: Optional user ID to filter by (None = all users)
            days: Number of days to analyze

        Returns:
            FeedbackAnalytics object with aggregated metrics

        Example:
            analytics = await processor.get_feedback_analytics(days=7)
            print(f"Thumbs up: {analytics.thumbs_up_count}")
            print(f"Satisfaction rate: {analytics.satisfaction_rate}%")
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute(
                            """
                            SELECT
                                feedback_type,
                                COUNT(*) as count
                            FROM relevance_feedback
                            WHERE user_id = %s
                              AND timestamp > NOW() - INTERVAL '%s days'
                            GROUP BY feedback_type
                        """,
                            (user_id, days),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT
                                feedback_type,
                                COUNT(*) as count
                            FROM relevance_feedback
                            WHERE timestamp > NOW() - INTERVAL '%s days'
                            GROUP BY feedback_type
                        """,
                            (days,),
                        )

                    rows = cur.fetchall()

                    # Aggregate feedback counts
                    feedback_counts = {row[0]: row[1] for row in rows}

                    thumbs_up = feedback_counts.get("thumbs_up", 0)
                    thumbs_down = feedback_counts.get("thumbs_down", 0)
                    not_relevant = feedback_counts.get("not_relevant", 0)
                    value_conflict = feedback_counts.get("value_conflict", 0)
                    inaccurate = feedback_counts.get("inaccurate", 0)

                    total_feedback = sum(feedback_counts.values())

                    # Calculate satisfaction rate
                    if total_feedback > 0:
                        satisfaction_rate = (thumbs_up / total_feedback) * 100
                    else:
                        satisfaction_rate = 0.0

                    return FeedbackAnalytics(
                        thumbs_up_count=thumbs_up,
                        thumbs_down_count=thumbs_down,
                        not_relevant_count=not_relevant,
                        value_conflict_count=value_conflict,
                        inaccurate_count=inaccurate,
                        total_feedback=total_feedback,
                        satisfaction_rate=satisfaction_rate,
                        days_analyzed=days,
                    )

        except Exception as e:
            logger.error(f"❌ Failed to get feedback analytics: {e}")
            return FeedbackAnalytics(
                thumbs_up_count=0,
                thumbs_down_count=0,
                not_relevant_count=0,
                value_conflict_count=0,
                inaccurate_count=0,
                total_feedback=0,
                satisfaction_rate=0.0,
                days_analyzed=days,
            )

    async def get_item_feedback(
        self, item_id: str, item_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get all feedback for a specific item

        Useful for understanding how different users rated the same content.

        Args:
            item_id: Item ID
            item_type: Type of item

        Returns:
            List of feedback records for this item
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            user_id,
                            feedback_type,
                            additional_notes,
                            timestamp
                        FROM relevance_feedback
                        WHERE item_id = %s AND item_type = %s
                        ORDER BY timestamp DESC
                    """,
                        (item_id, item_type),
                    )

                    rows = cur.fetchall()

                    return [
                        {
                            "user_id": row[0],
                            "feedback_type": row[1],
                            "additional_notes": row[2],
                            "timestamp": row[3].isoformat(),
                        }
                        for row in rows
                    ]

        except Exception as e:
            logger.error(f"❌ Failed to get item feedback: {e}")
            return []

    async def get_user_adjustments(self, user_id: str) -> Dict[str, float]:
        """
        Get user-specific relevance multipliers accumulated from feedback history.

        Returns:
            Dict mapping signal_type → multiplier (e.g. {'goal_alignment': 1.3})
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT signal_type, multiplier FROM relevance_adjustments WHERE user_id = %s",
                        (str(user_id),),
                    )
                    rows = cur.fetchall()
            return (
                {row["signal_type"]: float(row["multiplier"]) for row in rows}
                if rows
                else {}
            )
        except Exception as e:
            logger.warning(f"Could not fetch relevance adjustments for {user_id}: {e}")
            return {}

    async def adjust_signal_from_feedback(
        self,
        user_id: str,
        feedback_type: str,
        item_type: str,
    ) -> None:
        """
        Nudge relevance weights based on sustained feedback patterns.

        Only adjusts when satisfaction drops below 40% over the last 30 days,
        indicating the user consistently finds responses misaligned.
        """
        try:
            analytics = await self.get_feedback_analytics(user_id=user_id, days=30)
            satisfaction = analytics.satisfaction_rate if analytics else 50.0

            if satisfaction < 40 and feedback_type == "thumbs_down":
                # User is consistently dissatisfied — boost goal alignment, reduce raw query match
                await self._upsert_adjustment(user_id, "goal_alignment", 1.3)
                await self._upsert_adjustment(user_id, "query_match", 0.8)
                logger.info(
                    f"[FeedbackProcessor] Adjusted goal_alignment→1.3, query_match→0.8 for user {user_id} "
                    f"(satisfaction={satisfaction:.0f}%)"
                )
        except Exception as e:
            logger.warning(f"Could not adjust relevance signal for {user_id}: {e}")

    async def note_esl_sensitivity_boost(
        self, user_id: str, content_category: str, increment: float = 0.1
    ) -> None:
        """
        Record a value_conflict event so the ESL becomes more cautious
        about this content category for this user.

        Writes directly to user_esl_sensitivity table (same effect as
        ESLEngine.note_user_sensitivity but accessible from the feedback service).
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO user_esl_sensitivity (user_id, content_category, sensitivity_boost)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, content_category)
                        DO UPDATE SET
                            sensitivity_boost = LEAST(user_esl_sensitivity.sensitivity_boost + %s, 1.0),
                            updated_at = NOW()
                        """,
                        (user_id, content_category, increment, increment),
                    )
                conn.commit()
            logger.info(
                f"[FeedbackProcessor] ESL sensitivity +{increment} for user={user_id} category={content_category}"
            )
        except Exception as e:
            logger.warning(f"Could not record ESL sensitivity boost for {user_id}: {e}")

    async def _upsert_adjustment(
        self, user_id: str, signal_type: str, multiplier: float
    ) -> None:
        """Insert or update a relevance_adjustments row."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO relevance_adjustments (user_id, signal_type, multiplier)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, signal_type)
                        DO UPDATE SET multiplier = %s, updated_at = NOW()
                        """,
                        (str(user_id), signal_type, multiplier, multiplier),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to upsert relevance adjustment: {e}")


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_feedback_processor():
        """Test feedback processor"""
        processor = FeedbackProcessor()

        print("\n" + "=" * 60)
        print("FEEDBACK PROCESSOR TEST")
        print("=" * 60)

        # Test user ID
        test_user_id = "00000000-0000-0000-0000-000000000000"

        # Submit feedback
        print("\n1. Submitting feedback...")
        result = await processor.submit_feedback(
            user_id=test_user_id,
            item_id="test-response-123",
            item_type="chat_response",
            feedback_type="thumbs_up",
            context_snapshot={
                "active_goals": ["learn Python"],
                "query": "What should I focus on today?",
            },
            additional_notes="Very helpful response!",
        )
        print(f"   Result: {result}")

        # Get feedback history
        print("\n2. Getting feedback history...")
        history = await processor.get_user_feedback_history(
            user_id=test_user_id, limit=10
        )
        print(f"   Found {len(history)} feedback records")
        if history:
            print(f"   Latest: {history[0]}")

        # Get analytics
        print("\n3. Getting feedback analytics...")
        analytics = await processor.get_feedback_analytics(
            user_id=test_user_id, days=30
        )
        print(f"   Thumbs up: {analytics.thumbs_up_count}")
        print(f"   Thumbs down: {analytics.thumbs_down_count}")
        print(f"   Satisfaction rate: {analytics.satisfaction_rate:.1f}%")

        print("\n✅ Feedback processor test complete!")

    asyncio.run(test_feedback_processor())
