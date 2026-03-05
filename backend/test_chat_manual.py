"""
Manual test of OrchestratorV2 chat flow WITHOUT databases
This verifies Gemini LLM + ESL integration works
"""
import asyncio
from services.orchestrator_v2 import OrchestratorV2
from services.context_manager import ContextManager


class MockContextManager(ContextManager):
    """Mock context manager that doesn't need databases"""

    async def get_active_goals(self, user_id: str):
        """Return mock goals"""
        from models.context import Goal, GoalStatus
        from datetime import datetime
        return [
            Goal(
                id="1",
                user_id=user_id,
                title="Test Groq Integration",
                description="Verify OrchestratorV2 works with Llama",
                priority=1,
                status=GoalStatus.ACTIVE,
                created_at=datetime(2024, 1, 1)
            )
        ]

    async def get_upcoming_events(self, user_id: str, hours_ahead: int = 48):
        """Return empty events"""
        return []

    async def get_user_values(self, user_id: str):
        """Return mock user values"""
        from esl.models import UserValue, ValueType
        from datetime import datetime
        return [
            UserValue(
                id="1",
                user_id=user_id,
                value="No dark patterns",
                type=ValueType.BOUNDARY,
                priority=1,
                is_active=True,
                created_at=datetime(2024, 1, 1)
            )
        ]

    async def query_semantic_memory(self, user_id: str, query: str, limit: int = 5, offset: int = 0):
        """Return empty memory"""
        return []

    async def store_semantic_memory(self, entry):
        """No-op storage"""
        print(f"  [Mock] Storing memory: {entry.content[:50]}...")
        return True

    async def get_user_context(self, user_id: str):
        """Return minimal mock context for ESL"""
        from esl.models import UserContext
        from datetime import datetime

        user_values = await self.get_user_values(user_id)

        return UserContext(
            user_id=user_id,
            user_values=user_values,
            active_goals=[],
            focus_mode=False,
            current_time=datetime.utcnow()
        )


async def test_chat():
    """Test chat endpoint with OrchestratorV2"""
    print("=" * 60)
    print("🧪 TESTING ORCHESTRATORV2 + GROQ (LLAMA 3.3) + ESL")
    print("=" * 60)
    print()

    # Initialize with mock context manager
    mock_cm = MockContextManager()
    orchestrator = OrchestratorV2(mock_cm)

    test_user_id = "test-user-123"
    test_message = "Hello! Can you help me understand what you can do?"

    print(f"📤 User: {test_message}")
    print()
    print("Processing with OrchestratorV2...")
    print("  1. Building context from user values/goals")
    print("  2. Calling Groq (Llama 3.3 70B) for response generation")
    print("  3. Evaluating through ESL")
    print()

    # Call orchestrator
    result = await orchestrator.handle_user_message(
        user_id=test_user_id,
        message=test_message
    )

    print("=" * 60)
    print("✅ RESULTS")
    print("=" * 60)
    print()
    print(f"Executed: {result['executed']}")
    print(f"Timestamp: {result.get('timestamp', 'N/A')}")
    print()

    if result['executed']:
        print(f"🤖 Assistant Response:")
        print(f"   {result['response']}")
        print()
        print(f"🛡️  ESL Decision: APPROVED")
        print(f"   {result.get('transparency', 'N/A')}")
    else:
        print(f"🛡️  ESL Decision: BLOCKED")
        print(f"   Reason: {result.get('error', 'Unknown')}")

    print()
    print("=" * 60)

    if result['executed']:
        print("✅ SUCCESS: OrchestratorV2 + Groq (Llama 3.3) + ESL working!")
    else:
        print("❌ Test failed - check error above")
    print("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(test_chat())
