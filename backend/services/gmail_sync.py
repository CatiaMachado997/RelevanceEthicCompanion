"""
Gmail Sync Service — read-only integration using Google OAuth2.
Uses the same Google OAuth client credentials as Google Calendar.
"""

from typing import List, Dict, Any, Optional
import logging

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import settings

logger = logging.getLogger(__name__)


class GmailSync:
    """Gmail integration with OAuth2 (read-only)"""

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, redirect_uri: str = None):
        self.redirect_uri = redirect_uri or settings.GMAIL_OAUTH_REDIRECT_URI
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def get_authorization_url(self, user_id: str, oauth_state: Optional[str] = None) -> str:
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=oauth_state or user_id,
            prompt='consent'
        )
        return auth_url

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        flow = Flow.from_client_config(
            self.client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expires_at": creds.expiry.isoformat() if creds.expiry else None
        }

    def fetch_messages(
        self,
        access_token: str,
        refresh_token: str,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch recent emails (subject + snippet only, no body)"""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=self.SCOPES
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build('gmail', 'v1', credentials=creds)
        result = service.users().messages().list(
            userId='me',
            maxResults=max_results,
            labelIds=['INBOX']
        ).execute()

        messages = []
        for msg in result.get('messages', []):
            detail = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in detail.get('payload', {}).get('headers', [])}
            messages.append({
                'id': msg['id'],
                'subject': headers.get('Subject', '(no subject)'),
                'from': headers.get('From', ''),
                'date': headers.get('Date', ''),
                'snippet': detail.get('snippet', ''),
            })

        return messages
