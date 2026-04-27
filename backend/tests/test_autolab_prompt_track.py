"""Tests for the prompt optimization track."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from autolab.tracks.prompt_opt.surface import ORCHESTRATOR_SYSTEM_PROMPT, ESL_EVALUATION_PROMPT, config


def test_surface_exports_prompt_strings():
    assert isinstance(ORCHESTRATOR_SYSTEM_PROMPT, str)
    assert len(ORCHESTRATOR_SYSTEM_PROMPT) > 50
    assert isinstance(ESL_EVALUATION_PROMPT, str)
    assert len(ESL_EVALUATION_PROMPT) > 50


def test_surface_config_dict_has_expected_keys():
    assert "orchestrator_system_prompt" in config
    assert "esl_evaluation_prompt" in config


def test_evaluate_returns_none_without_api_key(tmp_path):
    """evaluate_prompts returns None when ANTHROPIC_API_KEY is not set."""
    surface_path = tmp_path / "surface.py"
    surface_path.write_text(
        "ORCHESTRATOR_SYSTEM_PROMPT = 'test'\n"
        "ESL_EVALUATION_PROMPT = 'test'\n"
        "config = {}\n"
    )
    from autolab.tracks.prompt_opt.evaluator import evaluate_prompts
    with patch("autolab.tracks.prompt_opt.evaluator.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        result = evaluate_prompts(surface_path)
    assert result is None


def test_evaluate_returns_none_on_bad_surface(tmp_path):
    """evaluate_prompts returns None when surface.py is malformed."""
    surface_path = tmp_path / "surface.py"
    surface_path.write_text("this is not valid python !!!\n")
    from autolab.tracks.prompt_opt.evaluator import evaluate_prompts
    with patch("autolab.tracks.prompt_opt.evaluator.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"
        result = evaluate_prompts(surface_path)
    assert result is None
