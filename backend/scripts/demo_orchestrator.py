#!/usr/bin/env python3
"""
Orchestrator Demo
Shows the complete ESL integration pattern in action
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import asyncio
from uuid import uuid4
from services.orchestrator import Orchestrator, ActionType, UrgencyLevel
from services.context_manager import ContextManager


async def main():
    """Run orchestrator demo"""

    print("=" * 70)
    print("ETHIC COMPANION - ORCHESTRATOR DEMO")
    print("Demonstrating: User Input → ProposedAction → ESL → Decision")
    print("=" * 70)

    # Initialize
    context_manager = ContextManager()
    orchestrator = Orchestrator(context_manager)

    # Mock user (in production, this comes from Supabase Auth)
    user_id = uuid4()
    print(f"\n👤 Demo User ID: {user_id}")

    # ========== DEMO 1: Push Notification ==========
    print("\n" + "─" * 70)
    print("📱 DEMO 1: Push Notification with ESL Protection")
    print("─" * 70)

    result1 = await orchestrator.send_notification(
        user_id=user_id,
        title="Meeting Reminder",
        body="Your team sync starts in 10 minutes",
        urgency=UrgencyLevel.HIGH,
    )

    print(f"\n✅ Decision: {result1['decision'].status}")
    print(f"📝 Reasoning: {result1['decision'].reason}")
    print(f"🚀 Executed: {result1['executed']}")
    print(f"💬 Transparency: {result1['transparency']}")

    # ========== DEMO 2: User Message (Chat) ==========
    print("\n" + "─" * 70)
    print("💬 DEMO 2: User Message with ESL-Protected Response")
    print("─" * 70)

    result2 = await orchestrator.handle_user_message(
        user_id=user_id, message="What's on my schedule today?"
    )

    print(f"\n✅ Decision: {result2['esl_decision']['status']}")
    print(f"📝 Reasoning: {result2['esl_decision']['reason']}")
    print(f"🚀 Executed: {result2['executed']}")
    if result2["executed"]:
        print(f"🤖 Response: {result2['response']}")

    # ========== DEMO 3: Proactive Suggestion ==========
    print("\n" + "─" * 70)
    print("💡 DEMO 3: Proactive AI Suggestion (ESL Guards Against Manipulation)")
    print("─" * 70)

    result3 = await orchestrator.suggest_proactive_action(
        user_id=user_id,
        suggestion_type="end_of_day_summary",
        suggestion_content="Here's your productivity summary for today...",
        rationale="Detected end of work day based on calendar",
    )

    print(f"\n✅ Decision: {result3['decision'].status}")
    print(f"📝 Reasoning: {result3['decision'].reason}")
    print(f"🚀 Executed: {result3['executed']}")

    # ========== DEMO 4: Custom Action ==========
    print("\n" + "─" * 70)
    print("🎯 DEMO 4: Custom Action with ESL Evaluation")
    print("─" * 70)

    result4 = await orchestrator.decide_action(
        user_id=user_id,
        action_type=ActionType.CONTENT_GENERATION,
        content="Generated weekly report based on your goals",
        urgency=UrgencyLevel.LOW,
        metadata={"report_type": "weekly", "auto_generated": True},
    )

    print(f"\n✅ Decision: {result4['decision'].status}")
    print(f"📝 Reasoning: {result4['decision'].reason}")
    print(f"🚀 Executed: {result4['executed']}")

    # ========== ESL Statistics ==========
    print("\n" + "─" * 70)
    print("📊 ESL TRANSPARENCY REPORT")
    print("─" * 70)

    report = await orchestrator.get_esl_transparency_report(user_id=user_id, days=7)

    print(f"\n📈 Report for last {report['period_days']} days:")
    print(f"   Total decisions: {report['report']['total_decisions']}")
    if report["report"]["total_decisions"] > 0:
        print(f"   Approved: {report['report']['approved_count']}")
        print(f"   Vetoed: {report['report']['vetoed_count']}")
        print(f"   Modified: {report['report']['modified_count']}")
    else:
        print(f"   {report['report'].get('message', 'No ESL decisions logged yet')}")

    # ========== Summary ==========
    print("\n" + "=" * 70)
    print("✨ DEMO COMPLETE")
    print("=" * 70)
    print("\n🎯 Key Takeaways:")
    print("   1. Every action goes through ESL (mandatory gateway)")
    print("   2. ESL evaluates based on user values and context")
    print("   3. Decisions are logged for transparency")
    print("   4. User boundaries are sacred and enforced")
    print("\n🏛️ Architecture: Trust over Engagement")
    print("   • No dark patterns")
    print("   • No manipulation")
    print("   • User empowerment first")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
