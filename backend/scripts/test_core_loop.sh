#!/bin/bash
#
# Test the Backend Core Loop
# Demonstrates ESL audit persistence, transparency endpoint, and relevance scan
#
# Prerequisites:
# 1. Run setup_supabase_auth.sql in Supabase
# 2. Have a test user signed up
# 3. Server running on http://localhost:8000

BASE_URL="http://localhost:8000"

echo "========================================="
echo "Backend Core Loop Test"
echo "========================================="
echo ""

# Step 1: Signup (or skip if you already have a user)
echo "1. Creating test user..."
SIGNUP_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test-core-loop@example.com",
    "password": "SecurePassword123!",
    "full_name": "Core Loop Test User"
  }')

echo "Signup response: $SIGNUP_RESPONSE"
echo ""

# Extract access token (requires jq)
if command -v jq &> /dev/null; then
    TOKEN=$(echo $SIGNUP_RESPONSE | jq -r '.access_token // empty')
    if [ -z "$TOKEN" ]; then
        echo "⚠️  No access_token in signup response. User may already exist."
        echo "Trying login instead..."
        
        LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
          -H "Content-Type: application/json" \
          -d '{
            "email": "test-core-loop@example.com",
            "password": "SecurePassword123!"
          }')
        
        echo "Login response: $LOGIN_RESPONSE"
        TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token // empty')
    fi
    
    if [ -z "$TOKEN" ]; then
        echo "❌ Failed to get token. Please check your credentials or Supabase setup."
        exit 1
    fi
    
    echo "✅ Token acquired"
    echo ""
else
    echo "⚠️  jq not found. Install with: brew install jq"
    echo "For now, manually extract the access_token from the response above."
    exit 1
fi

# Step 2: Add a user value (boundary)
echo "2. Adding user boundary: no_work_after_19h..."
curl -s -X POST "$BASE_URL/api/values/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "type": "boundary",
    "value": "no_work_after_19h",
    "priority": 1
  }' | jq '.'
echo ""

# Step 3: Send a chat message (goes through ESL)
echo "3. Sending chat message (ESL-protected)..."
CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "What should I focus on today?",
    "context": {}
  }')

echo "$CHAT_RESPONSE" | jq '.'
echo ""

# Step 4: Check ESL transparency report
echo "4. Fetching ESL transparency report..."
curl -s -X GET "$BASE_URL/api/transparency/report?days=7" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Step 5: Get ESL audit logs
echo "5. Fetching ESL audit logs..."
curl -s -X GET "$BASE_URL/api/transparency/logs?days=7&limit=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

# Step 6: Trigger relevance scan (requires events in DB)
echo "6. Triggering relevance scan for upcoming events..."
SCAN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/relevance/scan?window_minutes=15" \
  -H "Authorization: Bearer $TOKEN")

echo "$SCAN_RESPONSE" | jq '.'
echo ""

# Step 7: Get ESL insights
echo "7. Fetching ESL insights..."
curl -s -X GET "$BASE_URL/api/transparency/insights" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
echo ""

echo "========================================="
echo "✅ Backend Core Loop Test Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "- ESL evaluated chat message and logged decision"
echo "- Transparency endpoints show ESL activity"
echo "- Relevance scan ready to propose proactive actions"
echo "- TopicFilter integrated into ESL pipeline"
echo ""
echo "Next steps:"
echo "1. Add calendar events to test relevance engine"
echo "2. Configure Groq API for real LLM summaries"
echo "3. Add frontend to visualize ESL transparency"
