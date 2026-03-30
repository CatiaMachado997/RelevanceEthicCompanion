"""
Relevance Engine

Detects when the user may need assistance (e.g., an event starting soon)
and proposes a proactive, ESL-checked action via the Orchestrator.
"""

from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime, timedelta

from services.context_manager import ContextManager
# OrchestratorV2, ActionType, UrgencyLevel imported lazily inside scan_upcoming_events()
from services.llm_service_legacy import LLMService


class RelevanceEngine:
    """
    Minimal relevance engine that detects upcoming events within a time window
    and proposes a proactive summary to the user via the ESL gateway.
    """

    def __init__(self, context_manager: ContextManager, llm: LLMService | None = None):
        self.context_manager = context_manager
        self.llm = llm or LLMService()

    async def scan_upcoming_events(
        self,
        user_id: str,
        window_minutes: int = 15,
        hours_ahead: int = 2,
        orchestrator=None,
    ) -> List[Dict[str, Any]]:
        """
        Scan for events starting within the next window and propose summaries.

        Args:
            user_id: User ID
            window_minutes: Time window to flag events as imminent
            hours_ahead: How far ahead to fetch events from storage
            orchestrator: Optional orchestrator instance; if not provided, one will be created

        Returns:
            List of ESL decision results for proposed actions
        """
        # Get events up to a few hours ahead
        events = await self.context_manager.get_upcoming_events(user_id, hours_ahead=hours_ahead)
        now = datetime.utcnow()
        window = now + timedelta(minutes=window_minutes)

        # Prepare orchestrator if not provided
        if orchestrator is None:
            from services.orchestrator_v2 import OrchestratorV2  # lazy import
            orchestrator = OrchestratorV2(self.context_manager)
        orch = orchestrator

        results: List[Dict[str, Any]] = []
        for ev in events:
            # Events are Pydantic models; access start_time/end_time
            start = ev.start_time if isinstance(ev.start_time, datetime) else datetime.fromisoformat(ev.start_time)

            # Only consider events starting within the window (and in the future)
            if now <= start <= window:
                summary = await self.llm.summarize_event(ev.title, ev.description, context={"event": ev.model_dump()})
                metadata = {
                    "event_id": ev.id,
                    "source": ev.source,
                    "start_time": start.isoformat(),
                    "rationale": "Event starting soon",
                    "goal_relevance": True,
                }

                decision = await orch.suggest_proactive_action(
                    user_id=user_id,
                    suggestion_type="event_summary",
                    suggestion_content=summary,
                    rationale="Upcoming calendar event detected",
                )

                # Attach metadata for observability
                decision["metadata"] = metadata
                results.append(decision)

        return results
