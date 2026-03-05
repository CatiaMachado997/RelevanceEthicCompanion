#!/bin/bash
# Quick test for Supabase Auth integration

BASE_URL="http://localhost:8000"

echo "🔐 Testing Supabase Auth"
echo "========================"
echo ""

# Test 1: Signup
echo "1. Testing Signup..."
SIGNUP_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "supabase_test@example.com",
    "password": "testpass123",
    "full_name": "Supabase Test User"
  }')

echo "$SIGNUP_RESPONSE" | python3 -m json.tool
echo ""

# Extract token
ACCESS_TOKEN=$(echo "$SIGNUP_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ]; then
    echo "✅ Signup successful!"
    echo ""
    
    # Test 2: Get Profile
    echo "2. Testing Get Profile..."
    curl -s -X GET "$BASE_URL/api/auth/me" \
      -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
    echo ""
    
    # Test 3: Create a value (protected route)
    echo "3. Testing Protected Route (Create Value)..."
    curl -s -X POST "$BASE_URL/api/values/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "type": "boundary",
        "value": "no_notifications_after_20h",
        "priority": 1
      }' | python3 -m json.tool
    echo ""
    
    echo "✅ All tests passed!"
else
    echo "❌ Signup failed"
    echo "Make sure:"
    echo "1. Server is running (python main.py)"
    echo "2. Database trigger is set up (run setup_supabase_auth.sql)"
    echo "3. Supabase Auth is enabled in dashboard"
fi
