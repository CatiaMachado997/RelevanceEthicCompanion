"""Tests for the ESL tuning track evaluator."""

import pytest
from pathlib import Path

from autolab.tracks.esl_tuning.surface import ESLConfig
from autolab.tracks.esl_tuning.evaluator import evaluate_esl_config
from autolab.tracks.esl_tuning.benchmark import BENCHMARK_SCENARIOS, ExpectedOutcome


def test_esl_config_defaults():
    cfg = ESLConfig()
    assert 0.0 < cfg.engagement_score_threshold < 1.0
    assert 0 <= cfg.quiet_hours_start <= 23
    assert 0 <= cfg.quiet_hours_end <= 23


def test_benchmark_has_required_counts():
    approved = [s for s in BENCHMARK_SCENARIOS if s.expected == ExpectedOutcome.APPROVED]
    vetoed = [s for s in BENCHMARK_SCENARIOS if s.expected == ExpectedOutcome.VETOED]
    assert len(approved) >= 80
    assert len(vetoed) >= 30
    assert len(BENCHMARK_SCENARIOS) >= 120


def test_evaluate_returns_float_between_0_and_1(tmp_path):
    surface_path = tmp_path / "surface.py"
    surface_path.write_text(
        "from autolab.tracks.esl_tuning.surface import ESLConfig\nconfig = ESLConfig()\n"
    )
    score = evaluate_esl_config(surface_path)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_evaluate_lower_score_for_broken_config(tmp_path):
    """A config that never triggers MODIFIED scores worse than defaults."""
    default_surface = tmp_path / "default.py"
    default_surface.write_text(
        "from autolab.tracks.esl_tuning.surface import ESLConfig\nconfig = ESLConfig()\n"
    )
    # critical_urgency_relevance_min=0.0 means the urgency check never triggers
    # MODIFIED, so all 40 "unjustified critical urgency" scenarios get misclassified.
    broken_surface = tmp_path / "broken.py"
    broken_surface.write_text(
        "from autolab.tracks.esl_tuning.surface import ESLConfig\n"
        "config = ESLConfig(critical_urgency_relevance_min=0.0)\n"
    )
    default_score = evaluate_esl_config(default_surface)
    broken_score = evaluate_esl_config(broken_surface)
    assert default_score > broken_score
