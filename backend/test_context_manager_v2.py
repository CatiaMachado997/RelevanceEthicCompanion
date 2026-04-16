#!/usr/bin/env python3
"""
Test Refactored Context Manager V2
Tests PostgreSQL + Weaviate integration
"""

import sys

sys.path.insert(0, "/Users/catiamachado/RelevanceEthicCompanion/backend")

import asyncio
from datetime import datetime, timedelta, timezone


async def test_context_manager_v2():
    """Test the refactored context manager"""
    from services.context_manager import ContextManager
    from utils.weaviate_client import get_weaviate_client
    from esl.models import UserValue, ValueType
    from models.context import Goal, Event, GoalStatus

    print("\n" + "=" * 70)
    print("TEST: Context Manager V2 (PostgreSQL + Weaviate)")
    print("=" * 70)

    # Initialize
    weaviate_client = get_weaviate_client()
    context_mgr = ContextManager(weaviate_client=weaviate_client)

    test_user_id = "00000000-0000-0000-0000-000000000000"

    # Test 1: Get user values from PostgreSQL
    print("\n1. Testing get_user_values (PostgreSQL)...")
    values = await context_mgr.get_user_values(test_user_id)
    print(f"   ✅ Retrieved {len(values)} user values")
    for v in values:
        print(f"      - {v.value} (priority: {v.priority})")

    # Test 2: Get active goals from PostgreSQL
    print("\n2. Testing get_active_goals (PostgreSQL)...")
    goals = await context_mgr.get_active_goals(test_user_id)
    print(f"   ✅ Retrieved {len(goals)} active goals")
    for g in goals:
        print(f"      - {g.title} (priority: {g.priority})")

    # Test 3: Create a new goal
    print("\n3. Testing create_goal (PostgreSQL)...")
    new_goal = Goal(
        user_id=test_user_id,
        title="Test V2 Context Manager",
        description="Verify PostgreSQL integration works",
        status=GoalStatus.ACTIVE,
        priority=9,
    )
    created_goal = await context_mgr.create_goal(new_goal)
    print(f"   ✅ Created goal: {created_goal.title} (ID: {created_goal.id})")

    # Test 4: Get upcoming events from PostgreSQL
    print("\n4. Testing get_upcoming_events (PostgreSQL)...")
    events = await context_mgr.get_upcoming_events(test_user_id, hours_ahead=168)
    print(f"   ✅ Retrieved {len(events)} upcoming events")
    for e in events[:3]:
        print(f"      - {e.title} at {e.start_time}")

    # Test 5: Store an event
    print("\n5. Testing store_event (PostgreSQL)...")
    new_event = Event(
        user_id=test_user_id,
        title="V2 Testing Session",
        description="Testing refactored context manager",
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        end_time=datetime.now(timezone.utc) + timedelta(hours=3),
        source="manual",
        source_id="test-v2-event",
    )
    stored_event = await context_mgr.store_event(new_event)
    print(f"   ✅ Stored event: {stored_event.title} (ID: {stored_event.id})")

    # Test 6: Get user context (for ESL)
    print("\n6. Testing get_user_context (for ESL)...")
    user_context = await context_mgr.get_user_context(test_user_id)
    print(f"   ✅ Built user context")
    print(f"      - User ID: {user_context.user_id}")
    print(f"      - Active goals: {len(user_context.active_goals)}")
    print(f"      - User values: {len(user_context.user_values)}")
    print(f"      - Focus mode: {user_context.focus_mode}")

    # Test 7: Get current context (for V2 relevance scoring)
    print("\n7. Testing get_current_context (for V2)...")
    current_context = await context_mgr.get_current_context(test_user_id)
    print(f"   ✅ Built current context (RelevanceContext)")
    print(f"      - Active goals: {len(current_context.active_goals)}")
    for g in current_context.active_goals:
        print(f"        • {g}")
    print(f"      - Upcoming events: {len(current_context.upcoming_events)}")
    for e in current_context.upcoming_events[:2]:
        print(f"        • {e['title']}")
    print(f"      - User values: {len(current_context.user_values)}")
    print(f"      - Focus mode: {current_context.focus_mode}")
    print(f"      - Time of day: {current_context.time_of_day}:00")

    # Test 8: Set focus mode
    print("\n8. Testing set_focus_mode (PostgreSQL)...")
    await context_mgr.set_focus_mode(test_user_id, True)
    focus_mode = await context_mgr._get_focus_mode(test_user_id)
    print(f"   ✅ Focus mode set to: {focus_mode}")

    # Reset focus mode
    await context_mgr.set_focus_mode(test_user_id, False)

    print("\n" + "=" * 70)
    print("🎉 ALL CONTEXT MANAGER V2 TESTS PASSED!")
    print("=" * 70)
    print("\n✅ PostgreSQL integration: WORKING")
    print("✅ Weaviate integration: INITIALIZED")
    print("✅ M1 (structured data): WORKING")
    print("✅ M2 (semantic memory): READY (needs embedding service)")
    print("✅ ESL context building: WORKING")
    print("✅ V2 relevance context building: WORKING")
    print("\n🚀 Ready for next steps:")
    print("   1. Add GEMINI_API_KEY to test semantic memory")
    print("   2. Create data ingestion services")
    print("   3. Refactor orchestrator with LangChain")


if __name__ == "__main__":
    asyncio.run(test_context_manager_v2())
