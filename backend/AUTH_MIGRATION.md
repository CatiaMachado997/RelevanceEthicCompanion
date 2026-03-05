# Supabase Auth Migration Guide

## 🎯 Overview

We've added JWT-based authentication to secure the Ethic Companion API. All routes now require authentication via Bearer tokens.

## 🔑 What Changed

### 1. New Authentication Routes (`/api/auth`)

- `POST /api/auth/signup` - Register new user
- `POST /api/auth/login` - Login and get access token
- `GET /api/auth/me` - Get current user profile
- `PUT /api/auth/me` - Update user profile
- `POST /api/auth/change-password` - Change password
- `POST /api/auth/logout` - Logout (client-side token deletion)
- `DELETE /api/auth/account` - Delete account (soft delete)

### 2. Protected Routes

All existing routes now require authentication:
- `/api/values/*` - User values/boundaries
- `/api/chat/*` - Chat with AI
- `/api/goals/*` - User goals
- `/api/transparency/*` - ESL audit logs

### 3. Database Changes

Run this SQL migration to add authentication fields:

```sql
-- Add authentication fields
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS password_hash TEXT,
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC',
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON public.users(deleted_at);

-- Update RLS policies to exclude deleted users
DROP POLICY IF EXISTS "Users can view own data" ON public.users;
CREATE POLICY "Users can view own data"
    ON public.users FOR SELECT
    USING (auth.uid() = id AND deleted_at IS NULL);

DROP POLICY IF EXISTS "Users can update own data" ON public.users;
CREATE POLICY "Users can update own data"
    ON public.users FOR UPDATE
    USING (auth.uid() = id AND deleted_at IS NULL);

DROP POLICY IF EXISTS "Users can insert own data" ON public.users;
CREATE POLICY "Users can insert own data"
    ON public.users FOR INSERT
    WITH CHECK (true);
```

## 📝 Migration Steps

### Step 1: Run Database Migration

```bash
# In Supabase SQL Editor or psql
psql -h <your-supabase-host> -U postgres -d postgres -f database/add_auth_fields.sql
```

Or copy/paste the SQL from `backend/database/add_auth_fields.sql` into Supabase SQL Editor.

### Step 2: Update Environment Variables

Ensure your `.env` file has all required settings:

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key

# Security (generate a secure random string)
SECRET_KEY=your_jwt_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Generate a secure SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 3: Test Authentication

```bash
# Start the server
python main.py

# In another terminal, run tests
bash scripts/test_auth.sh
```

## 🔄 API Usage Changes

### Before (Header-based, insecure):
```bash
curl -X GET http://localhost:8000/api/values/ \
  -H "X-User-ID: 00000000-0000-0000-0000-000000000001"
```

### After (JWT-based, secure):

**1. Sign up:**
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "full_name": "Jane Doe",
    "timezone": "America/New_York"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "full_name": "Jane Doe"
}
```

**2. Use the token for protected routes:**
```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X GET http://localhost:8000/api/values/ \
  -H "Authorization: Bearer $TOKEN"
```

## 🔐 Security Improvements

### ✅ What We Now Have

1. **Password Hashing**: Bcrypt-based password storage
2. **JWT Tokens**: Stateless authentication with expiration
3. **Token Validation**: All protected routes verify JWT signatures
4. **User Isolation**: RLS policies ensure users only access their data
5. **Soft Deletes**: Account deletion preserves data for recovery
6. **Failed Login Protection**: Returns generic error messages

### 🛡️ Best Practices

- **Never commit `.env`**: Contains SECRET_KEY
- **Use HTTPS in production**: Prevents token interception
- **Token expiration**: Tokens expire after 30 minutes (configurable)
- **Client-side storage**: Store tokens in httpOnly cookies or secure storage
- **Logout**: Delete token from client storage

## 🧪 Testing

### Run All Auth Tests
```bash
bash scripts/test_auth.sh
```

### Manual Testing

**1. Create account:**
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456", "full_name": "Test User"}'
```

**2. Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

**3. Get profile:**
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 🚀 Next Steps

1. **Frontend Integration**:
   - Add signup/login forms
   - Store JWT token in localStorage/cookies
   - Add Authorization header to all API calls
   - Handle token expiration (refresh or re-login)

2. **Enhanced Security** (Future):
   - Refresh tokens for longer sessions
   - Token blacklisting on logout
   - Rate limiting on auth endpoints
   - Email verification
   - Password reset flow
   - 2FA support

3. **Supabase Auth Integration** (Optional):
   - Replace custom JWT with Supabase Auth
   - Use `supabase.auth.signUp()` and `supabase.auth.signIn()`
   - Benefit from built-in email verification, OAuth, etc.

## ❓ Troubleshooting

### "Could not validate credentials"
- Token expired (30 min default)
- Invalid token format
- Wrong SECRET_KEY in .env

### "Email already registered"
- User exists, use login instead
- Check Supabase dashboard

### "Users can insert own data" policy error
- Run the migration SQL
- Verify RLS policies in Supabase dashboard

### Import errors
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

## 📚 Files Changed

### New Files:
- `backend/utils/auth.py` - JWT utilities and auth dependency
- `backend/models/auth.py` - Auth request/response models
- `backend/routes/auth.py` - Authentication endpoints
- `backend/database/add_auth_fields.sql` - Database migration
- `backend/scripts/test_auth.sh` - Auth testing script
- `AUTH_MIGRATION.md` - This guide

### Modified Files:
- `backend/main.py` - Added auth router
- `backend/routes/values.py` - Uses JWT auth
- `backend/routes/chat.py` - Uses JWT auth
- `backend/routes/goals.py` - Uses JWT auth
- `backend/routes/transparency.py` - Uses JWT auth

## ✨ Benefits

1. **Security**: Industry-standard JWT authentication
2. **Scalability**: Stateless tokens work across multiple servers
3. **User Control**: Users manage their own accounts
4. **Compliance**: Proper authentication for data privacy
5. **Integration Ready**: Easy to integrate with frontend frameworks
6. **ESL Alignment**: User authentication aligns with "Trust over Engagement" - users control access to their data

---

**Questions?** Check the code comments in `backend/utils/auth.py` and `backend/routes/auth.py` for implementation details.
