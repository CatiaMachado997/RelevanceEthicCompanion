"""
Ethic Companion - Backend API
Main FastAPI application entry point

Purpose: AI as our Companion in Decision-Making
Core Value: Trust over Engagement
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os

# Allow oauthlib to accept when Google returns a superset of requested scopes
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from fastapi import Request, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from utils.rate_limit import limiter
from scripts.run_migrations import run_migrations

# Initialize background scheduler (global instance)
_scheduler = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global _scheduler

    # Startup
    print("🚀 Ethic Companion Backend Starting...")
    print("⚖️  Ethical Safeguard Layer: ACTIVE")
    print("🎯 Mission: Trust over Engagement")

    from utils.db import open_pool, close_pool

    open_pool()

    try:
        n_applied = run_migrations()
        if n_applied:
            logger.info(f"applied {n_applied} migration(s)")
        else:
            logger.info("schema up to date")
    except Exception:
        logger.exception("Migration failed on startup; refusing to serve traffic")
        raise

    # Auto-migrate: ensure extra columns exist in user_settings
    try:
        from utils.db import get_db_connection

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for col, defn in [
                    ("weight_goal_alignment", "FLOAT DEFAULT 1.0"),
                    ("weight_time_sensitivity", "FLOAT DEFAULT 1.0"),
                    ("weight_personal_values", "FLOAT DEFAULT 1.0"),
                    ("weight_context_relevance", "FLOAT DEFAULT 1.0"),
                    ("timezone", "TEXT"),
                    ("language", "TEXT"),
                    ("status", "TEXT DEFAULT 'available'"),
                    ("status_until", "TIMESTAMPTZ"),
                ]:
                    cur.execute(
                        f"ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS {col} {defn}"
                    )
        logger.debug("user_settings columns verified")
    except Exception as e:
        logger.warning(
            f"Could not verify user_settings columns (DB may be unavailable): {e}"
        )

    # Auto-migrate V4+ tables (idempotent — safe to run on every startup)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS daily_insights (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      content TEXT NOT NULL,
                      date DATE NOT NULL DEFAULT CURRENT_DATE,
                      generated_at TIMESTAMPTZ DEFAULT NOW(),
                      UNIQUE(user_id, date)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS goal_milestones (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      title TEXT NOT NULL,
                      completed BOOLEAN DEFAULT FALSE,
                      created_at TIMESTAMPTZ DEFAULT NOW(),
                      updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_goal_milestones_goal ON goal_milestones(goal_id)"
                )
                # Sprint 3: Documents
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                      id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      filename      TEXT NOT NULL,
                      content_type  TEXT NOT NULL,
                      size_bytes    INTEGER NOT NULL DEFAULT 0,
                      status        TEXT NOT NULL DEFAULT 'processing'
                                    CHECK (status IN ('processing', 'ready', 'failed')),
                      chunk_count   INTEGER NOT NULL DEFAULT 0,
                      error_message TEXT,
                      created_at    TIMESTAMPTZ DEFAULT NOW(),
                      updated_at    TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_documents_status  ON documents(status)"
                )
                # Sprint 4: Projects
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      title       TEXT NOT NULL,
                      description TEXT,
                      status      TEXT NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active', 'completed', 'archived')),
                      goal_id     UUID REFERENCES goals(id) ON DELETE SET NULL,
                      created_at  TIMESTAMPTZ DEFAULT NOW(),
                      updated_at  TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_projects_status  ON projects(status)"
                )
                # Sprint 4: Tasks
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                      id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      project_id     UUID REFERENCES projects(id) ON DELETE SET NULL,
                      title          TEXT NOT NULL,
                      description    TEXT,
                      status         TEXT NOT NULL DEFAULT 'todo'
                                     CHECK (status IN ('todo', 'in_progress', 'done', 'cancelled')),
                      priority       INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
                      due_date       TIMESTAMPTZ,
                      source_origin  TEXT NOT NULL DEFAULT 'manual',
                      ai_confidence  FLOAT,
                      user_confirmed BOOLEAN NOT NULL DEFAULT TRUE,
                      created_at     TIMESTAMPTZ DEFAULT NOW(),
                      updated_at     TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_id    ON tasks(user_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status)"
                )
        logger.debug("V4+ tables verified")
    except Exception as e:
        logger.warning(f"Could not verify V4+ tables: {e}")

    if settings.ENVIRONMENT != "development":
        if not settings.AUTH_ENFORCEMENT_ENABLED:
            logger.warning(
                "⚠️  AUTH_ENFORCEMENT_ENABLED is false in %s. Protected routes may allow fallback behavior.",
                settings.ENVIRONMENT,
            )
        if not settings.AUTH_ENFORCE_READ_ROUTES:
            logger.warning(
                "⚠️  AUTH_ENFORCE_READ_ROUTES is false in %s. Read routes are not strictly authenticated.",
                settings.ENVIRONMENT,
            )

    # Initialize and start background scheduler (Phase 5)
    try:
        from services.scheduler import BackgroundScheduler, set_scheduler_instance
        from services.data_ingestion import DataIngestionService
        from services.context_manager import ContextManager
        from services.embedding_service import EmbeddingService
        from utils.weaviate_client import get_weaviate_client

        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
        context_manager = ContextManager(
            weaviate_client=weaviate_client, embedding_service=embedding_service
        )
        data_ingestion = DataIngestionService(context_manager)

        _scheduler = BackgroundScheduler(data_ingestion)
        _scheduler.start()
        set_scheduler_instance(_scheduler)

        print("🔄 Background Scheduler: STARTED")
        print("   - Calendar sync: Every 15 minutes")
    except Exception as e:
        logger.warning(f"⚠️  Background scheduler failed to start: {e}")
        logger.warning(
            "   Continuing without scheduled syncing (manual sync still works)"
        )

    yield

    # Shutdown
    print("👋 Shutting down gracefully...")

    if _scheduler:
        _scheduler.stop()
        print("✅ Background scheduler stopped")

    close_pool()


app = FastAPI(
    title="Ethic Companion API",
    description="AI Companion with Ethical Safeguards - Trust over Engagement",
    version="1.0.0",
    lifespan=lifespan,
)

from utils.errors import register_error_handlers

register_error_handlers(app)


async def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    """Rate limit handler that logs auth-endpoint violations to the audit log."""
    assert isinstance(exc, RateLimitExceeded)
    try:
        path = request.url.path
        if "/auth/" in path or "/tools/" in path:
            from utils.auth_audit import log_auth_event

            log_auth_event(
                event="rate_limited",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                detail={"path": path, "limit": str(exc.detail)},
            )
    except Exception:
        pass
    # slowapi's default handler is synchronous and returns a Response directly.
    return _rate_limit_exceeded_handler(request, exc)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Ethic Companion API",
        "version": "1.0.0",
        "status": "operational",
        "mission": "Trust over Engagement",
        "esl_status": "active",
    }


# Import routers
from routes import (
    auth,
    values,
    chat,
    goals,
    transparency,
    relevance,
    data_sources,
    profile,
    notifications,
    feedback,
    search,
    documents,
    projects,
    tasks,
    context,
    folders,
    dashboard,
    connectors,
    weekly_review,
    today,
    onboarding,
)
from routes import settings as settings_router
from routes.insight import router as insight_router
from routes.health import router as health_router
from routes.status import router as status_router

# Register routers
app.include_router(health_router)
app.include_router(auth.router)
app.include_router(values.router)
app.include_router(chat.router)
app.include_router(goals.router)
app.include_router(transparency.router)
app.include_router(relevance.router)
app.include_router(data_sources.router)  # Phase 5: Google Calendar integration
app.include_router(profile.router)
app.include_router(notifications.router)
app.include_router(settings_router.router)
app.include_router(feedback.router)
app.include_router(search.router)
app.include_router(insight_router)
app.include_router(documents.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(context.router)
app.include_router(folders.router)
app.include_router(dashboard.router)
app.include_router(status_router)
app.include_router(connectors.router, prefix="/api/connectors", tags=["connectors"])
app.include_router(weekly_review.router, prefix="/api/weekly-review", tags=["weekly-review"])
app.include_router(today.router, prefix="/api/today", tags=["today"])
app.include_router(onboarding.router)

from routes import tool_marketplace

app.include_router(tool_marketplace.router)

# Sprint 2a: Expose all routes as MCP tools
from fastapi_mcp import FastApiMCP

mcp = FastApiMCP(app)
mcp.mount_http()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
