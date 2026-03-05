#!/usr/bin/env python3
"""Quick test for Weaviate fixes"""
import sys
sys.path.insert(0, '/Users/catiamachado/RelevanceEthicCompanion/backend')

import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

async def test_weaviate_fixes():
    from services.embedding_service import EmbeddingService
    from services.context_manager import ContextManager
    from utils.weaviate_client import get_weaviate_client
    from models.context import SemanticMemoryEntry

    print("\n" + "="*60)
    print("Testing Weaviate Fixes")
    print("="*60)

    gemini_key = os.getenv("GEMINI_API_KEY")
    embedding_service = EmbeddingService(gemini_key)
    weaviate_client = get_weaviate_client()
    context_manager = ContextManager(
        weaviate_client=weaviate_client,
        embedding_service=embedding_service
    )

    test_user_id = "00000000-0000-0000-0000-000000000000"

    # Test 1: Store with proper timestamp format
    print("\n1. Testing semantic memory storage with RFC3339 timestamp...")
    entry = SemanticMemoryEntry(
        user_id=test_user_id,
        content="Testing Weaviate datetime fix",
        source="test",
        timestamp=datetime.now(timezone.utc),  # timezone-aware
        metadata={"test": True}
    )

    memory_id = await context_manager.store_semantic_memory(entry)
    if memory_id:
        print(f"   ✅ Storage successful: {memory_id}")
    else:
        print(f"   ❌ Storage failed")
        return False

    # Test 2: Query with hybrid search
    print("\n2. Testing hybrid search with Filter...")
    try:
        results = await context_manager.query_semantic_memory(
            user_id=test_user_id,
            query="datetime fix",
            limit=5
        )
        print(f"   ✅ Hybrid search successful: {len(results)} results")
        for r in results:
            print(f"      - {r.content[:50]}...")
    except Exception as e:
        print(f"   ❌ Hybrid search failed: {e}")
        return False

    print("\n" + "="*60)
    print("✅ ALL FIXES WORKING!")
    print("="*60)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_weaviate_fixes())
    sys.exit(0 if success else 1)
