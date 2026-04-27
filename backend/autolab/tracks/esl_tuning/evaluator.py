"""ESL tuning track evaluator.

Loads surface.py, extracts ESLConfig, runs the benchmark,
and returns macro F1-score across APPROVED / VETOED / MODIFIED classes.
"""

import importlib.util
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _load_config(surface_path: Path):
    """Dynamically load ESLConfig from surface_path."""
    spec = importlib.util.spec_from_file_location("surface", surface_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.config


def _run_esl_with_config(action, config) -> str:
    """Run ESL rules against an action using the given config. Returns decision status string."""
    from esl.models import ESLDecisionStatus

    metadata = action.metadata
    engagement_metrics = ["click_rate", "time_in_app", "daily_active", "session_length", "retention_boost"]
    assistance_metrics = ["goal_relevance", "user_request", "time_saving", "clarity_improvement"]

    engagement_count = sum(1 for m in engagement_metrics if m in metadata)
    engagement_score = engagement_count / len(engagement_metrics)
    goal_relevance_score = 1.0 if any(m in metadata for m in assistance_metrics) else 0.0

    # Check engagement threshold
    if engagement_score > config.engagement_score_threshold and goal_relevance_score < config.goal_relevance_min:
        return ESLDecisionStatus.VETOED

    # Check critical urgency
    if action.urgency == "critical" and goal_relevance_score < config.critical_urgency_relevance_min:
        return ESLDecisionStatus.MODIFIED

    # Check manipulation (requires >= manipulation_signal_threshold distinct signals)
    import re
    content_lower = (action.content or "").lower()
    fomo_patterns = [r"don't miss out", r"last chance", r"everyone else", r"you're missing", r"limited time", r"act now", r"before it's gone"]
    urgency_patterns = [r"urgent(?!.*meeting)", r"act immediately", r"right now", r"can't wait"]
    guilt_patterns = [r"you should have", r"you forgot", r"you haven't", r"disappointing"]
    violations = []
    for p in fomo_patterns:
        if re.search(p, content_lower):
            violations.append(p)
    for p in urgency_patterns:
        if re.search(p, content_lower):
            violations.append(p)
    for p in guilt_patterns:
        if re.search(p, content_lower):
            violations.append(p)
    if len(violations) >= config.manipulation_signal_threshold:
        return ESLDecisionStatus.VETOED

    return ESLDecisionStatus.APPROVED


def _macro_f1(y_true: list, y_pred: list, classes: list) -> float:
    """Compute macro-averaged F1 across classes."""
    f1s = []
    for cls in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else 0.0


def evaluate_esl_config(surface_path: Path) -> Optional[float]:
    """Load surface.py, run benchmark, return macro F1 (0.0-1.0) or None on error."""
    try:
        config = _load_config(surface_path)
    except Exception as e:
        logger.error(f"Failed to load ESLConfig from {surface_path}: {e}")
        return None

    from autolab.tracks.esl_tuning.benchmark import BENCHMARK_SCENARIOS, ExpectedOutcome
    from esl.models import ESLDecisionStatus

    CLASS_MAP = {
        ExpectedOutcome.APPROVED: ESLDecisionStatus.APPROVED,
        ExpectedOutcome.VETOED: ESLDecisionStatus.VETOED,
        ExpectedOutcome.MODIFIED: ESLDecisionStatus.MODIFIED,
    }

    y_true = []
    y_pred = []
    for scenario in BENCHMARK_SCENARIOS:
        predicted = _run_esl_with_config(scenario.action, config)
        y_true.append(CLASS_MAP[scenario.expected])
        y_pred.append(predicted)

    classes = [ESLDecisionStatus.APPROVED, ESLDecisionStatus.VETOED, ESLDecisionStatus.MODIFIED]
    return _macro_f1(y_true, y_pred, classes)
