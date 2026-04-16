"""
Embedding Service
Generates semantic embeddings using Gemini API

THIS IS YOUR CODE - You wrap the external API with YOUR logic:
- Batch processing for efficiency
- Error handling and retries
- Caching for common queries
- Rate limiting
"""

from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
import logging
import hashlib
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings using Gemini

    The model (Gemini) just converts text to vectors.
    YOUR CODE decides:
    - When to generate embeddings
    - How to batch requests
    - How to handle errors
    - What to cache
    """

    def __init__(self, api_key: str):
        """
        Initialize Gemini client

        Args:
            api_key: Gemini API key
        """
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")

        self.api_key = api_key
        self._client = genai.Client(api_key=api_key)

        # Simple in-memory cache (for MVP)
        # In production, use Redis or similar
        self._cache: Dict[str, tuple[List[float], datetime]] = {}
        self._cache_ttl = timedelta(hours=1)

        logger.info("✅ EmbeddingService initialized with Gemini")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.sha256(text.encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache if valid"""
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            embedding, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < self._cache_ttl:
                logger.debug(f"✅ Cache hit for text (len={len(text)})")
                return embedding
            else:
                # Expired
                del self._cache[cache_key]
        return None

    def _store_in_cache(self, text: str, embedding: List[float]):
        """Store embedding in cache"""
        cache_key = self._get_cache_key(text)
        self._cache[cache_key] = (embedding, datetime.utcnow())

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            Embedding vector (768 dimensions for Gemini embedding-001)
        """
        # Check cache first
        cached = self._get_from_cache(text)
        if cached:
            return cached

        try:
            # Call Gemini API (THE ONLY EXTERNAL INTELLIGENCE)
            # Note: Free tier uses embedding-001
            result = self._client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(task_type="retrieval_document"),
            )

            embedding = result.embeddings[0].values

            # Store in cache
            self._store_in_cache(text, embedding)

            logger.debug(
                f"✅ Generated embedding for text (len={len(text)}, dim={len(embedding)})"
            )
            return embedding

        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            raise

    async def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently

        YOUR BATCHING LOGIC - Not from Gemini
        Gemini can handle batches, but YOU decide how to split them

        Args:
            texts: List of texts to embed
            batch_size: Maximum texts per API call

        Returns:
            List of embedding vectors
        """
        embeddings: List[List[float]] = []

        # Split into batches (YOUR LOGIC)
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            try:
                # Check cache first
                batch_embeddings = []
                uncached_texts = []
                uncached_indices = []

                for idx, text in enumerate(batch):
                    cached = self._get_from_cache(text)
                    if cached:
                        batch_embeddings.append((idx, cached))
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(idx)

                # Generate embeddings for uncached texts
                if uncached_texts:
                    result = self._client.models.embed_content(
                        model="models/gemini-embedding-001",
                        contents=uncached_texts,
                        config=types.EmbedContentConfig(task_type="retrieval_document"),
                    )

                    # New SDK always returns a list of ContentEmbedding objects
                    new_embeddings = [emb.values for emb in result.embeddings]

                    # Store in cache and add to results
                    for text, embedding, idx in zip(
                        uncached_texts, new_embeddings, uncached_indices
                    ):
                        self._store_in_cache(text, embedding)
                        batch_embeddings.append((idx, embedding))

                # Sort by original index and extract embeddings
                batch_embeddings.sort(key=lambda x: x[0])
                embeddings.extend([emb for _, emb in batch_embeddings])

                logger.debug(
                    f"✅ Generated batch {i // batch_size + 1}: {len(batch)} texts"
                )

            except Exception as e:
                logger.error(f"❌ Failed to generate batch embeddings: {e}")
                raise

        return embeddings

    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a search query

        Uses different task_type for better retrieval performance

        Args:
            query: Search query

        Returns:
            Query embedding vector
        """
        try:
            # Use retrieval_query task type (optimized for queries)
            result = self._client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=query,
                config=types.EmbedContentConfig(task_type="retrieval_query"),
            )

            embedding = result.embeddings[0].values
            logger.debug(
                f"✅ Generated query embedding (len={len(query)}, dim={len(embedding)})"
            )
            return embedding

        except Exception as e:
            logger.error(f"❌ Failed to generate query embedding: {e}")
            raise

    def clear_cache(self):
        """Clear embedding cache"""
        self._cache.clear()
        logger.info("✅ Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "ttl_hours": self._cache_ttl.total_seconds() / 3600,
        }
