"""
Configuration Management
Loads environment variables and application settings
"""

from pydantic import computed_field, ConfigDict
from pydantic_settings import BaseSettings
from typing import List


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
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/data-sources/oauth/google-calendar/callback"

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
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    model_config = ConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
