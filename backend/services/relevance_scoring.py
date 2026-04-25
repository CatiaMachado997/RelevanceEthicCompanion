"""
Relevance Scoring Engine - V2 Core Logic

THIS IS 100% YOUR CUSTOM ALGORITHM - Not from any base model.

The intelligence is in:
- Multi-factor scoring (query match, goal alignment, timeliness, recency)
- Source credibility vetting
- Manipulation detection integration
- Value conflict detection
- ESL ethical guardrails

Base models (Groq/Llama) don't do any of this.
"""

from typing import List, Optional, Dict, Any
import re
from datetime import datetime
import logging

from models.relevance import CandidateItem, ScoredItem, RelevanceContext
from esl.engine import EthicalSafeguardLayer
from utils.db import get_db

logger = logging.getLogger(__name__)


def get_user_relevance_weights(user_id: str) -> Dict[str, float]:
    """
    Fetch user-configured relevance weight multipliers from the DB,
    then apply any feedback-learned adjustments from relevance_adjustments.

    Returns a dict with the 4 weight keys; falls back to 1.0 for any missing value.
    """
    defaults = {
        "weight_goal_alignment": 1.0,
        "weight_time_sensitivity": 1.0,
        "weight_personal_values": 1.0,
        "weight_context_relevance": 1.0,
    }
    # Map relevance_adjustments.signal_type → weight key
    _signal_to_weight = {
        "goal_alignment": "weight_goal_alignment",
        "timeliness": "weight_time_sensitivity",
        "personal_values": "weight_personal_values",
        "query_match": "weight_context_relevance",
    }
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # C.2 — user-configured weights
                cur.execute(
                    """
                    SELECT weight_goal_alignment, weight_time_sensitivity,
                           weight_personal_values, weight_context_relevance
                    FROM user_settings
                    WHERE user_id = %s
                    """,
                    (str(user_id),),
                )
                row = cur.fetchone()
                if row:
                    keys = list(defaults.keys())
                    weights = {
                        keys[i]: (row[i] if row[i] is not None else 1.0)
                        for i in range(4)
                    }
                else:
                    weights = dict(defaults)

                # C.1.3 — feedback-learned multipliers from relevance_adjustments
                cur.execute(
                    "SELECT signal_type, multiplier FROM relevance_adjustments WHERE user_id = %s",
                    (str(user_id),),
                )
                for signal_type, multiplier in cur.fetchall():
                    weight_key = _signal_to_weight.get(signal_type)
                    if weight_key and multiplier is not None:
                        weights[weight_key] = weights[weight_key] * float(multiplier)
                        logger.debug(
                            f"[RelevanceScoring] Applied feedback adjustment "
                            f"{signal_type}×{multiplier:.2f} → {weight_key}={weights[weight_key]:.2f} "
                            f"for user {user_id}"
                        )

        return weights
    except Exception as exc:
        logger.warning(f"Could not fetch relevance weights for {user_id}: {exc}")
    return defaults


