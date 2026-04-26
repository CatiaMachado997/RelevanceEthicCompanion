"""Tests for the hill-climbing runner engine."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from autolab.runner import HillClimbingRunner, TrialOutcome


def _make_runner(tmp_path, evaluator_scores):
    """Helper: runner with a mock evaluator that returns scores in sequence."""
    score_iter = iter(evaluator_scores)

    def mock_evaluate(surface_path: Path):
        return next(score_iter)

    obsidian = MagicMock()
    runner = HillClimbingRunner(
        track_name="test_track",
        surface_path=tmp_path / "surface.py",
        program_md_path=tmp_path / "program.md",
        evaluate_fn=mock_evaluate,
        obsidian_client=obsidian,
        budget_secs=1,
        anthropic_api_key="test-key",
    )
    # Write a dummy surface file
    (tmp_path / "surface.py").write_text("# surface\nVALUE = 1\n")
    (tmp_path / "program.md").write_text("# program\nOptimize VALUE.\n")
    return runner, obsidian


def test_runner_keeps_improvement(tmp_path):
    runner, obsidian = _make_runner(tmp_path, [0.80, 0.85])
    runner.baseline_score = 0.80

    # Mock the LLM diff proposal to increment VALUE
    with patch.object(runner, "_propose_diff", return_value="--- a/surface.py\n+++ b/surface.py\n@@ -1,2 +1,2 @@\n # surface\n-VALUE = 1\n+VALUE = 2\n"):
        outcome = runner.run_one_trial(trial_num=1)

    assert outcome == TrialOutcome.WIN
    assert runner.baseline_score == pytest.approx(0.85)
    obsidian.log_result.assert_called_once()
    obsidian.update_best.assert_called_once()
    # Surface file should reflect the change
    assert "VALUE = 2" in (tmp_path / "surface.py").read_text()


def test_runner_reverts_regression(tmp_path):
    runner, obsidian = _make_runner(tmp_path, [0.80, 0.75])
    runner.baseline_score = 0.80
    original_content = (tmp_path / "surface.py").read_text()

    with patch.object(runner, "_propose_diff", return_value="--- a/surface.py\n+++ b/surface.py\n@@ -1,2 +1,2 @@\n # surface\n-VALUE = 1\n+VALUE = 0\n"):
        outcome = runner.run_one_trial(trial_num=1)

    assert outcome == TrialOutcome.LOSS
    assert runner.baseline_score == pytest.approx(0.80)  # unchanged
    # Surface file should be reverted
    assert (tmp_path / "surface.py").read_text() == original_content


def test_runner_skips_on_none_score(tmp_path):
    """Evaluator returning None (e.g. Weaviate down) -> skip trial, don't revert."""
    score_iter = iter([None])

    def mock_evaluate(surface_path: Path):
        return next(score_iter)

    obsidian = MagicMock()
    runner = HillClimbingRunner(
        track_name="test_track",
        surface_path=tmp_path / "surface.py",
        program_md_path=tmp_path / "program.md",
        evaluate_fn=mock_evaluate,
        obsidian_client=obsidian,
        budget_secs=1,
        anthropic_api_key="test-key",
    )
    (tmp_path / "surface.py").write_text("VALUE = 1\n")
    (tmp_path / "program.md").write_text("Optimize.\n")
    runner.baseline_score = 0.80

    with patch.object(runner, "_propose_diff", return_value="--- a/surface.py\n+++ b/surface.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"):
        outcome = runner.run_one_trial(trial_num=1)

    assert outcome == TrialOutcome.SKIP
    obsidian.log_result.assert_not_called()
