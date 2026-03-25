"""
Background Scheduler Service

Manages periodic tasks like data source syncing.
"""

import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from services.data_ingestion import DataIngestionService
from utils.db import get_db_connection

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Manages background tasks for data ingestion

    Tasks:
    - Sync Google Calendar every 15 minutes for connected users
    - Clean up expired tokens
    - Generate daily summaries (future)
    """

    def __init__(self, data_ingestion: DataIngestionService):
        """
        Initialize background scheduler

        Args:
            data_ingestion: Data ingestion service instance
        """
        self.data_ingestion = data_ingestion
        self.scheduler = AsyncIOScheduler()
        self._running = False

        logger.info("✅ BackgroundScheduler initialized")

    def start(self):
        """Start all background tasks"""
        if self._running:
            logger.warning("⚠️  Scheduler already running")
            return

        # Task 1: Sync Google Calendar every 15 minutes
        self.scheduler.add_job(
            func=self._sync_all_calendars,
            trigger=IntervalTrigger(minutes=15),
            id='sync_google_calendar',
            name='Sync Google Calendar for all users',
            replace_existing=True,
            max_instances=1  # Prevent overlap
        )

        # Task 2: Clean up expired tokens daily at 3 AM
        self.scheduler.add_job(
            func=self._cleanup_expired_tokens,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_tokens',
            name='Clean up expired OAuth tokens',
            replace_existing=True
        )

        # Task 3: Health check every hour
        self.scheduler.add_job(
            func=self._health_check,
            trigger=IntervalTrigger(hours=1),
            id='health_check',
            name='Scheduler health check',
            replace_existing=True
        )

        # Weekly digest — every Monday at 8 AM
        self.scheduler.add_job(
            func=self._generate_weekly_digest,
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_digest',
            name='Generate weekly AI digest for all users',
            replace_existing=True,
            max_instances=1,
        )

        # Start scheduler
        self.scheduler.start()
        self._running = True

        logger.info("✅ Background scheduler started")
        logger.info("   - Calendar sync: Every 15 minutes")
        logger.info("   - Token cleanup: Daily at 3 AM")
        logger.info("   - Health check: Every hour")
        logger.info("   - Weekly digest: Every Monday at 8 AM")

    def stop(self):
        """Stop all background tasks"""
        if not self._running:
            return

        self.scheduler.shutdown(wait=True)
        self._running = False

        logger.info("👋 Background scheduler stopped")

    async def _sync_all_calendars(self):
        """
        Sync Google Calendar for all connected users

        This runs every 15 minutes to keep events up to date.
        """
        try:
            logger.info("🔄 Starting scheduled calendar sync for all users")

            # Get all users with Google Calendar connected
            users_to_sync = await self._get_users_with_calendar()

            synced_count = 0
            failed_count = 0

            for user_id in users_to_sync:
                try:
                    result = await self.data_ingestion.sync_data_source(
                        user_id=user_id,
                        source_type='google_calendar'
                    )

                    if result['success']:
                        synced_count += 1
                        logger.debug(f"✅ Synced calendar for user {user_id}: {result['items_synced']} events")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️  Sync failed for user {user_id}: {result['message']}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Error syncing calendar for user {user_id}: {e}")

            logger.info(
                f"✅ Scheduled calendar sync complete: "
                f"{synced_count} users synced, {failed_count} failed"
            )

        except Exception as e:
            logger.error(f"❌ Critical error in scheduled calendar sync: {e}", exc_info=True)

    async def _get_users_with_calendar(self) -> list:
        """Get list of user IDs with Google Calendar connected"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT user_id
                        FROM data_sources
                        WHERE source_type = 'google_calendar'
                          AND enabled = TRUE
                          AND oauth_token_encrypted IS NOT NULL
                        ORDER BY user_id
                    """)

                    return [row[0] for row in cur.fetchall()]

        except Exception as e:
            logger.error(f"❌ Failed to get users with calendar: {e}")
            return []

    async def _cleanup_expired_tokens(self):
        """
        Clean up expired OAuth tokens

        Marks data sources as disabled if tokens are expired and can't be refreshed.
        Runs daily at 3 AM.
        """
        try:
            logger.info("🧹 Starting cleanup of expired OAuth tokens")

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Find expired tokens
                    cur.execute("""
                        SELECT user_id, source_type, token_expires_at
                        FROM data_sources
                        WHERE enabled = TRUE
                          AND token_expires_at < NOW()
                    """)

                    expired = cur.fetchall()

                    if not expired:
                        logger.info("✅ No expired tokens found")
                        return

                    logger.info(f"Found {len(expired)} expired tokens")

                    # For now, just log - in production, attempt refresh
                    for user_id, source_type, expires_at in expired:
                        logger.warning(
                            f"⚠️  Expired token: {source_type} for user {user_id} "
                            f"(expired at {expires_at})"
                        )

                        # TODO: Attempt token refresh before disabling
                        # For MVP, we'll let users re-authorize manually

            logger.info("✅ Token cleanup complete")

        except Exception as e:
            logger.error(f"❌ Error during token cleanup: {e}", exc_info=True)

    async def _generate_weekly_digest(self):
        """
        Generate a weekly digest notification for all users.
        Runs Monday at 8 AM. Creates a notification summarising the week.
        """
        logger.info("[Scheduler] Generating weekly digest notifications...")
        try:
            from utils.db import get_db_connection
            from routes.notifications import create_notification
            from services.context_manager import ContextManager
            from langchain_core.messages import HumanMessage
            from langchain_groq import ChatGroq
            from config import settings

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users LIMIT 100")
                    users = cur.fetchall()

            ctx = ContextManager()

            for user_row in users:
                user_id = str(user_row["id"])
                try:
                    goals = await ctx.get_active_goals(user_id)
                    values = await ctx.get_user_values(user_id)

                    if not goals and not values:
                        continue  # Skip users with no data

                    goal_text = "\n".join(f"- {g.get('title', g) if isinstance(g, dict) else g.title}" for g in goals[:5])
                    value_text = "\n".join(f"- {v.get('value', v) if isinstance(v, dict) else v.value}" for v in values[:3])

                    prompt = f"""Write a short weekly check-in message (2–3 sentences) for a user.
