"""
Standalone OAuth Test Script

Tests Google Calendar OAuth flow without requiring full backend services.
This verifies your OAuth credentials are configured correctly.
"""

import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

# Load environment variables
load_dotenv()


def test_oauth_config():
    """Test that OAuth credentials are configured"""
    print("\n" + "=" * 60)
    print("GOOGLE OAUTH CONFIGURATION TEST")
    print("=" * 60)

    # Check environment variables
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")

    print("\n1. Checking Environment Variables...")
    print(f"   GOOGLE_OAUTH_CLIENT_ID: {'✅ Set' if client_id else '❌ Missing'}")
    print(
        f"   GOOGLE_OAUTH_CLIENT_SECRET: {'✅ Set' if client_secret else '❌ Missing'}"
    )
    print(f"   GOOGLE_OAUTH_REDIRECT_URI: {redirect_uri or '❌ Missing'}")

    if not all([client_id, client_secret, redirect_uri]):
        print("\n❌ OAuth credentials not configured in .env file")
        print("\nAdd to backend/.env:")
        print("GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com")
        print("GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret")
        print(
            "GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/data-sources/oauth/google-calendar/callback"
        )
        return False

    # Try to create OAuth flow
    print("\n2. Creating OAuth Flow...")
    try:
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            redirect_uri=redirect_uri,
        )

        print("   ✅ OAuth flow created successfully")

        # Generate authorization URL
        print("\n3. Generating Authorization URL...")
        auth_url, state = flow.authorization_url(
            access_type="offline", prompt="consent", state="test-user-123"
        )

        print("   ✅ Authorization URL generated successfully")
        print(f"\n{'=' * 60}")
        print("AUTHORIZATION URL:")
        print(f"{'=' * 60}")
        print(f"\n{auth_url}\n")
        print(f"{'=' * 60}")
        print("\nTO TEST OAUTH FLOW:")
        print("1. Copy the URL above")
        print("2. Paste it into your browser")
        print("3. Sign in with Google")
        print("4. Grant calendar read permission")
        print("5. You'll be redirected to localhost:8000/...")
        print(f"{'=' * 60}")

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = test_oauth_config()
    if success:
        print("\n✅ OAuth configuration is valid!")
        print("   You can now test the full flow once Docker services are stable.\n")
    else:
        print("\n❌ OAuth configuration failed")
        print("   Please check your credentials in .env file\n")
