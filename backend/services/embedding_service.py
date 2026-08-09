"""Semantic embeddings with Gemini or a local Ollama fallback."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate and cache document/query embeddings using one vector space."""

    def __init__(
        self,
        api_key: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        configured_provider = (provider or settings.EMBEDDING_PROVIDER).lower()
        if configured_provider == "auto":
            configured_provider = "gemini" if api_key else "ollama"
        if configured_provider not in {"gemini", "ollama"}:
            raise ValueError("EMBEDDING_PROVIDER must be one of: auto, gemini, ollama")
        if configured_provider == "gemini" and not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")

        self.api_key = api_key
        self.provider = configured_provider
        self.model = model or (
            "models/gemini-embedding-001"
            if self.provider == "gemini"
            else settings.OLLAMA_EMBEDDING_MODEL
        )
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self._client = (
            genai.Client(api_key=api_key) if self.provider == "gemini" else None
        )
        self._cache: Dict[str, tuple[List[float], datetime]] = {}
        self._cache_ttl = timedelta(hours=1)

        logger.info(
            "EmbeddingService initialized with %s (%s)",
            self.provider,
            self.model,
        )

    def _get_cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        cache_key = self._get_cache_key(text)
        cached = self._cache.get(cache_key)
        if cached is None:
            return None
        embedding, timestamp = cached
        if datetime.now(timezone.utc) - timestamp < self._cache_ttl:
            return embedding
        del self._cache[cache_key]
        return None

    def _store_in_cache(self, text: str, embedding: List[float]) -> None:
        self._cache[self._get_cache_key(text)] = (
            embedding,
            datetime.now(timezone.utc),
        )

    def _ollama_embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Call Ollama directly, avoiding a new production SDK dependency."""
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(
                {"model": self.model, "input": texts, "truncate": True}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama embeddings unavailable at {self.base_url}: {exc}"
            ) from exc

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("Ollama returned an invalid embeddings response")
        return [[float(value) for value in row] for row in embeddings]

    async def _ollama_embed(self, texts: List[str]) -> List[List[float]]:
        rows = await asyncio.to_thread(self._ollama_embed_sync, texts)
        return [self._fit_dimensions(row) for row in rows]

    def _fit_dimensions(self, embedding: List[float]) -> List[float]:
        """Pad local vectors to the collection dimension without changing cosine."""
        if len(embedding) > self.dimensions:
            raise ValueError(
                f"Embedding dimension {len(embedding)} exceeds configured "
                f"dimension {self.dimensions}"
            )
        if len(embedding) == self.dimensions:
            return embedding
        return embedding + [0.0] * (self.dimensions - len(embedding))

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate one document embedding."""
        cached = self._get_from_cache(text)
        if cached is not None:
            return cached

        try:
            if self.provider == "ollama":
                embedding = (await self._ollama_embed([text]))[0]
            else:
                if self._client is None:
                    raise RuntimeError("Gemini client is not initialized")
                result = self._client.models.embed_content(
                    model=self.model,
                    contents=text,
                    config=types.EmbedContentConfig(task_type="retrieval_document"),
                )
                if not result.embeddings or result.embeddings[0].values is None:
                    raise ValueError("Gemini returned no embedding")
                embedding = list(result.embeddings[0].values)

            self._store_in_cache(text, embedding)
            return embedding
        except Exception as exc:
            logger.error("Failed to generate embedding: %s", exc)
            raise

    async def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100
    ) -> List[List[float]]:
        """Generate document embeddings in provider-sized batches."""
        embeddings: List[List[float]] = []
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset : offset + batch_size]
            ordered: List[Optional[List[float]]] = [None] * len(batch)
            uncached_texts: List[str] = []
            uncached_indices: List[int] = []

            for index, text in enumerate(batch):
                cached = self._get_from_cache(text)
                if cached is None:
                    uncached_texts.append(text)
                    uncached_indices.append(index)
                else:
                    ordered[index] = cached

            if uncached_texts:
                if self.provider == "ollama":
                    generated = await self._ollama_embed(uncached_texts)
                else:
                    if self._client is None:
                        raise RuntimeError("Gemini client is not initialized")
                    result = self._client.models.embed_content(
                        model=self.model,
                        contents=uncached_texts,
                        config=types.EmbedContentConfig(task_type="retrieval_document"),
                    )
                    if not result.embeddings:
                        raise ValueError("Gemini returned no embeddings")
                    generated = [
                        list(item.values) if item.values is not None else []
                        for item in result.embeddings
                    ]

                if len(generated) != len(uncached_texts):
                    raise ValueError("Embedding provider returned the wrong row count")
                for text, index, embedding in zip(
                    uncached_texts, uncached_indices, generated
                ):
                    self._store_in_cache(text, embedding)
                    ordered[index] = embedding

            if any(item is None for item in ordered):
                raise ValueError("Embedding batch contains a missing row")
            embeddings.extend(item for item in ordered if item is not None)

        return embeddings

    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate a query embedding in the same provider vector space."""
        if self.provider == "ollama":
            return await self.generate_embedding(query)

        try:
            if self._client is None:
                raise RuntimeError("Gemini client is not initialized")
            result = self._client.models.embed_content(
                model=self.model,
                contents=query,
                config=types.EmbedContentConfig(task_type="retrieval_query"),
            )
            if not result.embeddings or result.embeddings[0].values is None:
                raise ValueError("Gemini returned no embedding")
            return list(result.embeddings[0].values)
        except Exception as exc:
            logger.error("Failed to generate query embedding: %s", exc)
            raise

    def clear_cache(self) -> None:
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "provider": self.provider,
            "model": self.model,
        }
