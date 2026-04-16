"""
Test script to verify Weaviate setup
Run this after starting docker-compose
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.weaviate_client import get_weaviate_client, close_weaviate_client
import logging

logging.basicConfig(level=logging.INFO)


def test_weaviate_connection():
    """Test Weaviate connection and schema initialization"""
    print("🧪 Testing Weaviate Setup...")
    print("-" * 50)

    try:
        # Get client (will auto-initialize schemas)
        client = get_weaviate_client()
        print("✅ Connected to Weaviate successfully")

        # List all collections
        collections = client.client.collections.list_all()
        print("\n📚 Available Collections:")
        for collection_name in collections:
            print(f"  - {collection_name}")

        # Test storing a sample memory
        print("\n🧪 Testing memory storage...")
        from datetime import datetime

        test_memory = {
            "user_id": "test_user_123",
            "content": "This is a test conversation memory",
            "role": "user",
            "timestamp": datetime.now(),
            "source": "test",
            "metadata": "{}",
        }

        test_vector = [0.1] * 768  # Dummy 768-dim vector

        uuid = client.store_memory(
            collection="ConversationMemory", content=test_memory, vector=test_vector
        )
        print(f"✅ Stored test memory with UUID: {uuid}")

        # Test keyword search
        print("\n🧪 Testing keyword search...")
        results = client.query_keyword(
            collection="ConversationMemory",
            query="test conversation",
            user_id="test_user_123",
            limit=5,
        )
        print(f"✅ Keyword search returned {len(results)} results")

        # Cleanup
        print("\n🧹 Cleaning up test data...")
        client.delete_by_id("ConversationMemory", uuid)
        print("✅ Test data cleaned up")

        # Close connection
        close_weaviate_client()
        print("\n✅ All tests passed! Weaviate is ready for V2.")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = test_weaviate_connection()
    sys.exit(0 if success else 1)