Active goals:
{goal_text or "None"}

Values:
{value_text or "None"}

Be encouraging and specific. Suggest one concrete action for the week ahead."""

                    llm = ChatGroq(
                        model="llama-3.1-8b-instant",
                        groq_api_key=settings.GROQ_API_KEY,
                        temperature=0.7,
                    )
                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    content = (response.content or "").strip()

                    if content:
                        with get_db_connection() as conn:
                            create_notification(
                                conn,
                                user_id=user_id,
                                type="info",
                                title="Your weekly companion check-in",
                                message=content[:500],
                                metadata={"source": "weekly_digest"},
                            )

                except Exception as e:
                    logger.warning(f"[Scheduler] Weekly digest failed for user {user_id}: {e}")

        except Exception as e:
            logger.error(f"[Scheduler] Weekly digest job failed: {e}")

    async def _health_check(self):
        """
        Health check for scheduler

        Logs scheduler status and job information.
        Runs every hour.
        """
        try:
            jobs = self.scheduler.get_jobs()
            logger.info(
                f"💚 Scheduler health check: "
                f"{len(jobs)} jobs registered, running={self._running}"
            )

            # Log next run times for key jobs
            for job in jobs:
                if job.next_run_time:
                    logger.debug(
                        f"   - {job.name}: next run at {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")

    def get_job_status(self) -> dict:
        """
        Get status of all scheduled jobs

        Returns:
            Dict with job statuses
        """
        if not self._running:
            return {"running": False, "jobs": []}

        jobs = self.scheduler.get_jobs()

        return {
            "running": self._running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ]
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    from services.embedding_service import EmbeddingService
    from services.context_manager import ContextManager
    from utils.weaviate_client import get_weaviate_client
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_scheduler():
        """Test background scheduler"""

        # Initialize dependencies
        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(os.getenv('GEMINI_API_KEY'))

        context_manager = ContextManager(
            weaviate_client=weaviate_client,
            embedding_service=embedding_service
        )

        data_ingestion = DataIngestionService(context_manager)
        scheduler = BackgroundScheduler(data_ingestion)

        print("\n" + "=" * 60)
        print("BACKGROUND SCHEDULER TEST")
        print("=" * 60)

        # Start scheduler
        scheduler.start()

        # Get job status
        status = scheduler.get_job_status()
        print(f"\n✅ Scheduler running: {status['running']}")
        print(f"   Registered jobs: {len(status['jobs'])}")

        for job in status['jobs']:
            print(f"\n   - {job['name']}")
            print(f"     ID: {job['id']}")
            print(f"     Next run: {job['next_run']}")

        # Let it run for a minute
        print("\n⏳ Scheduler running for 60 seconds...")
        await asyncio.sleep(60)

        # Stop scheduler
        scheduler.stop()
        print("\n👋 Scheduler stopped")

    asyncio.run(test_scheduler())
