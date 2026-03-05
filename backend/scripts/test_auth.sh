#!/bin/bash
# Test Supabase Auth Integration
# Tests signup, login, profile management, and protected routes

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "🔐 Testing Supabase Auth Integration"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: Health Check
echo "${BLUE}Test 1: Health Check${NC}"
RESPONSE=$(curl -s -X GET "$BASE_URL/health")
echo "Response: $RESPONSE"
if echo "$RESPONSE" | grep -q "healthy"; then
    echo "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
else
    echo "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 2: Signup New User
echo "${BLUE}Test 2: Signup New User${NC}"
SIGNUP_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepass123",
    "full_name": "Test User",
    "timezone": "America/New_York"
  }')
echo "Response: $SIGNUP_RESPONSE"

# Extract access token from signup response
ACCESS_TOKEN=$(echo "$SIGNUP_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ]; then
    echo "${GREEN}✓ PASS - Got access token${NC}"
    ((TESTS_PASSED++))
    echo "Access Token: ${ACCESS_TOKEN:0:50}..."
else
    echo "${RED}✗ FAIL - No access token${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 3: Get Profile (Protected Route)
echo "${BLUE}Test 3: Get Profile (Protected)${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    PROFILE_RESPONSE=$(curl -s -X GET "$BASE_URL/api/auth/me" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    echo "Response: $PROFILE_RESPONSE"
    
    if echo "$PROFILE_RESPONSE" | grep -q "test@example.com"; then
        echo "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo "${RED}✗ SKIP - No token available${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 4: Create User Value (Protected)
echo "${BLUE}Test 4: Create User Value (Protected)${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    VALUE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/values/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "type": "boundary",
        "value": "no_work_after_19h",
        "priority": 1
      }')
    echo "Response: $VALUE_RESPONSE"
    
    if echo "$VALUE_RESPONSE" | grep -q "no_work_after_19h"; then
        echo "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo "${RED}✗ SKIP - No token available${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 5: Login Existing User
echo "${BLUE}Test 5: Login Existing User${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepass123"
  }')
echo "Response: $LOGIN_RESPONSE"

LOGIN_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$LOGIN_TOKEN" ]; then
    echo "${GREEN}✓ PASS - Logged in successfully${NC}"
    ((TESTS_PASSED++))
else
    echo "${RED}✗ FAIL - Login failed${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 6: Wrong Password (Should Fail)
echo "${BLUE}Test 6: Wrong Password (Should Fail)${NC}"
WRONG_PASSWORD=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "wrongpassword"
  }')
echo "Response: $WRONG_PASSWORD"

if echo "$WRONG_PASSWORD" | grep -q "Incorrect email or password"; then
    echo "${GREEN}✓ PASS - Correctly rejected wrong password${NC}"
    ((TESTS_PASSED++))
else
    echo "${RED}✗ FAIL - Should have rejected wrong password${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 7: Update Profile
echo "${BLUE}Test 7: Update Profile${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    UPDATE_RESPONSE=$(curl -s -X PUT "$BASE_URL/api/auth/me?full_name=Updated%20Name&timezone=Europe/London" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    echo "Response: $UPDATE_RESPONSE"
    
    if echo "$UPDATE_RESPONSE" | grep -q "Updated Name"; then
        echo "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo "${RED}✗ SKIP - No token available${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 8: Access Protected Chat Endpoint
echo "${BLUE}Test 8: Access Protected Chat Endpoint${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat/" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "message": "Hello, AI!"
      }')
    echo "Response: $CHAT_RESPONSE"
    
    if echo "$CHAT_RESPONSE" | grep -q "executed"; then
        echo "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo "${RED}✗ SKIP - No token available${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 9: Logout
echo "${BLUE}Test 9: Logout${NC}"
if [ -n "$ACCESS_TOKEN" ]; then
    LOGOUT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/logout" \
      -H "Authorization: Bearer $ACCESS_TOKEN")
    echo "Response: $LOGOUT_RESPONSE"
    
    if echo "$LOGOUT_RESPONSE" | grep -q "success"; then
        echo "${GREEN}✓ PASS${NC}"
        ((TESTS_PASSED++))
    else
        echo "${RED}✗ FAIL${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo "${RED}✗ SKIP - No token available${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Test 10: Access Without Token (Should Fail)
echo "${BLUE}Test 10: Access Without Token (Should Fail)${NC}"
NO_AUTH_RESPONSE=$(curl -s -X GET "$BASE_URL/api/auth/me")
echo "Response: $NO_AUTH_RESPONSE"

if echo "$NO_AUTH_RESPONSE" | grep -q "Not authenticated"; then
    echo "${GREEN}✓ PASS - Correctly rejected unauthorized access${NC}"
    ((TESTS_PASSED++))
else
    echo "${RED}✗ FAIL - Should have rejected unauthorized access${NC}"
    ((TESTS_FAILED++))
fi
echo ""

# Summary
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo "${GREEN}Passed: $TESTS_PASSED${NC}"
echo "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo "${RED}❌ Some tests failed${NC}"
    exit 1
fi
