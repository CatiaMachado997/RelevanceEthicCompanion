#!/bin/bash

echo "🧪 Testing Ethic Companion API"
echo "=============================="

# Fixed test user ID (create with: python scripts/create_test_user.py)
TEST_USER_ID="00000000-0000-0000-0000-000000000001"

# Test health
echo -e "\n1️⃣ Testing Health Endpoint..."
curl -s http://localhost:8000/health | python -m json.tool

# Test chat with test user
echo -e "\n2️⃣ Testing Chat Endpoint..."
curl -s -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $TEST_USER_ID" \
  -d '{"message": "Hello, what can you help me with?"}' | python -m json.tool

# Test values with test user
echo -e "\n3️⃣ Testing Values Endpoint (Create Boundary)..."
curl -s -X POST http://localhost:8000/api/values/ \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $TEST_USER_ID" \
  -d '{"type": "boundary", "value": "no_work_after_19h", "priority": 1}' | python -m json.tool

# List values
echo -e "\n4️⃣ Listing Values..."
curl -s http://localhost:8000/api/values/ \
  -H "X-User-ID: $TEST_USER_ID" | python -m json.tool

# Test goals with test user
echo -e "\n5️⃣ Testing Goals Endpoint (Create Goal)..."
curl -s -X POST http://localhost:8000/api/goals/ \
  -H "Content-Type: application/json" \
  -H "X-User-ID: $TEST_USER_ID" \
  -d '{"title": "Learn Python", "description": "Master backend development", "priority": 1}' | python -m json.tool

# List goals
echo -e "\n6️⃣ Listing Goals..."
curl -s http://localhost:8000/api/goals/ \
  -H "X-User-ID: $TEST_USER_ID" | python -m json.tool

# Test transparency with test user
echo -e "\n7️⃣ Testing Transparency Report..."
curl -s http://localhost:8000/api/transparency/report?days=7 \
  -H "X-User-ID: $TEST_USER_ID" | python -m json.tool

# Test ESL audit logs
echo -e "\n8️⃣ Testing ESL Audit Logs..."
curl -s http://localhost:8000/api/transparency/logs?limit=5 \
  -H "X-User-ID: $TEST_USER_ID" | python -m json.tool

echo -e "\n✅ API Tests Complete!"
echo -e "\n💡 Test User ID: $TEST_USER_ID"
