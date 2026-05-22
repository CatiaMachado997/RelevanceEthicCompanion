"""
Configuration Management
Loads environment variables and application settings
"""

import os
import logging as _logging

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

_secrets_logger = _logging.getLogger(__name__)

# Ordered list of (GCP secret name → env var name) pairs.
_GCP_SECRETS: list[tuple[str, str]] = [
    ("ethic-companion-secret-key", "SECRET_KEY"),
    ("ethic-companion-encryption-key", "ENCRYPTION_KEY"),
    ("ethic-companion-gemini-api-key", "GEMINI_API_KEY"),
    ("ethic-companion-groq-api-key", "GROQ_API_KEY"),
    ("ethic-companion-tavily-api-key", "TAVILY_API_KEY"),
    ("ethic-companion-composio-api-key", "COMPOSIO_API_KEY"),
    ("ethic-companion-google-oauth-secret", "GOOGLE_OAUTH_CLIENT_SECRET"),
    ("ethic-companion-slack-client-secret", "SLACK_CLIENT_SECRET"),
    ("ethic-companion-github-client-secret", "GITHUB_CLIENT_SECRET"),
    ("ethic-companion-notion-client-secret", "NOTION_CLIENT_SECRET"),
    # Store as JSON array: ["https://app.example.com"] or comma-separated for pydantic parsing
    ("ethic-companion-allowed-origins", "CORS_ORIGINS"),
]


def load_secrets_from_gcp(project_id: str, client=None) -> None:
    """
    Fetch secrets from GCP Secret Manager and set them as environment variables.
    Called once at startup when ENVIRONMENT=production.
    Missing secrets log a warning but do not crash.
    Args:
        project_id: GCP project ID.
        client: optional pre-built SecretManagerServiceClient (for testing).
    """
    if not project_id:
        return
    if client is None:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
    for secret_name, env_var in _GCP_SECRETS:
        resource = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        try:
            response = client.access_secret_version(name=resource)
            value = response.payload.data.decode("utf-8").strip()
            os.environ[env_var] = value
            _secrets_logger.debug("Loaded secret %s → %s", secret_name, env_var)
        except Exception as exc:
            _secrets_logger.warning(
                "Could not load secret '%s' from GCP Secret Manager: %s",
                secret_name,
                exc,
            )


class Settings(BaseSettings):
    """Application Settings"""

    # PostgreSQL (M1 - Structured Memory)
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # mypy doesn't support decorators stacked on @property; pydantic's
    # @computed_field requires this ordering at runtime.
    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"  # noqa: E501

    # Weaviate (M2 - Semantic Memory)
    WEAVIATE_URL: str = "http://localhost:8080"

    # APIs - V1 (being phased out)
    GROQ_API_KEY: str

    # APIs - V2 (new)
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str

    # Google Cloud (optional — only needed when using GCP Secret Manager)
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Google OAuth (Phase 5: Calendar Integration)
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = (
        "http://localhost:8000/api/data-sources/oauth/google_calendar/callback"
    )
    GMAIL_OAUTH_REDIRECT_URI: str = (
        "http://localhost:8000/api/data-sources/oauth/gmail/callback"
    )

    # Application
    ENVIRONMENT: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    AUTH_ENFORCEMENT_ENABLED: bool = (
        True  # default secure; set False in local .env for dev
    )
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
    SLACK_REDIRECT_URI: str = (
        "http://localhost:8000/api/data-sources/oauth/slack/callback"
    )

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
    USE_LANGGRAPH: bool = (
        True  # orchestrator_v2 removed in sprint-2a; LangGraph is the only orchestrator
    )

    # Dev mode: override mock user ID to match the real user who connected OAuth
    DEV_USER_ID: str = "00000000-0000-0000-0000-000000000000"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# Load GCP secrets before instantiating Settings so pydantic picks them up from env.
if os.environ.get("ENVIRONMENT") == "production":
    _project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if _project:
        load_secrets_from_gcp(project_id=_project)
    else:
        _secrets_logger.warning(
            "GOOGLE_CLOUD_PROJECT not set; skipping GCP secret loading"
        )

# Required fields are loaded from environment by pydantic-settings at runtime.
settings = Settings()  # type: ignore[call-arg]
