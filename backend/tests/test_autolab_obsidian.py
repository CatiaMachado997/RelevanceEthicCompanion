"""Tests for Obsidian vault client with fallback."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from autolab.obsidian import ObsidianClient, ExperimentResult


def test_experiment_result_fields():
    r = ExperimentResult(
        track="esl_tuning",
        trial=1,
        score=0.85,
        baseline=0.80,
        delta=0.05,
        outcome="WIN",
        hypothesis="raised urgency threshold 0.7->0.75",
    )
    assert r.track == "esl_tuning"
    assert r.outcome == "WIN"
    assert r.delta == pytest.approx(0.05)


def test_fallback_writes_json_when_obsidian_unavailable(tmp_path):
    client = ObsidianClient(
        api_key="test-key",
        base_url="https://127.0.0.1:27124",
        vault_path="EthicCompanion",
        fallback_dir=str(tmp_path),
    )
    result = ExperimentResult(
        track="esl_tuning",
        trial=1,
        score=0.85,
        baseline=0.80,
        delta=0.05,
        outcome="WIN",
        hypothesis="test hypothesis",
    )

    # Mock requests.patch to raise ConnectionError (Obsidian not running)
    with patch("autolab.obsidian.requests.patch") as mock_patch:
        mock_patch.side_effect = ConnectionError("Obsidian not running")
        client.log_result(result)

    # Fallback JSON should be written
    log_file = tmp_path / "esl_tuning" / "log.jsonl"
    assert log_file.exists()
    line = json.loads(log_file.read_text().strip())
    assert line["outcome"] == "WIN"
    assert line["trial"] == 1


def test_ping_returns_false_when_obsidian_unavailable():
    client = ObsidianClient(
        api_key="test-key",
        base_url="https://127.0.0.1:27124",
        vault_path="EthicCompanion",
    )
    with patch("autolab.obsidian.requests.get") as mock_get:
        mock_get.side_effect = ConnectionError
        assert client.ping() is False


def test_ping_returns_true_when_obsidian_available():
    client = ObsidianClient(
        api_key="test-key",
        base_url="https://127.0.0.1:27124",
        vault_path="EthicCompanion",
    )
    with patch("autolab.obsidian.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        assert client.ping() is True
