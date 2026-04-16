"""
Google Calendar Sync Service

Handles OAuth2 authentication and periodic event synchronization.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models.context import Event
from config import settings

logger = logging.getLogger(__name__)


class GoogleCalendarSync:
    """
    Google Calendar integration with OAuth2

    Responsibilities:
    - OAuth2 authorization flow
    - Fetch events from Google Calendar
    - Normalize Google event data to Event model
    - Handle token refresh
    """

    # OAuth scopes - read-only calendar access
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, redirect_uri: str = None):
        """
        Initialize Google Calendar sync

        Args:
            redirect_uri: OAuth redirect URI (must match Google Console config).
                          Defaults to settings.GOOGLE_OAUTH_REDIRECT_URI.
        """
        self.redirect_uri = redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URI
        self.client_config = self._load_client_config()

    def _load_client_config(self) -> Dict[str, Any]:
        """Load OAuth client configuration from environment or file"""

        # Option 1: From environment variables (recommended for production)
        if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
            return {
                "web": {
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            }

        # Option 2: From credentials file (for local development)
        creds_path = os.path.join(
            os.path.dirname(__file__), "..", "credentials", "google_oauth.json"
        )
        if os.path.exists(creds_path):
            import json

            with open(creds_path, "r") as f:
                return json.load(f)

        raise ValueError(
            "Google OAuth credentials not found. "
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET environment variables, "
            "or create credentials/google_oauth.json file."
        )

    def get_authorization_url(
        self, user_id: str, oauth_state: Optional[str] = None
    ) -> str:
        """
        Generate OAuth authorization URL for user

        Args:
            user_id: User ID to associate with this authorization

        Returns:
            Authorization URL to redirect user to
        """
        try:
            flow = Flow.from_client_config(
                self.client_config, scopes=self.SCOPES, redirect_uri=self.redirect_uri
            )

            state_value = oauth_state or user_id

            # Generate authorization URL with signed state parameter
            auth_url, state = flow.authorization_url(
                access_type="offline",  # Get refresh token
                include_granted_scopes="true",
                state=state_value,
                prompt="consent",  # Force consent to get refresh token
            )

            logger.info(f"Generated OAuth URL for user {user_id}")
            return auth_url

        except Exception as e:
            logger.error(f"Failed to generate OAuth URL: {e}")
            raise

    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, str]:
        """
        Exchange authorization code for access and refresh tokens

        Args:
            authorization_code: Code from OAuth callback

        Returns:
            Dict with access_token, refresh_token, expires_at
        """
        try:
            flow = Flow.from_client_config(
                self.client_config, scopes=self.SCOPES, redirect_uri=self.redirect_uri
            )

            # Exchange code for tokens
            flow.fetch_token(code=authorization_code)

            creds = flow.credentials

            # Calculate token expiration
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=creds.expiry.timestamp() - datetime.now().timestamp()
            )

            return {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_at": expires_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to exchange OAuth code: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token using refresh token

        Args:
            refresh_token: Stored refresh token

        Returns:
            Dict with new access_token and expires_at
        """
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=self.client_config["web"]["token_uri"],
                client_id=self.client_config["web"]["client_id"],
                client_secret=self.client_config["web"]["client_secret"],
            )

            # Refresh the token
            creds.refresh(Request())

            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=creds.expiry.timestamp() - datetime.now().timestamp()
            )

            return {"access_token": creds.token, "expires_at": expires_at.isoformat()}

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    async def fetch_events(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events from Google Calendar

        Args:
            access_token: OAuth access token
            refresh_token: Optional refresh token if access token expired
            time_min: Start of time range (default: now)
            time_max: End of time range (default: 30 days from now)
            max_results: Maximum events to fetch

        Returns:
            List of Google Calendar event dictionaries
        """
        try:
            # Create credentials
            creds = Credentials(token=access_token)

            # Build Calendar API service
            service = build("calendar", "v3", credentials=creds)

            # Default time range: next 30 days
            if not time_min:
                time_min = datetime.now(timezone.utc)
            if not time_max:
                time_max = time_min + timedelta(days=30)

            # Format times for API (RFC3339)
            time_min_str = time_min.isoformat()
            time_max_str = time_max.isoformat()

            # Fetch events from primary calendar
            logger.info(f"Fetching events from {time_min_str} to {time_max_str}")

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min_str,
                    timeMax=time_max_str,
                    maxResults=max_results,
                    singleEvents=True,  # Expand recurring events
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            logger.info(f"✅ Fetched {len(events)} events from Google Calendar")

            return events

        except HttpError as e:
            if e.resp.status == 401:
                # Token expired - try to refresh if we have refresh token
                if refresh_token:
                    logger.info("Access token expired, refreshing...")
                    new_tokens = self.refresh_access_token(refresh_token)
                    # Retry with new token
                    return await self.fetch_events(
                        access_token=new_tokens["access_token"],
                        time_min=time_min,
                        time_max=time_max,
                        max_results=max_results,
                    )
                else:
                    logger.error("Access token expired and no refresh token available")
                    raise
            else:
                logger.error(f"Google Calendar API error: {e}")
                raise

        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            raise

    def normalize_event(self, google_event: Dict[str, Any], user_id: str) -> Event:
        """
        Convert Google Calendar event to internal Event model

        Args:
            google_event: Raw Google Calendar event
            user_id: User ID to associate event with

        Returns:
            Event model instance
        """
        # Extract event ID
        event_id = google_event.get("id")

        # Extract title
        title = google_event.get("summary", "Untitled Event")

        # Extract description
        description = google_event.get("description", "")

        # Extract start/end times
        start = google_event.get("start", {})
        end = google_event.get("end", {})

        # Handle all-day events vs timed events
        if "dateTime" in start:
            start_time = datetime.fromisoformat(
                start["dateTime"].replace("Z", "+00:00")
            )
        else:
            # All-day event
            start_time = datetime.fromisoformat(start["date"]).replace(
                tzinfo=timezone.utc
            )

        if "dateTime" in end:
            end_time = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
        else:
            # All-day event
            end_time = datetime.fromisoformat(end["date"]).replace(tzinfo=timezone.utc)

        # Extract location
        location = google_event.get("location", "")

        # Build metadata
        metadata = {
            "google_event_id": event_id,
            "google_calendar_id": google_event.get("organizer", {}).get("email", ""),
            "status": google_event.get("status", "confirmed"),
            "html_link": google_event.get("htmlLink", ""),
            "attendees": [
                {"email": att.get("email"), "responseStatus": att.get("responseStatus")}
                for att in google_event.get("attendees", [])
            ],
            "creator": google_event.get("creator", {}).get("email", ""),
            "all_day": "date" in start,  # True if all-day event
        }

        # Create Event model
        return Event(
            id=event_id,  # Use Google event ID
            user_id=user_id,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            location=location,
            source="google_calendar",
            source_id=event_id,
            metadata=metadata,
        )


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_google_calendar():
        """Test Google Calendar integration"""

        sync = GoogleCalendarSync()

        # Step 1: Get authorization URL
        print("\n" + "=" * 60)
        print("GOOGLE CALENDAR OAUTH TEST")
        print("=" * 60)

        test_user_id = "test-user-123"
        auth_url = sync.get_authorization_url(test_user_id)

        print(f"\n1. Authorization URL:")
        print(f"   {auth_url}")
        print(f"\n2. Open this URL in browser and authorize")
        print(f"3. Copy the 'code' parameter from redirect URL")

        # In real flow, user would be redirected and you'd get the code from callback
        # For testing, you'd need to manually paste the code here

    asyncio.run(test_google_calendar())
