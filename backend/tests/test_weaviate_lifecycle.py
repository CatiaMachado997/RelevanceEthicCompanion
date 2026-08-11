"""Lifecycle coverage for the singleton Weaviate connection."""

from unittest.mock import MagicMock


def test_close_weaviate_client_resets_singleton(monkeypatch):
    from utils import weaviate_client as module

    client = MagicMock()
    monkeypatch.setattr(module, "_weaviate_client", client)
    monkeypatch.setattr(module, "_weaviate_unavailable", True)
    monkeypatch.setattr(module, "_weaviate_last_probe", 42.0)

    module.close_weaviate_client()

    client.close.assert_called_once_with()
    assert module._weaviate_client is None
    assert module._weaviate_unavailable is False
    assert module._weaviate_last_probe == 0.0
