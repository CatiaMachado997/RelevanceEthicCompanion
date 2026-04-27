"""
Background Scheduler Service

Manages periodic tasks like data source syncing.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from services.data_ingestion import DataIngestionService
from services.proactive_gate import gate_proactive_notification
from services.tool_telemetry import ToolTelemetryService
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
            id="sync_google_calendar",
            name="Sync Google Calendar for all users",
            replace_existing=True,
            max_instances=1,  # Prevent overlap
        )

        # Gmail sync — every 30 minutes
        self.scheduler.add_job(
            func=self._sync_all_gmail,
            trigger="interval",
            minutes=30,
            id="sync_gmail",
            replace_existing=True,
        )
        # Slack sync — every 5 minutes
        self.scheduler.add_job(
            func=self._sync_all_slack,
            trigger="interval",
            minutes=5,
            id="sync_slack",
            replace_existing=True,
        )

        # Task 2: Clean up expired tokens daily at 3 AM
        self.scheduler.add_job(
            func=self._cleanup_expired_tokens,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup_tokens",
            name="Clean up expired OAuth tokens",
            replace_existing=True,
        )

        # Task 3: Health check every hour
        self.scheduler.add_job(
            func=self._health_check,
            trigger=IntervalTrigger(hours=1),
            id="health_check",
            name="Scheduler health check",
            replace_existing=True,
        )

        # Weekly digest — every Monday at 8 AM
        self.scheduler.add_job(
            func=self._generate_weekly_digest,
            trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
            id="weekly_digest",
            name="Generate weekly AI digest for all users",
            replace_existing=True,
            max_instances=1,
        )

        # Pre-meeting brief — every 15 minutes alongside calendar sync
        self.scheduler.add_job(
            func=self._generate_pre_meeting_briefs,
            trigger=IntervalTrigger(minutes=15),
            id="pre_meeting_briefs",
            name="Generate pre-meeting briefs for upcoming events",
            replace_existing=True,
            max_instances=1,
        )

        # Daily focus plan — every day at 8 AM
        self.scheduler.add_job(
            func=self._generate_daily_focus_plan,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_focus_plan",
            name="Generate daily focus plan for all users",
            replace_existing=True,
            max_instances=1,
        )

        # Deadline warnings — every day at 8 AM
        self.scheduler.add_job(
            func=self._generate_deadline_warnings,
            trigger=CronTrigger(hour=8, minute=5),
            id="deadline_warnings",
            name="Warn users about tasks due within 24 hours",
            replace_existing=True,
            max_instances=1,
        )

        # Project status snapshot — every Friday at 5 PM
        self.scheduler.add_job(
            func=self._generate_project_status_snapshot,
            trigger=CronTrigger(day_of_week="fri", hour=17, minute=0),
            id="project_status_snapshot",
            name="Generate weekly project status snapshot for all users",
            replace_existing=True,
            max_instances=1,
        )

        # Related-items clustering — every Sunday at 6 PM
        self.scheduler.add_job(
            func=self._generate_related_items_clusters,
            trigger=CronTrigger(day_of_week="sun", hour=18, minute=0),
            id="related_items_clusters",
            name="Cluster related tasks/events/goals and surface connections",
            replace_existing=True,
            max_instances=1,
        )

        # Sprint E Task 1: daily prune of tool_call_events + esl_audit_log
        self.scheduler.add_job(
            func=self._prune_old_telemetry,
            trigger=CronTrigger(hour=4, minute=0),
            id="prune_old_telemetry",
            name="Prune tool_call_events and esl_audit_log older than RETENTION_DAYS",
            replace_existing=True,
            max_instances=1,
        )

        # Start scheduler
        self.scheduler.start()
        self._running = True

        logger.info("✅ Background scheduler started")
        logger.info("   - Calendar sync: Every 15 minutes")
        logger.info("   - Gmail sync: Every 30 minutes")
        logger.info("   - Slack sync: Every 5 minutes")
        logger.info("   - Token cleanup: Daily at 3 AM")
        logger.info("   - Health check: Every hour")
        logger.info("   - Weekly digest: Every Monday at 8 AM")
        logger.info("   - Pre-meeting briefs: Every 15 minutes")
        logger.info("   - Daily focus plan: Daily at 8:00 AM")
        logger.info("   - Deadline warnings: Daily at 8:05 AM")
        logger.info("   - Project status snapshot: Every Friday at 5:00 PM")
        logger.info("   - Related-items clustering: Every Sunday at 6:00 PM")

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
                        user_id=user_id, source_type="google_calendar"
                    )

                    if result["success"]:
                        synced_count += 1
                        logger.debug(
                            f"✅ Synced calendar for user {user_id}: {result['items_synced']} events"
                        )
                    else:
                        failed_count += 1
                        logger.warning(
                            f"⚠️  Sync failed for user {user_id}: {result['message']}"
                        )

                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Error syncing calendar for user {user_id}: {e}")

            logger.info(
                f"✅ Scheduled calendar sync complete: "
                f"{synced_count} users synced, {failed_count} failed"
            )

        except Exception as e:
            logger.error(
                f"❌ Critical error in scheduled calendar sync: {e}", exc_info=True
            )

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

    async def _sync_all_gmail(self):
        await self._sync_all_for_source("gmail")

    async def _sync_all_slack(self):
        await self._sync_all_for_source("slack")

    async def _sync_all_for_source(self, source_type: str):
        """Generic per-source sync runner — replaces the calendar-specific helper
        once we have three sources."""
        try:
            users = await self._get_users_with_source(source_type)
            synced = failed = 0
            for user_id in users:
                try:
                    r = await self.data_ingestion.sync_data_source(
                        user_id, source_type
                    )
                    if r.get("success"):
                        synced += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"❌ {source_type} sync failed for {user_id}: {e}"
                    )
            logger.info(
                f"✅ Scheduled {source_type} sync: {synced} ok, {failed} failed"
            )
        except Exception as e:
            logger.error(
                f"❌ Critical error in {source_type} sync: {e}", exc_info=True
            )

    async def _get_users_with_source(self, source_type: str) -> list:
        from utils.db import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM data_sources "
                    "WHERE source_type = %s AND enabled = TRUE",
                    (source_type,),
                )
                return [r["user_id"] for r in cur.fetchall()]

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

                    goal_text = "\n".join(
                        f"- {g.get('title', g) if isinstance(g, dict) else g.title}"
                        for g in goals[:5]
                    )
                    value_text = "\n".join(
                        f"- {v.get('value', v) if isinstance(v, dict) else v.value}"
                        for v in values[:3]
                    )

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

                    if not content:
                        continue

                    brief_content = content
                    should_send, final_content = await gate_proactive_notification(
                        user_id=user_id,
                        notification_type="weekly_digest",
                        content=brief_content,
                        urgency="low",
                        metadata={"source": "weekly_digest"},
                    )
                    esl_decision = (
                        "VETOED"
                        if not should_send
                        else (
                            "MODIFIED"
                            if final_content != brief_content
                            else "APPROVED"
                        )
                    )
                    ToolTelemetryService().record_tool_call(
                        user_id=user_id,
                        tool_name="weekly_digest",
                        source="scheduled",
                        source_ref="weekly_digest",
                        input={"prompt_inputs": {"goals": goal_text, "values": value_text}},
                        output={"content": final_content},
                        status="success" if should_send else "vetoed",
                        esl_decision=esl_decision,
                        latency_ms=None,
                    )
                    if not should_send:
                        logger.info(
                            f"⛔ ESL vetoed weekly_digest for user {user_id}"
                        )
                        continue
                    content = final_content
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
                    logger.warning(
                        f"[Scheduler] Weekly digest failed for user {user_id}: {e}"
                    )

        except Exception as e:
            logger.error(f"[Scheduler] Weekly digest job failed: {e}")

    async def _generate_pre_meeting_briefs(self):
        """
        Generate a pre-meeting brief for any meeting starting within 60 minutes
        that doesn't already have one. Runs every 15 minutes.
        """
        logger.info("[Scheduler] Checking for upcoming meetings requiring briefs…")
        try:
            from routes.notifications import create_notification
            from services.context_manager import ContextManager
            from langchain_core.messages import HumanMessage
            from langchain_groq import ChatGroq
            from config import settings

            now = datetime.utcnow()
            window_end = datetime(
                now.year, now.month, now.day, now.hour, now.minute
            ).__class__(now.year, now.month, now.day, now.hour, now.minute)
            # Events starting between now and 60 minutes from now
            import datetime as dt_module

            window_end = now + dt_module.timedelta(minutes=60)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Get events starting in the next 60 minutes for all users
                    cur.execute(
                        """
                        SELECT e.user_id, e.title, e.start_time, e.location, e.description
                        FROM events e
                        WHERE e.start_time >= %s
                          AND e.start_time <= %s
                        ORDER BY e.start_time ASC
                        """,
                        (now, window_end),
                    )
                    upcoming = cur.fetchall()

            if not upcoming:
                logger.info("[Scheduler] No upcoming meetings in the next 60 minutes.")
                return

            ctx = ContextManager()
            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                groq_api_key=settings.GROQ_API_KEY,
                temperature=0.5,
            )

            briefs_created = 0
            for row in upcoming:
                user_id = str(row["user_id"])
                event_title = row["title"] or "Meeting"
                event_start = row["start_time"]
                event_location = row.get("location") or ""
                event_start_iso = event_start.isoformat() if event_start else ""

                # Dedup: skip if brief already exists for this event start time
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT 1 FROM user_notifications
                            WHERE user_id = %s
                              AND metadata->>'subtype' = 'pre_meeting_brief'
                              AND metadata->>'event_start' = %s
                            LIMIT 1
                            """,
                            (user_id, event_start_iso),
                        )
                        if cur.fetchone():
                            continue  # Brief already sent for this event

                try:
                    # Gather user context for the brief
                    goals = await ctx.get_active_goals(user_id)
                    goal_text = "\n".join(
                        f"- {g.get('title', g) if isinstance(g, dict) else g.title}"
                        for g in goals[:3]
                    )

                    minutes_until = int(
                        (event_start.replace(tzinfo=None) - now).total_seconds() / 60
                    )
                    location_note = f" at {event_location}" if event_location else ""

                    prompt = (
                        f'A user has a meeting in {minutes_until} minutes: "{event_title}"{location_note}.\n'
                        f"Active goals:\n{goal_text or 'None'}\n\n"
                        "Write a brief 2–3 sentence pre-meeting note. "
                        "Mention what to focus on and one useful question to consider. "
                        "Be specific and practical, not generic."
                    )

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    brief_text = (response.content or "").strip()

                    if not brief_text:
                        continue

                    brief_content = brief_text
                    meta = {
                        "subtype": "pre_meeting_brief",
                        "event_title": event_title,
                        "event_start": event_start_iso,
                        "source": "scheduler",
                    }
                    should_send, final_content = await gate_proactive_notification(
                        user_id=user_id,
                        notification_type="pre_meeting_brief",
                        content=brief_content,
                        urgency="medium",
                        metadata=meta,
                    )
                    esl_decision = (
                        "VETOED"
                        if not should_send
                        else (
                            "MODIFIED"
                            if final_content != brief_content
                            else "APPROVED"
                        )
                    )
                    ToolTelemetryService().record_tool_call(
                        user_id=user_id,
                        tool_name="pre_meeting_brief",
                        source="scheduled",
                        source_ref="pre_meeting_brief",
                        input={
                            "prompt_inputs": {
                                "event_title": event_title,
                                "minutes_until": minutes_until,
                                "goals": goal_text,
                            }
                        },
                        output={"content": final_content},
                        status="success" if should_send else "vetoed",
                        esl_decision=esl_decision,
                        latency_ms=None,
                    )
                    if not should_send:
                        logger.info(
                            f"⛔ ESL vetoed pre_meeting_brief for user {user_id}"
                        )
                        continue
                    brief_text = final_content
                    with get_db_connection() as conn:
                        create_notification(
                            conn,
                            user_id=user_id,
                            type="brief",
                            title=f"Pre-meeting brief: {event_title}",
                            message=brief_text[:500],
                            metadata=meta,
                        )
                    briefs_created += 1

                except Exception as e:
                    logger.warning(
                        f"[Scheduler] Pre-meeting brief failed for user {user_id}: {e}"
                    )

            logger.info(
                f"[Scheduler] Pre-meeting briefs complete: {briefs_created} created."
            )

        except Exception as e:
            logger.error(f"[Scheduler] Pre-meeting brief job failed: {e}")

    async def _generate_daily_focus_plan(self):
        """
        Generate a daily focus plan for all users at 8 AM.
        Uses today's events, tasks due soon, and active goals to suggest priorities.
        """
        logger.info("[Scheduler] Generating daily focus plans…")
        try:
            from routes.notifications import create_notification
            from services.context_manager import ContextManager
            from services.context_snapshot import ContextSnapshotService
            from langchain_core.messages import HumanMessage
            from langchain_groq import ChatGroq
            from config import settings

            today_str = datetime.utcnow().strftime("%Y-%m-%d")

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users LIMIT 100")
                    users = cur.fetchall()

            ContextManager()
            snapshot_svc = ContextSnapshotService()
            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                groq_api_key=settings.GROQ_API_KEY,
                temperature=0.6,
            )

            for user_row in users:
                user_id = str(user_row["id"])
                try:
                    # Dedup: skip if daily focus already sent today
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT 1 FROM user_notifications
                                WHERE user_id = %s
                                  AND metadata->>'subtype' = 'daily_focus'
                                  AND created_at::date = CURRENT_DATE
                                LIMIT 1
                                """,
                                (user_id,),
                            )
                            if cur.fetchone():
                                continue

                    snapshot = snapshot_svc.compute(user_id)

                    events = snapshot.get("upcoming_events", [])
                    tasks = snapshot.get("tasks_due_soon", [])
                    goals = snapshot.get("active_goals", [])

                    if not events and not tasks and not goals:
                        continue  # No data for this user

                    events_text = (
                        "\n".join(
                            f"- {e['title']} at {e['start_time'][:16] if e.get('start_time') else 'TBD'}"
                            for e in events[:4]
                        )
                        or "None"
                    )
                    tasks_text = (
                        "\n".join(
                            f"- {t['title']} (due {t['due_date'][:10] if t.get('due_date') else 'soon'}, priority {t.get('priority', 5)})"  # noqa: E501
                            for t in tasks[:5]
                        )
                        or "None"
                    )
                    goals_text = (
                        "\n".join(f"- {g['title']}" for g in goals[:3]) or "None"
                    )
                    pressure = snapshot.get("calendar_pressure", "light")

                    prompt = (
                        f"Today's schedule ({today_str}) — calendar pressure: {pressure}.\n"
                        f"Upcoming events:\n{events_text}\n"
                        f"Tasks due soon:\n{tasks_text}\n"
                        f"Active goals:\n{goals_text}\n\n"
                        "Write a concise daily focus plan (3 bullet points max). "
                        "Each bullet: one concrete priority. "
                        "Be direct and actionable, not motivational."
                    )

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    plan_text = (response.content or "").strip()

                    if not plan_text:
                        continue

                    brief_content = plan_text
                    meta = {"subtype": "daily_focus", "source": "scheduler"}
                    should_send, final_content = await gate_proactive_notification(
                        user_id=user_id,
                        notification_type="daily_focus_plan",
                        content=brief_content,
                        urgency="low",
                        metadata=meta,
                    )
                    esl_decision = (
                        "VETOED"
                        if not should_send
                        else (
                            "MODIFIED"
                            if final_content != brief_content
                            else "APPROVED"
                        )
                    )
                    ToolTelemetryService().record_tool_call(
                        user_id=user_id,
                        tool_name="daily_focus_plan",
                        source="scheduled",
                        source_ref="daily_focus_plan",
                        input={
                            "prompt_inputs": {
                                "events": events_text,
                                "tasks": tasks_text,
                                "goals": goals_text,
                                "pressure": pressure,
                            }
                        },
                        output={"content": final_content},
                        status="success" if should_send else "vetoed",
                        esl_decision=esl_decision,
                        latency_ms=None,
                    )
                    if not should_send:
                        logger.info(
                            f"⛔ ESL vetoed daily_focus_plan for user {user_id}"
                        )
                        continue
                    plan_text = final_content
                    with get_db_connection() as conn:
                        create_notification(
                            conn,
                            user_id=user_id,
                            type="info",
                            title="Your focus for today",
                            message=plan_text[:500],
                            metadata=meta,
                        )

                except Exception as e:
                    logger.warning(
                        f"[Scheduler] Daily focus failed for user {user_id}: {e}"
                    )

            logger.info("[Scheduler] Daily focus plans complete.")

        except Exception as e:
            logger.error(f"[Scheduler] Daily focus job failed: {e}")

    async def _generate_deadline_warnings(self):
        """
        Warn users about tasks due within the next 24 hours.
        Runs at 8:05 AM daily. No LLM needed — pure SQL-driven notifications.
        """
        logger.info("[Scheduler] Checking for deadline warnings…")
        try:
            from routes.notifications import create_notification
            import datetime as dt_module

            now = datetime.utcnow()
            in_24h = now + dt_module.timedelta(hours=24)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT t.id, t.user_id, t.title, t.due_date, t.priority,
                               p.title AS project_title
                        FROM tasks t
                        LEFT JOIN projects p ON p.id = t.project_id
                        WHERE t.status NOT IN ('done', 'cancelled')
                          AND t.due_date IS NOT NULL
                          AND t.due_date >= %s
                          AND t.due_date <= %s
                        ORDER BY t.due_date ASC, t.priority DESC
                        """,
                        (now, in_24h),
                    )
                    due_tasks = cur.fetchall()

            if not due_tasks:
                logger.info("[Scheduler] No deadline warnings needed.")
                return

            warnings_created = 0
            for row in due_tasks:
                task_id = str(row["id"])
                user_id = str(row["user_id"])
                task_title = row["title"]
                due_date = row["due_date"]
                project_title = row.get("project_title")

                # Dedup: one warning per task per day
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT 1 FROM user_notifications
                            WHERE user_id = %s
                              AND metadata->>'subtype' = 'deadline_warning'
                              AND metadata->>'task_id' = %s
                              AND created_at::date = CURRENT_DATE
                            LIMIT 1
                            """,
                            (user_id, task_id),
                        )
                        if cur.fetchone():
                            continue

                due_str = due_date.strftime("%-I:%M %p") if due_date else "today"
                context_note = f" ({project_title})" if project_title else ""
                message = f"Due at {due_str}{context_note}. Don't let it slip through."

                brief_content = message
                meta = {
                    "subtype": "deadline_warning",
                    "task_id": task_id,
                    "source": "scheduler",
                }
                should_send, final_content = await gate_proactive_notification(
                    user_id=user_id,
                    notification_type="deadline_warning",
                    content=brief_content,
                    urgency="medium",
                    metadata=meta,
                )
                esl_decision = (
                    "VETOED"
                    if not should_send
                    else (
                        "MODIFIED"
                        if final_content != brief_content
                        else "APPROVED"
                    )
                )
                ToolTelemetryService().record_tool_call(
                    user_id=user_id,
                    tool_name="deadline_warning",
                    source="scheduled",
                    source_ref="deadline_warning",
                    input={
                        "prompt_inputs": {
                            "task_title": task_title,
                            "task_id": task_id,
                            "due_str": due_str,
                        }
                    },
                    output={"content": final_content},
                    status="success" if should_send else "vetoed",
                    esl_decision=esl_decision,
                    latency_ms=None,
                )
                if not should_send:
                    logger.info(
                        f"⛔ ESL vetoed deadline_warning for user {user_id}"
                    )
                    continue
                message = final_content

                with get_db_connection() as conn:
                    create_notification(
                        conn,
                        user_id=user_id,
                        type="warning",
                        title=f"Due soon: {task_title}",
                        message=message,
                        metadata=meta,
                    )
                warnings_created += 1

            logger.info(
                f"[Scheduler] Deadline warnings complete: {warnings_created} created."
            )

        except Exception as e:
            logger.error(f"[Scheduler] Deadline warnings job failed: {e}")

    async def _generate_project_status_snapshot(self):
        """
        Generate a weekly project status snapshot for each user.
        Runs every Friday at 5 PM. Summarises active projects — progress,
        stalls, and one suggested action for the week ahead.
        """
        logger.info("[Scheduler] Generating project status snapshots…")
        try:
            from routes.notifications import create_notification
            from langchain_core.messages import HumanMessage
            from langchain_groq import ChatGroq
            from config import settings

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT p.id, p.user_id, p.title,
                               COUNT(t.id) FILTER (
                                   WHERE t.status NOT IN ('done', 'cancelled')
                               ) AS open_tasks,
                               COUNT(t.id) FILTER (
                                   WHERE t.status = 'done'
                               ) AS done_tasks,
                               COUNT(t.id) FILTER (
                                   WHERE t.status NOT IN ('done', 'cancelled')
                                     AND t.due_date IS NOT NULL
                                     AND t.due_date < NOW()
                               ) AS overdue_tasks
                        FROM projects p
                        LEFT JOIN tasks t ON t.project_id = p.id
                        WHERE p.status = 'active'
                        GROUP BY p.id, p.user_id, p.title
                        ORDER BY p.user_id, p.updated_at DESC
                        """,
                    )
                    projects = cur.fetchall()

            if not projects:
                logger.info("[Scheduler] No active projects for status snapshot.")
                return

            # Group by user
            from collections import defaultdict

            by_user: dict = defaultdict(list)
            for row in projects:
                by_user[str(row["user_id"])].append(row)

            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                groq_api_key=settings.GROQ_API_KEY,
                temperature=0.5,
            )

            snapshots_created = 0
            for user_id, user_projects in by_user.items():
                try:
                    # Dedup: one snapshot per user per week (check last 6 days)
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT 1 FROM user_notifications
                                WHERE user_id = %s
                                  AND metadata->>'subtype' = 'project_status_snapshot'
                                  AND created_at >= NOW() - INTERVAL '6 days'
                                LIMIT 1
                                """,
                                (user_id,),
                            )
                            if cur.fetchone():
                                continue

                    project_lines = "\n".join(
                        f"- {p['title']}: {p['open_tasks']} open task(s), "
                        f"{p['done_tasks']} done"
                        + (
                            f", {p['overdue_tasks']} overdue"
                            if p["overdue_tasks"]
                            else ""
                        )
                        for p in user_projects[:5]
                    )

                    prompt = (
                        "Weekly project review. Active projects:\n"
                        f"{project_lines}\n\n"
                        "Write a 2–3 sentence status summary for this user. "
                        "Acknowledge momentum where it exists. Flag stalled projects. "
                        "Suggest one concrete action for next week. Be direct."
                    )

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    summary = (response.content or "").strip()

                    if not summary:
                        continue

                    brief_content = summary
                    meta = {
                        "subtype": "project_status_snapshot",
                        "project_count": len(user_projects),
                        "source": "scheduler",
                    }
                    should_send, final_content = await gate_proactive_notification(
                        user_id=user_id,
                        notification_type="project_status_snapshot",
                        content=brief_content,
                        urgency="low",
                        metadata=meta,
                    )
                    esl_decision = (
                        "VETOED"
                        if not should_send
                        else (
                            "MODIFIED"
                            if final_content != brief_content
                            else "APPROVED"
                        )
                    )
                    ToolTelemetryService().record_tool_call(
                        user_id=user_id,
                        tool_name="project_status_snapshot",
                        source="scheduled",
                        source_ref="project_status_snapshot",
                        input={"prompt_inputs": {"project_lines": project_lines}},
                        output={"content": final_content},
                        status="success" if should_send else "vetoed",
                        esl_decision=esl_decision,
                        latency_ms=None,
                    )
                    if not should_send:
                        logger.info(
                            f"⛔ ESL vetoed project_status_snapshot for user {user_id}"
                        )
                        continue
                    summary = final_content
                    with get_db_connection() as conn:
                        create_notification(
                            conn,
                            user_id=user_id,
                            type="info",
                            title="Weekly project snapshot",
                            message=summary[:500],
                            metadata=meta,
                        )
                    snapshots_created += 1

                except Exception as e:
                    logger.warning(
                        f"[Scheduler] Project snapshot failed for user {user_id}: {e}"
                    )

            logger.info(
                f"[Scheduler] Project status snapshots complete: {snapshots_created} created."
            )

        except Exception as e:
            logger.error(f"[Scheduler] Project status snapshot job failed: {e}")

    async def _generate_related_items_clusters(self):
        """
        Find clusters of related tasks, events, and goals that share significant keywords.
        Runs every Sunday at 6 PM. Creates a notification when 2+ item types overlap on
        the same topic, surfacing connections the user may not have noticed.
        """
        import re
        from collections import defaultdict

        logger.info("[Scheduler] Running related-items clustering…")

        # Common English stop-words we exclude from keyword matching
        STOP_WORDS = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "have",
            "will",
            "been",
            "are",
            "our",
            "your",
            "their",
            "about",
            "some",
            "into",
            "more",
            "when",
            "than",
            "then",
            "they",
            "what",
            "also",
            "just",
            "been",
            "like",
            "each",
            "make",
            "over",
            "such",
            "after",
        }

        def keywords(text: str) -> set:
            words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
            return {w for w in words if w not in STOP_WORDS}

        try:
            from routes.notifications import create_notification
            import datetime as dt_module

            now = datetime.utcnow()
            in_7_days = now + dt_module.timedelta(days=7)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users LIMIT 100")
                    users = cur.fetchall()

            notifications_created = 0

            for user_row in users:
                user_id = str(user_row["id"])
                try:
                    # Dedup: one cluster notification per user per week
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT 1 FROM user_notifications
                                WHERE user_id = %s
                                  AND metadata->>'subtype' = 'related_items_cluster'
                                  AND created_at >= NOW() - INTERVAL '6 days'
                                LIMIT 1
                                """,
                                (user_id,),
                            )
                            if cur.fetchone():
                                continue

                    # Collect items
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT title FROM tasks WHERE user_id = %s AND status NOT IN ('done','cancelled') LIMIT 30",  # noqa: E501
                                (user_id,),
                            )
                            tasks = [r["title"] for r in cur.fetchall()]

                            cur.execute(
                                "SELECT title FROM events WHERE user_id = %s AND start_time >= %s AND start_time <= %s LIMIT 20",  # noqa: E501
                                (user_id, now, in_7_days),
                            )
                            events = [r["title"] for r in cur.fetchall()]

                            cur.execute(
                                "SELECT title FROM goals WHERE user_id = %s AND status = 'active' LIMIT 10",
                                (user_id,),
                            )
                            goals = [r["title"] for r in cur.fetchall()]

                    if not (tasks and (events or goals)):
                        continue  # not enough cross-type items to cluster

                    # Build keyword → [(type, title)] index
                    kw_index: dict = defaultdict(list)
                    for t in tasks:
                        for kw in keywords(t):
                            kw_index[kw].append(("task", t))
                    for e in events:
                        for kw in keywords(e):
                            kw_index[kw].append(("event", e))
                    for g in goals:
                        for kw in keywords(g):
                            kw_index[kw].append(("goal", g))

                    # Keep clusters with 2+ distinct item types
                    clusters = {
                        kw: items
                        for kw, items in kw_index.items()
                        if len({i[0] for i in items}) >= 2
                    }

                    if not clusters:
                        continue

                    # Pick the top 2 clusters (most diverse cross-type overlap)
                    top = sorted(
                        clusters.items(),
                        key=lambda x: len({i[0] for i in x[1]}),
                        reverse=True,
                    )[:2]

                    lines = []
                    for kw, items in top:
                        types = {i[0] for i in items}
                        titles = list({i[1] for i in items})[:3]
                        lines.append(
                            f'"{kw.title()}": '
                            + ", ".join(f'"{t}"' for t in titles)
                            + f" ({', '.join(sorted(types))})"
                        )

                    message = (
                        "Items across your tasks, events, and goals share a common thread:\n"
                        + "\n".join(f"• {line}" for line in lines)
                        + "\nConsider linking them or reviewing them together."
                    )

                    brief_content = message
                    meta = {
                        "subtype": "related_items_cluster",
                        "cluster_keywords": [kw for kw, _ in top],
                        "source": "scheduler",
                    }
                    should_send, final_content = await gate_proactive_notification(
                        user_id=user_id,
                        notification_type="related_items_cluster",
                        content=brief_content,
                        urgency="low",
                        metadata=meta,
                    )
                    esl_decision = (
                        "VETOED"
                        if not should_send
                        else (
                            "MODIFIED"
                            if final_content != brief_content
                            else "APPROVED"
                        )
                    )
                    ToolTelemetryService().record_tool_call(
                        user_id=user_id,
                        tool_name="related_items_cluster",
                        source="scheduled",
                        source_ref="related_items_cluster",
                        input={"prompt_inputs": {"cluster_keywords": [kw for kw, _ in top]}},
                        output={"content": final_content},
                        status="success" if should_send else "vetoed",
                        esl_decision=esl_decision,
                        latency_ms=None,
                    )
                    if not should_send:
                        logger.info(
                            f"⛔ ESL vetoed related_items_cluster for user {user_id}"
                        )
                        continue
                    message = final_content

                    with get_db_connection() as conn:
                        create_notification(
                            conn,
                            user_id=user_id,
                            type="info",
                            title="Connected items this week",
                            message=message[:500],
                            metadata=meta,
                        )
                    notifications_created += 1

                except Exception as e:
                    logger.warning(
                        f"[Scheduler] Related-items clustering failed for user {user_id}: {e}"
                    )

            logger.info(
                f"[Scheduler] Related-items clustering complete: {notifications_created} notifications."
            )

        except Exception as e:
            logger.error(f"[Scheduler] Related-items clustering job failed: {e}")

    async def _prune_old_telemetry(self):
        """
        Sprint E Task 1: drop telemetry rows older than RETENTION_DAYS from
        `tool_call_events` (uses `created_at`) and `esl_audit_log` (uses
        `timestamp`). Daily at 04:00 UTC. Errors are logged, not raised, so a
        broken prune doesn't take down the scheduler thread.
        """
        try:
            from config import settings

            days = int(getattr(settings, "RETENTION_DAYS", 90))

            tool_deleted = 0
            audit_deleted = 0
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM tool_call_events "
                        "WHERE created_at < NOW() - (INTERVAL '1 day' * %s)",
                        (days,),
                    )
                    tool_deleted = cur.rowcount or 0

                    cur.execute(
                        "DELETE FROM esl_audit_log "
                        "WHERE timestamp < NOW() - (INTERVAL '1 day' * %s)",
                        (days,),
                    )
                    audit_deleted = cur.rowcount or 0

            logger.info(
                f"pruned {tool_deleted} tool_call_events, "
                f"{audit_deleted} esl_audit_log rows older than {days}d"
            )
        except Exception as e:
            logger.error(f"[Scheduler] prune_old_telemetry failed: {e}")

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
                    "next_run": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
                for job in jobs
            ],
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
        embedding_service = EmbeddingService(os.getenv("GEMINI_API_KEY"))

        context_manager = ContextManager(
            weaviate_client=weaviate_client, embedding_service=embedding_service
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

        for job in status["jobs"]:
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
