"""Tests for the context scoring track."""

import math
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from autolab.tracks.context_scoring.surface import WeaviateConfig
from autolab.tracks.context_scoring.evaluator import _ndcg, _dcg, evaluate_context_config


def test_weaviate_config_defaults():
    cfg = WeaviateConfig()
    assert 0.0 <= cfg.alpha <= 1.0
    assert 1 <= cfg.limit <= 100
    assert 0.0 <= cfg.certainty <= 1.0
    assert cfg.distance_metric in ("cosine", "dot", "l2-squared")


def test_dcg_perfect_rank():
    """Perfect result at rank 1 gives DCG = 1/log2(2) = 1.0."""
    assert _dcg([1.0, 0.0, 0.0], k=3) == pytest.approx(1.0)


def test_ndcg_perfect_retrieval():
    """All results contain expected keywords => NDCG@5 = 1.0."""
    retrieved = ["boundary no_work_after evening", "foo bar", "baz"]
    keywords = ["boundary"]
    # Only first matches, ideal is also [1, 0, 0] so NDCG = 1.0
    assert _ndcg(retrieved, keywords, k=3) == pytest.approx(1.0)


def test_evaluate_returns_none_when_weaviate_down(tmp_path):
    """evaluate_context_config returns None gracefully when Weaviate is unavailable."""
    import sys
    surface_path = tmp_path / "surface.py"
    surface_path.write_text(
        "from autolab.tracks.context_scoring.surface import WeaviateConfig\nconfig = WeaviateConfig()\n"
    )
    # weaviate may not be installed in the test environment; mock the module so
    # utils.weaviate_client can be imported before patching get_weaviate_client.
    mock_weaviate_mod = MagicMock()
    weaviate_mocks = {
        "weaviate": mock_weaviate_mod,
        "weaviate.classes": MagicMock(),
        "weaviate.classes.query": MagicMock(),
    }
    with patch.dict("sys.modules", weaviate_mocks):
        with patch("utils.weaviate_client.get_weaviate_client") as mock_wc:
            mock_wc.side_effect = Exception("Weaviate not running")
            result = evaluate_context_config(surface_path)
    assert result is None
