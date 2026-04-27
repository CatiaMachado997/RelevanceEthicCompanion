"""Context relevance scoring evaluator.

Runs 50 (query, expected_keywords) pairs through Weaviate and computes NDCG@5.
Returns None (SKIP) gracefully if Weaviate is not running.
"""

import importlib.util
import logging
import math
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 50 fixed test pairs: (query, list of keywords that should appear in top results)
TEST_PAIRS = [
    ("work boundary evening", ["no_work_after", "boundary", "evening"]),
    ("morning standup meeting", ["standup", "meeting", "morning"]),
    ("project deadline stress", ["deadline", "stress", "project"]),
    ("focus mode concentration", ["focus", "concentration", "deep work"]),
    ("goal progress tracking", ["goal", "progress", "milestone"]),
    ("email inbox management", ["email", "inbox", "manage"]),
    ("task prioritization", ["priority", "task", "important"]),
    ("team collaboration sync", ["team", "sync", "collaborate"]),
    ("user value boundary", ["value", "boundary", "respect"]),
    ("decision making framework", ["decision", "framework", "values"]),
    ("productivity improvement", ["productivity", "improve", "efficient"]),
    ("burnout prevention self care", ["burnout", "self-care", "rest"]),
    ("weekly review retrospective", ["review", "retrospective", "week"]),
    ("sprint planning agile", ["sprint", "agile", "plan"]),
    ("feedback response message", ["feedback", "response", "message"]),
    ("calendar schedule event", ["calendar", "schedule", "event"]),
    ("notification alert reminder", ["notification", "reminder", "alert"]),
    ("context switch interruption", ["context", "interruption", "focus"]),
    ("code review pull request", ["code", "review", "PR"]),
    ("documentation writing", ["documentation", "write", "spec"]),
    ("stakeholder communication", ["stakeholder", "communication", "update"]),
    ("data privacy protection", ["privacy", "data", "protect"]),
    ("onboarding new user", ["onboard", "user", "setup"]),
    ("performance metric KPI", ["performance", "metric", "KPI"]),
    ("conflict resolution", ["conflict", "resolution", "disagreement"]),
    ("time management schedule", ["time", "schedule", "manage"]),
    ("knowledge base search", ["knowledge", "search", "find"]),
    ("automation workflow", ["automation", "workflow", "process"]),
    ("mental model thinking", ["mental", "model", "think"]),
    ("accountability check in", ["accountability", "check", "progress"]),
    ("creative brainstorm idea", ["brainstorm", "idea", "creative"]),
    ("risk assessment project", ["risk", "assessment", "project"]),
    ("user feedback product", ["feedback", "product", "user"]),
    ("meeting notes action items", ["meeting", "notes", "action"]),
    ("learning skill development", ["learning", "skill", "develop"]),
    ("energy management flow state", ["energy", "flow", "state"]),
    ("delegation team member", ["delegate", "team", "member"]),
    ("scope creep feature", ["scope", "creep", "feature"]),
    ("technical debt refactor", ["technical", "debt", "refactor"]),
    ("release deployment ship", ["release", "deploy", "ship"]),
    ("customer interview insight", ["customer", "interview", "insight"]),
    ("revenue growth business", ["revenue", "growth", "business"]),
    ("stress anxiety wellbeing", ["stress", "anxiety", "wellbeing"]),
    ("personal values alignment", ["personal", "value", "align"]),
    ("habit routine daily", ["habit", "routine", "daily"]),
    ("problem solving debug", ["problem", "solve", "debug"]),
    ("relationship trust communication", ["relationship", "trust", "communicate"]),
    ("vision mission strategy", ["vision", "mission", "strategy"]),
    ("break rest recovery", ["break", "rest", "recover"]),
    ("reflection journal insight", ["reflection", "journal", "insight"]),
]


def _dcg(relevances: list, k: int = 5) -> float:
    return sum(
        rel / math.log2(i + 2)
        for i, rel in enumerate(relevances[:k])
    )


def _ndcg(retrieved_texts: list, expected_keywords: list, k: int = 5) -> float:
    """Compute NDCG@k. Relevance = 1 if any expected keyword appears in retrieved text."""
    gains = [
        1.0 if any(kw.lower() in r.lower() for kw in expected_keywords) else 0.0
        for r in retrieved_texts
    ]
    ideal = sorted(gains, reverse=True)
    dcg = _dcg(gains, k)
    idcg = _dcg(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def _load_config(surface_path: Path):
    spec = importlib.util.spec_from_file_location("surface", surface_path)
    if spec is None:
        raise ValueError(f"Cannot load module spec from {surface_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.config


def evaluate_context_config(surface_path: Path) -> Optional[float]:
    """Load WeaviateConfig, run 50 test pairs, return mean NDCG@5. None if Weaviate down."""
    try:
        cfg = _load_config(surface_path)
    except Exception as e:
        logger.error(f"Failed to load WeaviateConfig from {surface_path}: {e}")
        return None

    try:
        from utils.weaviate_client import get_weaviate_client
        wc = get_weaviate_client()
        if wc is None or not wc.is_ready():
            logger.info("Weaviate not ready — skipping context scoring trial")
            return None
    except Exception:
        logger.info("Weaviate unavailable — skipping context scoring trial")
        return None

    scores = []
    for query, expected_keywords in TEST_PAIRS:
        try:
            collection = wc.collections.get("ConversationMemory")
            results = collection.query.hybrid(
                query=query,
                alpha=cfg.alpha,
                limit=cfg.limit,
                return_metadata=["score"],
            )
            retrieved = [
                obj.properties.get("content", "") or obj.properties.get("text", "")
                for obj in results.objects
            ]
            scores.append(_ndcg(retrieved, expected_keywords, k=5))
        except Exception as e:
            logger.warning(f"Weaviate query failed for '{query}': {e}")
            continue

    return sum(scores) / len(scores) if scores else None
