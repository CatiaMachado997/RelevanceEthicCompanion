"""Mutable surface for ESL tuning track.

This is the ONLY file the AutoResearch agent edits for this track.
All values are threshold constants extracted from esl/rules.py.
The real ESL engine imports ESLConfig at runtime if ESL_CONFIG_PATH is set.
"""

from dataclasses import dataclass


@dataclass
class ESLConfig:
    # EngagementDetector thresholds
    engagement_score_threshold: float = 0.7     # flag if engagement_score > this
    goal_relevance_min: float = 0.3             # require goal_relevance_score >= this

    # ManipulationDetector: min signals before flagging
    manipulation_signal_threshold: int = 2

    # TimeBasedRules: quiet hours (24-hour clock)
    quiet_hours_start: int = 22
    quiet_hours_end: int = 7

    # UrgencyLevel critical: require goal_relevance_score >= this
    critical_urgency_relevance_min: float = 0.3


config = ESLConfig()
