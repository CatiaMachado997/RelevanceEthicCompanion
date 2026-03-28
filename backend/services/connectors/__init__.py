# backend/services/connectors/__init__.py
"""Connector factory — returns the right BaseConnector for a source_type."""
from services.connectors.base import BaseConnector
from config import settings


def get_connector(source_type: str) -> BaseConnector:
    """
    Return the connector instance for the given source_type.
    Raises ValueError for unsupported source types.
    """
    if source_type == "google_calendar":
        from services.connectors.google_calendar import GoogleCalendarConnector
        return GoogleCalendarConnector(redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI)
    elif source_type == "gmail":
        from services.connectors.gmail import GmailConnector
        return GmailConnector(redirect_uri=settings.GMAIL_OAUTH_REDIRECT_URI)
    elif source_type == "slack":
        from services.connectors.slack import SlackConnector
        return SlackConnector()
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
