"""
Ethical Safeguard Layer (ESL)

The Heart and Conscience of Ethic Companion

This module is MANDATORY for all user-facing actions.
No notification, no content generation, no proactive action
can bypass the ESL.

Core Principles:
1. User Well-being is Primary Metric
2. User Control is Crucial
3. Commitment to Non-Manipulation
4. Continuous Research and Alignment
"""

from .engine import EthicalSafeguardLayer
from .models import ProposedAction, UserValue, ESLDecision, ESLDecisionStatus
from .audit import ESLAuditLogger

__all__ = [
    "EthicalSafeguardLayer",
    "ProposedAction",
    "UserValue",
    "ESLDecision",
    "ESLDecisionStatus",
    "ESLAuditLogger",
]
