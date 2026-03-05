#!/bin/bash

# Test Supabase Auth Integration
# This script tests signup, login, and protected routes

API_URL="http://localhost:8000"
TEST_EMAIL="test_$(date +%s)@example.com"
TEST_PASSWORD="SecurePassword123!"

echo "🧪 Testing Ethic Companion Auth Flow"
echo "===================================="
echo ""

# Test 1: Signup
echo "1️⃣ Testing Signup..."
SIGNUP_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

echo "Response: $SIGNUP_RESPONSE"
echo ""

# Extract access token (using grep/sed for simplicity)
ACCESS_TOKEN=$(echo $SIGNUP_RESPONSE | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Signup failed - no access token received"
  exit 1
fi

echo "✅ Signup successful! Access token received."
echo "Access token (first 50 chars): ${ACCESS_TOKEN:0:50}..."
echo ""

# Test 2: Get Profile (Protected Route)
echo "2️⃣ Testing Protected Route (GET /api/auth/me)..."
PROFILE_RESPONSE=$(curl -s -X GET "$API_URL/api/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

echo "Response: $PROFILE_RESPONSE"
echo ""

if echo "$PROFILE_RESPONSE" | grep -q "$TEST_EMAIL"; then
  echo "✅ Protected route works! User profile retrieved."
else
  echo "❌ Protected route failed - user not found"
  exit 1
fi

# Test 3: Login with Same Credentials
echo "3️⃣ Testing Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

echo "Response: $LOGIN_RESPONSE"
echo ""

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
  echo "✅ Login successful!"
else
  echo "❌ Login failed"
  exit 1
fi

# Test 4: Check if user exists in public.users (requires Supabase access)
echo "4️⃣ User created in public.users table"
echo "   To verify: Run this query in Supabase SQL Editor:"
echo "   SELECT * FROM public.users WHERE email = '$TEST_EMAIL';"
echo ""

echo "===================================="
echo "✅ All tests passed!"
echo "Test email: $TEST_EMAIL"
echo "Test password: $TEST_PASSWORD"
echo ""
echo "Next steps:"
echo "1. Verify user exists in Supabase Dashboard (Table Editor -> users)"
echo "2. Check that user also exists in auth.users (Authentication -> Users)"
echo "3. Test frontend: http://localhost:3000"
