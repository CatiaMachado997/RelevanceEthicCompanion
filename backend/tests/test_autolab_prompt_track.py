"""Tests for the prompt optimisation experiment track."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SURFACE_PATH = (
    Path(__file__).parent.parent
    / "autolab" / "tracks" / "prompt_opt" / "surface.py"
)
EVALUATOR_PATH = (
    Path(__file__).parent.parent
    / "autolab" / "tracks" / "prompt_opt" / "evaluator.py"
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_surface_exports_required_names():
    """surface.py must export ORCHESTRATOR_SYSTEM_PROMPT, ESL_EVALUATION_PROMPT, config."""
    surface = _load_module(SURFACE_PATH, "prompt_opt_surface")
    assert hasattr(surface, "ORCHESTRATOR_SYSTEM_PROMPT")
    assert hasattr(surface, "ESL_EVALUATION_PROMPT")
    assert hasattr(surface, "config")
    assert isinstance(surface.ORCHESTRATOR_SYSTEM_PROMPT, str)
    assert isinstance(surface.ESL_EVALUATION_PROMPT, str)
    assert isinstance(surface.config, dict)
    assert len(surface.ORCHESTRATOR_SYSTEM_PROMPT) > 10
    assert len(surface.ESL_EVALUATION_PROMPT) > 10


def test_surface_config_has_required_keys():
    """config dict must contain model, max_tokens, temperature."""
    surface = _load_module(SURFACE_PATH, "prompt_opt_surface_cfg")
    cfg = surface.config
    assert "model" in cfg
    assert "max_tokens" in cfg
    assert "temperature" in cfg
    assert isinstance(cfg["max_tokens"], int)
    assert isinstance(cfg["temperature"], float)


def test_evaluate_prompts_returns_none_without_api_key(tmp_path):
    """evaluate_prompts returns None when GROQ_API_KEY is not set."""
    import shutil
    shutil.copy(SURFACE_PATH, tmp_path / "surface.py")

    evaluator = _load_module(EVALUATOR_PATH, "prompt_opt_evaluator_nokey")

    with patch.dict("os.environ", {}, clear=True):
        # Remove GROQ_API_KEY if present
        import os
        os.environ.pop("GROQ_API_KEY", None)
        result = evaluator.evaluate_prompts(tmp_path / "surface.py")

    assert result is None


def test_evaluate_prompts_returns_none_on_bad_surface(tmp_path):
    """evaluate_prompts returns None when surface.py is invalid."""
    bad_surface = tmp_path / "surface.py"
    bad_surface.write_text("# broken — missing required exports\n")

    evaluator = _load_module(EVALUATOR_PATH, "prompt_opt_evaluator_bad")

    mock_groq_module = MagicMock()
    mock_groq_module.Groq = MagicMock()

    with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
        with patch.dict("sys.modules", {"groq": mock_groq_module}):
            result = evaluator.evaluate_prompts(bad_surface)

    assert result is None
