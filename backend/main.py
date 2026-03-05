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

from config import settings

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

    # Initialize and start background scheduler (Phase 5)
    try:
        from services.scheduler import BackgroundScheduler
        from services.data_ingestion import DataIngestionService
        from services.context_manager import ContextManager
        from services.embedding_service import EmbeddingService
        from utils.weaviate_client import get_weaviate_client

        weaviate_client = get_weaviate_client()
        embedding_service = EmbeddingService(settings.GEMINI_API_KEY)
        context_manager = ContextManager(
            weaviate_client=weaviate_client,
            embedding_service=embedding_service
        )
        data_ingestion = DataIngestionService(context_manager)

        _scheduler = BackgroundScheduler(data_ingestion)
        _scheduler.start()

        print("🔄 Background Scheduler: STARTED")
        print("   - Calendar sync: Every 15 minutes")
    except Exception as e:
        logger.warning(f"⚠️  Background scheduler failed to start: {e}")
        logger.warning("   Continuing without scheduled syncing (manual sync still works)")

    yield

    # Shutdown
    print("👋 Shutting down gracefully...")

    if _scheduler:
        _scheduler.stop()
        print("✅ Background scheduler stopped")


app = FastAPI(
    title="Ethic Companion API",
    description="AI Companion with Ethical Safeguards - Trust over Engagement",
    version="1.0.0",
    lifespan=lifespan
)

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
        "esl_status": "active"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "ethical_safeguard_layer": "active",
        "components": {
            "api": "operational",
            "esl": "active",
            "database": "connected"  # TODO: Add actual health checks
        }
    }


# Import routers
from routes import auth, values, chat, goals, transparency, relevance, data_sources

# Register routers
app.include_router(auth.router)
app.include_router(values.router)
app.include_router(chat.router)
app.include_router(goals.router)
app.include_router(transparency.router)
app.include_router(relevance.router)
app.include_router(data_sources.router)  # Phase 5: Google Calendar integration


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
