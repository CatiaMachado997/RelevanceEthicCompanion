"""
Configuration Management
Loads environment variables and application settings
"""

from pydantic import computed_field, ConfigDict
from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Application Settings"""
    
    # PostgreSQL (M1 - Structured Memory)
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Weaviate (M2 - Semantic Memory)
    WEAVIATE_URL: str = "http://localhost:8080"

    # APIs - V1 (being phased out)
    GROQ_API_KEY: str

    # APIs - V2 (new)
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Google OAuth (Phase 5: Calendar Integration)
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/data-sources/oauth/google_calendar/callback"
    GMAIL_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/data-sources/oauth/gmail/callback"

    # Application
    ENVIRONMENT: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    AUTH_ENFORCEMENT_ENABLED: bool = False
    AUTH_ENFORCE_WRITE_ROUTES: bool = True
    AUTH_ENFORCE_READ_ROUTES: bool = False

    # Supabase auth
    SUPABASE_URL: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # JWT / Authentication
    SECRET_KEY: str
    # Fernet key for credential encryption.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""
    # Cookie security — False for local dev, True for production
    COOKIE_SECURE: bool = False
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Slack OAuth (Phase X: Slack Integration)
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_REDIRECT_URI: str = "http://localhost:8000/api/data-sources/oauth/slack/callback"

    # GitHub OAuth (Tool Marketplace)
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Notion OAuth (Tool Marketplace)
    NOTION_CLIENT_ID: str = ""
    NOTION_CLIENT_SECRET: str = ""

    # Composio — managed tool integrations (replaces per-connector OAuth boilerplate)
    # Get your key free at https://app.composio.dev/settings (API Keys tab)
    COMPOSIO_API_KEY: str = ""

    # Backend URL for OAuth redirects
    BACKEND_URL: str = "http://localhost:8000"

    # Frontend URL
    FRONTEND_URL: str = "http://localhost:3000"

    # Langfuse (optional — observability for LangGraph nodes)
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Feature flags
    USE_LANGGRAPH: bool = True  # orchestrator_v2 removed in sprint-2a; LangGraph is the only orchestrator

    # Dev mode: override mock user ID to match the real user who connected OAuth
    DEV_USER_ID: str = "00000000-0000-0000-0000-000000000000"

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
