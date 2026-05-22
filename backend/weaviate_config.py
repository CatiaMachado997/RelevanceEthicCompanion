"""
Weaviate Configuration
Schema definitions for Ethic Companion V2 semantic memory (M2)
"""

from typing import Dict, List, Any

# Collection schemas for Weaviate
WEAVIATE_SCHEMAS: List[Dict[str, Any]] = [
    {
        "class": "ConversationMemory",
        "description": "User messages and AI responses with semantic embeddings",
        "vectorizer": "none",  # We'll provide embeddings from Gemini
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "description": "Supabase UUID of the user",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "content",
                "dataType": ["text"],
                "description": "Message or response content",
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "role",
                "dataType": ["text"],
                "description": "Message role: user, assistant, or system",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "timestamp",
                "dataType": ["date"],
                "description": "ISO 8601 timestamp of the message",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "source",
                "dataType": ["text"],
                "description": "Source of the memory: chat, proactive, etc.",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "metadata",
                "dataType": ["text"],
                "description": "JSON string of additional metadata",
                "indexFilterable": False,
                "indexSearchable": False,
            },
        ],
    },
    {
        "class": "ContextualEvents",
        "description": "Calendar events and contextual events with embeddings",
        "vectorizer": "none",
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "description": "Supabase UUID of the user",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "title",
                "dataType": ["text"],
                "description": "Event title",
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "description",
                "dataType": ["text"],
                "description": "Event description or notes",
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "start_time",
                "dataType": ["date"],
                "description": "Event start time (ISO 8601)",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "end_time",
                "dataType": ["date"],
                "description": "Event end time (ISO 8601)",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "source",
                "dataType": ["text"],
                "description": "Source: google_calendar, manual, etc.",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "event_id",
                "dataType": ["text"],
                "description": "External event ID (e.g., Google Calendar ID)",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "metadata",
                "dataType": ["text"],
                "description": "JSON string of additional metadata",
                "indexFilterable": False,
                "indexSearchable": False,
            },
        ],
    },
    {
        "class": "UserGoals",
        "description": "User goals and objectives with semantic embeddings",
        "vectorizer": "none",
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "description": "Supabase UUID of the user",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "title",
                "dataType": ["text"],
                "description": "Goal title",
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "description",
                "dataType": ["text"],
                "description": "Detailed goal description",
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "status",
                "dataType": ["text"],
                "description": "Goal status: active, completed, paused",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "priority",
                "dataType": ["text"],
                "description": "Priority: high, medium, low",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "deadline",
                "dataType": ["date"],
                "description": "Goal deadline (ISO 8601)",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "created_at",
                "dataType": ["date"],
                "description": "Creation timestamp (ISO 8601)",
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "metadata",
                "dataType": ["text"],
                "description": "JSON string of additional metadata",
                "indexFilterable": False,
                "indexSearchable": False,
            },
        ],
    },
    {
        "class": "DocumentMemory",
        "description": "Document chunks with semantic embeddings for search",
        "vectorizer": "none",
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "content",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "document_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "filename",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "chunk_index",
                "dataType": ["int"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "chunk_count",
                "dataType": ["int"],
                "indexFilterable": False,
                "indexSearchable": False,
            },
            {
                "name": "created_at",
                "dataType": ["date"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "source_type",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
        ],
    },
    {
        "class": "PlannerRunMemory",
        "description": "Per-user record of past completed planner runs, "
                       "embedded for similarity recall at planner-step start. "
                       "Sprint K.",
        "vectorizer": "none",
        "properties": [
            {
                "name": "user_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "planner_run_id",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "message_text",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": True,
            },
            {
                "name": "plan_summary",
                "dataType": ["text"],
                "indexFilterable": False,
                "indexSearchable": False,
            },
            {
                "name": "status",
                "dataType": ["text"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
            {
                "name": "created_at",
                "dataType": ["date"],
                "indexFilterable": True,
                "indexSearchable": False,
            },
        ],
    },
]


def get_collection_schema(class_name: str) -> Dict[str, Any]:
    """Get schema for a specific collection by name"""
    for schema in WEAVIATE_SCHEMAS:
        if schema["class"] == class_name:
            return schema
    raise ValueError(f"Schema not found for collection: {class_name}")
