"""Evaluator for the prompt optimisation experiment track.

Runs 30 synthetic test conversations through the Orchestrator prompt
and scores each with a judge LLM call.  Returns the mean score [0, 1]
or None when the Groq API key is unavailable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 30 synthetic test conversations
# Each entry is (user_message, expected_theme) — judge checks alignment.
# ---------------------------------------------------------------------------
TEST_CONVERSATIONS = [
    ("Help me plan my week", "scheduling"),
    ("What should I focus on today?", "prioritisation"),
    ("I feel overwhelmed by tasks", "wellbeing"),
    ("Summarise my recent goals", "goals"),
    ("Set a reminder for my meeting", "reminder"),
    ("How am I progressing on my project?", "progress"),
    ("I want to stop checking social media", "boundary"),
    ("What are my values?", "values"),
    ("Help me write a work summary", "productivity"),
    ("I need to make a difficult decision", "decision"),
    ("Remind me about my doctor appointment", "health"),
    ("What tasks are overdue?", "tasks"),
    ("I want to learn a new skill", "learning"),
    ("Help me track my habit", "habit"),
    ("What did I discuss last week?", "memory"),
    ("I'm stressed about a deadline", "stress"),
    ("Celebrate a small win with me", "positivity"),
    ("What are my priorities?", "prioritisation"),
    ("Help me set a boundary with a colleague", "boundary"),
    ("Draft an email response", "productivity"),
    ("How can I improve my focus?", "wellbeing"),
    ("What should I delegate?", "delegation"),
    ("Summarise my meeting notes", "productivity"),
    ("I want to review my week", "reflection"),
    ("Help me prepare for a presentation", "preparation"),
    ("What is my biggest challenge right now?", "reflection"),
    ("I need a break, what do you suggest?", "wellbeing"),
    ("Track my mood today", "mood"),
    ("What have I accomplished this month?", "progress"),
    ("Help me say no to a request", "boundary"),
]


def _load_surface(surface_path: Path) -> Optional[ModuleType]:
    """Dynamically load surface.py as a module."""
    try:
        spec = importlib.util.spec_from_file_location("prompt_opt_surface", surface_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[arg-type]
        return module
    except Exception as e:
        logger.warning(f"Failed to load surface: {e}")
        return None


def _cache_key(system_prompt: str, user_message: str) -> str:
    return hashlib.sha256(f"{system_prompt}||{user_message}".encode()).hexdigest()


def _judge_response(
    user_message: str,
    assistant_response: str,
    expected_theme: str,
    judge_prompt: str,
    groq_client,
    judge_model: str,
    judge_temperature: float,
) -> float:
    """Ask a judge LLM to score the assistant response 0.0–1.0."""
    prompt = (
        f"{judge_prompt}\n\n"
        f"User message: {user_message}\n"
        f"Expected theme: {expected_theme}\n"
        f"Assistant response: {assistant_response}\n\n"
        "Score the response from 0.0 (poor) to 1.0 (excellent) based on "
        "helpfulness, alignment with expected theme, and ethical tone. "
        "Respond with ONLY a float number between 0.0 and 1.0."
    )
    try:
        result = groq_client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=judge_temperature,
            max_tokens=10,
        )
        text = result.choices[0].message.content.strip()
        score = float(text)
        return max(0.0, min(1.0, score))
    except (ValueError, IndexError, AttributeError) as e:
        logger.warning(f"Judge scoring failed: {e}")
        return 0.5  # neutral fallback


def evaluate_prompts(surface_path: Path) -> Optional[float]:
    """Evaluate the prompts in surface_path.

    Returns the mean judge score across 30 test conversations,
    or None if the Groq API key is unavailable or surface fails to load.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.info("GROQ_API_KEY not set — skipping prompt evaluation")
        return None

    surface = _load_surface(surface_path)
    if surface is None:
        logger.warning("Could not load surface module")
        return None

    try:
        system_prompt = surface.ORCHESTRATOR_SYSTEM_PROMPT
        judge_prompt = surface.ESL_EVALUATION_PROMPT
        cfg = surface.config
    except AttributeError as e:
        logger.warning(f"Surface missing required attribute: {e}")
        return None

    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq package not installed")
        return None

    client = Groq(api_key=api_key)
    model = cfg.get("model", "llama3-8b-8192")
    max_tokens = cfg.get("max_tokens", 512)
    temperature = cfg.get("temperature", 0.3)
    judge_model = cfg.get("judge_model", "llama3-8b-8192")
    judge_temperature = cfg.get("judge_temperature", 0.1)

    scores: list[float] = []
    cache: dict[str, float] = {}

    for user_message, expected_theme in TEST_CONVERSATIONS:
        key = _cache_key(system_prompt, user_message)
        if key in cache:
            scores.append(cache[key])
            continue

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            assistant_text = response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Groq API call failed for '{user_message}': {e}")
            return None

        score = _judge_response(
            user_message=user_message,
            assistant_response=assistant_text,
            expected_theme=expected_theme,
            judge_prompt=judge_prompt,
            groq_client=client,
            judge_model=judge_model,
            judge_temperature=judge_temperature,
        )
        cache[key] = score
        scores.append(score)

    if not scores:
        return None

    mean_score = sum(scores) / len(scores)
    logger.info(f"Prompt eval complete — mean score: {mean_score:.4f} over {len(scores)} conversations")
    return mean_score
