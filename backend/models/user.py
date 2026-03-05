"""
User Models

Pydantic models for user data and authentication
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


class User(BaseModel):
    """User model"""
    id: str
    email: EmailStr
    created_at: datetime
    updated_at: Optional[datetime] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
            "example": {
                "id": "user_123",
                "email": "user@example.com",
                "created_at": "2025-11-04T10:00:00Z",
                "full_name": "Jane Doe"
            }
        })


class UserCreate(BaseModel):
    """Model for user creation"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    """Model for user updates"""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserProfile(BaseModel):
    """Extended user profile"""
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    total_boundaries: int = 0
    total_interactions: int = 0
    esl_approval_rate: float = Field(default=0.0, ge=0.0, le=1.0)
