"""Provider-selection and batching tests for local Ollama embeddings."""

from unittest.mock import patch

import pytest

from services.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_ollama_embedding_is_cached_and_keeps_vector_shape():
    service = EmbeddingService(
        provider="ollama",
        model="mxbai-embed-large",
        base_url="http://ollama.test",
        dimensions=4,
    )

    with patch.object(
        service, "_ollama_embed_sync", return_value=[[0.1, 0.2, 0.3]]
    ) as embed:
        first = await service.generate_embedding("trustworthy AI")
        second = await service.generate_query_embedding("trustworthy AI")

    assert first == [0.1, 0.2, 0.3, 0.0]
    assert second == first
    embed.assert_called_once_with(["trustworthy AI"])


@pytest.mark.asyncio
async def test_ollama_batch_preserves_input_order_with_cache_hits():
    service = EmbeddingService(provider="ollama", dimensions=1)
    service._store_in_cache("cached", [1.0])

    with patch.object(
        service, "_ollama_embed_sync", return_value=[[2.0], [3.0]]
    ) as embed:
        rows = await service.generate_embeddings_batch(["new-a", "cached", "new-b"])

    assert rows == [[2.0], [1.0], [3.0]]
    embed.assert_called_once_with(["new-a", "new-b"])


def test_auto_provider_uses_ollama_without_gemini_key():
    service = EmbeddingService(api_key="", provider="auto")

    assert service.provider == "ollama"