class RelevanceScoringEngine:
    """
    Custom relevance scoring algorithm

    Scores candidates using YOUR custom heuristics:
    - 50%: Direct query match (highest priority)
    - 30%: Keyword overlap with active goals
    - 15%: Timeliness (proximity to calendar events)
    - 5%: Recency (relation to recent topics)

    Plus ethical filtering via ESL.
    """

    def __init__(self, esl_engine: EthicalSafeguardLayer):
        """
        Initialize relevance scoring engine

        Args:
            esl_engine: ESL instance for ethical guardrails
        """
        self.esl = esl_engine

        # Source credibility blocklists (YOUR CURATION)
        self.untrusted_sources = [
            "clickbait.com",
            "spam-site.net",
            # Add more as needed
        ]

        logger.info("✅ RelevanceScoringEngine initialized")

    async def score_candidates(
        self, user_id: str, candidates: List[CandidateItem], context: RelevanceContext
    ) -> List[ScoredItem]:
        """
        Score and rank candidates by relevance

        THIS IS YOUR ALGORITHM - Not LLM intelligence

        Args:
            user_id: Supabase UUID
            candidates: Items to score
            context: Relevance context (goals, events, query, etc.)

        Returns:
            List of scored items, sorted by relevance score (highest first)
        """
        scored_items: List[ScoredItem] = []

        # Load user-tunable weight multipliers (Task 7.3)
        weights = get_user_relevance_weights(user_id)

        for candidate in candidates:
            # Check ethical safety FIRST (YOUR ESL INTEGRATION)
            safety_check = await self.esl.check_content_safety(
                content=candidate.content,
                user_id=user_id,
                content_type=candidate.type.value,
            )

            if safety_check.blocked:
                # Don't show this item - ESL blocked it
                logger.debug(f"❌ Blocked item {candidate.id}: {safety_check.reason}")
                continue

            # Calculate relevance score (YOUR ALGORITHM)
            score, breakdown = self._calculate_relevance_score(
                candidate, context, weights
            )

            # Generate explanation (YOUR TRANSPARENCY LOGIC)
            explanation = self._generate_explanation(candidate, context, breakdown)

            scored_items.append(
                ScoredItem(
                    item=candidate,
                    relevance_score=score,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    ethical_flags=safety_check.violated_values,
                    confidence=safety_check.confidence,
                )
            )

        # Sort by score (YOUR RANKING)
        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)

        logger.info(
            f"✅ Scored {len(scored_items)}/{len(candidates)} candidates for user {user_id}"
        )
        return scored_items

    def _calculate_relevance_score(
        self,
        candidate: CandidateItem,
        context: RelevanceContext,
        weights: Optional[Dict[str, float]] = None,
    ) -> tuple[float, Dict[str, float]]:
        """
        Calculate multi-factor relevance score

        YOUR SCORING ALGORITHM:
        - 50 points: Direct query match
        - 30 points: Goal overlap  (scaled by weight_goal_alignment)
        - 15 points: Timeliness    (scaled by weight_time_sensitivity)
        - 5 points:  Recency       (scaled by weight_personal_values)
        - query_match scaled by    weight_context_relevance

        Args:
            candidate: Item to score
            context: Relevance context
            weights: User-tunable multipliers (0-2x each)

        Returns:
            (total_score, score_breakdown)
        """
        if weights is None:
            weights = {}

        breakdown = {}
        total_score = 0.0

        # Factor 1: Direct query match (50 points max)
        # Scaled by weight_context_relevance
        if context.query:
            query_score = self._score_query_match(
                candidate.content, candidate.title or "", context.query
            )
            query_score *= weights.get("weight_context_relevance", 1.0)
            breakdown["query_match"] = query_score
            total_score += query_score
        else:
            breakdown["query_match"] = 0.0

        # Factor 2: Goal overlap (30 points max)
        # Scaled by weight_goal_alignment
        goal_score = self._score_goal_overlap(
            candidate.content, candidate.title or "", context.active_goals
        )
        goal_score *= weights.get("weight_goal_alignment", 1.0)
        breakdown["goal_overlap"] = goal_score
        total_score += goal_score

        # Factor 3: Timeliness (15 points max)
        # Scaled by weight_time_sensitivity
        timeliness_score = self._score_timeliness(candidate, context.upcoming_events)
        timeliness_score *= weights.get("weight_time_sensitivity", 1.0)
        breakdown["timeliness"] = timeliness_score
        total_score += timeliness_score

        # Factor 4: Recency (5 points max)
        # Scaled by weight_personal_values
        recency_score = self._score_recency(candidate.content, context.recent_topics)
        recency_score *= weights.get("weight_personal_values", 1.0)
        breakdown["recency"] = recency_score
        total_score += recency_score

        # Penalty: Untrusted source (-20 points)
        if self._is_untrusted_source(candidate.source):
            breakdown["source_penalty"] = -20.0
            total_score -= 20.0
        else:
            breakdown["source_penalty"] = 0.0

        # Ensure score is in 0-100 range
        total_score = max(0.0, min(100.0, total_score))

        return total_score, breakdown

    def _score_query_match(self, content: str, title: str, query: str) -> float:
        """
        Score how well content matches user's query

        YOUR MATCHING LOGIC - Not semantic from LLM
        Uses simple keyword matching for MVP

        Args:
            content: Item content
            title: Item title
            query: User's query

        Returns:
            Score 0-50
        """
        query_lower = query.lower()
        content_lower = content.lower()
        title_lower = title.lower()

        # Exact phrase match in title - highest score
        if query_lower in title_lower:
            return 50.0

        # Exact phrase match in content
        if query_lower in content_lower:
            return 40.0

        # Keyword matching (YOUR LOGIC)
        query_words = set(re.findall(r"\w+", query_lower))
        content_words = set(re.findall(r"\w+", content_lower))
        title_words = set(re.findall(r"\w+", title_lower))

        # Calculate overlap
        title_overlap = (
            len(query_words & title_words) / len(query_words) if query_words else 0
        )
        content_overlap = (
            len(query_words & content_words) / len(query_words) if query_words else 0
        )

        # Weight title more than content
        score = (title_overlap * 30) + (content_overlap * 20)

        return min(50.0, score)

    def _score_goal_overlap(
        self, content: str, title: str, active_goals: List[str]
    ) -> float:
        """
        Score alignment with user's active goals

        YOUR GOAL MATCHING LOGIC

        Args:
            content: Item content
            title: Item title
            active_goals: List of goal titles

        Returns:
            Score 0-30
        """
        if not active_goals:
            return 0.0

        content_lower = content.lower()
        title_lower = title.lower()

        max_score = 0.0

        for goal in active_goals:
            goal_lower = goal.lower()

            # Exact goal mention in title
            if goal_lower in title_lower:
                max_score = max(max_score, 30.0)
                continue

            # Exact goal mention in content
            if goal_lower in content_lower:
                max_score = max(max_score, 20.0)
                continue

            # Keyword overlap with goal
            goal_words = set(re.findall(r"\w+", goal_lower))
            content_words = set(re.findall(r"\w+", content_lower))
            title_words = set(re.findall(r"\w+", title_lower))

            title_overlap = (
                len(goal_words & title_words) / len(goal_words) if goal_words else 0
            )
            content_overlap = (
                len(goal_words & content_words) / len(goal_words) if goal_words else 0
            )

            score = (title_overlap * 15) + (content_overlap * 10)
            max_score = max(max_score, score)

        return min(30.0, max_score)

    def _score_timeliness(
        self, candidate: CandidateItem, upcoming_events: List[Dict[str, Any]]
    ) -> float:
        """
        Score temporal relevance (proximity to calendar events)

        YOUR TEMPORAL LOGIC

        Args:
            candidate: Item to score
            upcoming_events: Upcoming calendar events

        Returns:
            Score 0-15
        """
        if not upcoming_events:
            return 0.0

        # Check if candidate is related to any upcoming event
        content_lower = candidate.content.lower()
        title_lower = (candidate.title or "").lower()

        max_score = 0.0

        for event in upcoming_events:
            event_title = event.get("title", "").lower()
            event_start = event.get("start_time")

            # Check content overlap with event
            if event_title and (
                event_title in content_lower or event_title in title_lower
            ):
                # Score based on proximity to event
                if isinstance(event_start, str):
                    event_start = datetime.fromisoformat(
                        event_start.replace("Z", "+00:00")
                    )

                if isinstance(event_start, datetime):
                    hours_until = (
                        event_start - datetime.utcnow()
                    ).total_seconds() / 3600

                    if hours_until < 0:
                        # Event already passed
                        score = 5.0
                    elif hours_until < 1:
                        # Starting very soon
                        score = 15.0
                    elif hours_until < 24:
                        # Starting today
                        score = 10.0
                    else:
                        # Future event
                        score = 5.0

                    max_score = max(max_score, score)

        return min(15.0, max_score)

    def _score_recency(self, content: str, recent_topics: List[str]) -> float:
        """
        Score based on recent conversation topics

        YOUR RECENCY LOGIC

        Args:
            content: Item content
            recent_topics: Recently discussed topics

        Returns:
            Score 0-5
        """
        if not recent_topics:
            return 0.0

        content_lower = content.lower()

        for topic in recent_topics:
            topic_lower = topic.lower()
            if topic_lower in content_lower:
                return 5.0

        return 0.0

    def _is_untrusted_source(self, source: str) -> bool:
        """
        Check if source is on untrusted blocklist

        YOUR CURATION - Not AI-generated

        Args:
            source: Source identifier

        Returns:
            True if untrusted
        """
        source_lower = source.lower()
        return any(blocked in source_lower for blocked in self.untrusted_sources)

    def _generate_explanation(
        self,
        candidate: CandidateItem,
        context: RelevanceContext,
        breakdown: Dict[str, float],
    ) -> str:
        """
        Generate human-readable explanation of relevance score

        YOUR TRANSPARENCY LOGIC

        Args:
            candidate: Scored item
            context: Relevance context
            breakdown: Score breakdown

        Returns:
            Explanation string
        """
        reasons = []

        # Query match
        if breakdown.get("query_match", 0) > 30:
            reasons.append(f"Closely matches your search: '{context.query}'")
        elif breakdown.get("query_match", 0) > 15:
            reasons.append(f"Partially matches your search: '{context.query}'")

        # Goal overlap
        if breakdown.get("goal_overlap", 0) > 20:
            reasons.append("Strongly aligned with your active goals")
        elif breakdown.get("goal_overlap", 0) > 10:
            reasons.append("Related to your active goals")

        # Timeliness
        if breakdown.get("timeliness", 0) > 10:
            reasons.append("Relevant to your upcoming calendar events")
        elif breakdown.get("timeliness", 0) > 5:
            reasons.append("Connected to a recent event")

        # Recency
        if breakdown.get("recency", 0) > 3:
            reasons.append("Related to recent conversations")

        # Source penalty
        if breakdown.get("source_penalty", 0) < 0:
            reasons.append("⚠️ Source may be less reliable")

        if not reasons:
            reasons.append("General relevance to your interests")

        return "; ".join(reasons)
