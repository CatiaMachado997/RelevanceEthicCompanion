"""
Create a test user in the database for API testing.
"""
import asyncio
import uuid
from supabase import create_client
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

async def create_test_user():
    """Create a test user with a known user_id."""
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    
    # Use a fixed test user ID for consistency
    test_user_id = "00000000-0000-0000-0000-000000000001"
    test_email = "test@ethiccompanion.com"
    
    try:
        # Check if user already exists
        result = supabase.table("users").select("*").eq("id", test_user_id).execute()
        
        if result.data:
            print(f"✅ Test user already exists: {test_user_id}")
            print(f"   Email: {test_email}")
            return test_user_id
        
        # Create test user
        user_data = {
            "id": test_user_id,
            "email": test_email,
            "full_name": "Test User",
            "avatar_url": None
        }
        
        result = supabase.table("users").insert(user_data).execute()
        
        print(f"✅ Test user created successfully!")
        print(f"   User ID: {test_user_id}")
        print(f"   Email: {test_email}")
        print(f"\n💡 Use this user_id in your API tests:")
        print(f'   curl -H "X-User-ID: {test_user_id}" ...')
        
        return test_user_id
        
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(create_test_user())
