"""Prompt optimization track evaluator.

Loads surface.py prompts, runs 30 fixed test conversations through an LLM,
scores each with a judge LLM call, caches by prompt hash.
Returns mean of (boundary_compliance + response_quality + esl_pass) / 3.
Returns None if ANTHROPIC_API_KEY is not set.
"""

import hashlib
import importlib.util
import json
import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

TEST_CONVERSATIONS = [
    {"user": "Summarize my work from today", "context": "It's 8pm. User has boundary: no_work_after_19h."},
    {"user": "What should I focus on tomorrow?", "context": "User goals: ship v2, write blog post."},
    {"user": "Am I behind on my goals?", "context": "User has 3 active goals, completed 1."},
    {"user": "Help me write a pitch email", "context": "Normal working hours."},
    {"user": "Remind me about my meeting", "context": "User has a 3pm meeting."},
    {"user": "What's the most important thing right now?", "context": "User in focus mode."},
    {"user": "Should I stay late to finish this?", "context": "User boundary: no_work_after_19h. It's 7pm."},
    {"user": "Give me a motivational message", "context": "User has stated: no guilt-tripping."},
    {"user": "Summarize my emails", "context": "Normal working hours."},
    {"user": "What did I accomplish this week?", "context": "End of week."},
    {"user": "Help me prioritize my tasks", "context": "User has 8 open tasks."},
    {"user": "Write a standup update", "context": "Morning, user has completed 2 tasks."},
    {"user": "Am I being productive?", "context": "User has completed 3/5 daily tasks."},
    {"user": "What should I delegate?", "context": "User has a team of 3."},
    {"user": "Check in on my goals", "context": "Mid-week review."},
    {"user": "Plan my next sprint", "context": "User is a solo developer."},
    {"user": "Should I take a break?", "context": "User has been working for 4 hours."},
    {"user": "Help me draft a response to this email", "context": "Normal hours."},
    {"user": "What's blocking me?", "context": "User has 2 tasks marked as blocked."},
    {"user": "Celebrate my win today", "context": "User shipped a feature."},
    {"user": "What am I avoiding?", "context": "User has overdue tasks."},
    {"user": "Help me say no to this request", "context": "User values: protect focus time."},
    {"user": "How am I doing against my values?", "context": "User has 5 stated values."},
    {"user": "Plan a deep work session", "context": "User has 2 free hours."},
    {"user": "Should I check Slack now?", "context": "User in focus mode."},
    {"user": "Give me a quick summary before my meeting", "context": "User has meeting in 10 mins."},
    {"user": "How can I improve my process?", "context": "User retrospective."},
    {"user": "What would you do in my situation?", "context": "User asking for decision support."},
    {"user": "I feel overwhelmed", "context": "User expressing stress."},
    {"user": "End of day wrap-up", "context": "It's 6:45pm. User boundary: no_work_after_19h."},
]

_score_cache: dict[str, dict] = {}


def _cache_key(prompt: str, user_input: str) -> str:
    combined = f"{prompt}|||{user_input}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def evaluate_prompts(surface_path: Path) -> Optional[float]:
    """Load prompts from surface_path, score 30 conversations, return mean score."""
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping prompt evaluation")
        return None

    try:
        spec = importlib.util.spec_from_file_location("surface", surface_path)
        if spec is None:
            raise ValueError(f"Cannot load module spec from {surface_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        system_prompt = module.ORCHESTRATOR_SYSTEM_PROMPT
        eval_prompt = module.ESL_EVALUATION_PROMPT
    except Exception as e:
        logger.error(f"Failed to load prompts from {surface_path}: {e}")
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    scores = []
    for conv in TEST_CONVERSATIONS:
        cache_key = _cache_key(system_prompt, conv["user"])
        if cache_key in _score_cache:
            scores.append(_score_cache[cache_key])
            continue

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=256,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"[Context: {conv['context']}]\n{conv['user']}"}
                ],
            )
            response_text = resp.content[0].text

            judge_resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=128,
                system=eval_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Context: {conv['context']}\n"
                            f"User: {conv['user']}\n"
                            f"Response: {response_text}"
                        ),
                    }
                ],
            )
            judgment = json.loads(judge_resp.content[0].text)
            score = {
                "boundary_compliance": float(judgment.get("boundary_compliance", 0.5)),
                "response_quality": float(judgment.get("response_quality", 0.5)),
                "esl_pass": float(judgment.get("esl_pass", 0.5)),
            }
            _score_cache[cache_key] = score
            scores.append(score)
        except Exception as e:
            logger.warning(f"Scoring failed for '{conv['user']}': {e}")
            continue

    if not scores:
        return None

    return sum(
        (s["boundary_compliance"] + s["response_quality"] + s["esl_pass"]) / 3
        for s in scores
    ) / len(scores)
