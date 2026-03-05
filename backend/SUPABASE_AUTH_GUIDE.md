# Supabase Auth vs Custom Auth - Implementation Guide

## 🎯 TL;DR - Should You Switch?

**YES!** Use Supabase Auth. Here's why:

| Feature | Custom JWT (What We Built) | Supabase Auth (Recommended) |
|---------|---------------------------|----------------------------|
| **Code to maintain** | ~300 lines | ~100 lines |
| **Email verification** | ❌ Need to build | ✅ Built-in |
| **Password reset** | ❌ Need to build | ✅ Built-in |
| **OAuth (Google, GitHub)** | ❌ Need to build | ✅ One click enable |
| **Magic links** | ❌ Need to build | ✅ Built-in |
| **Security updates** | ❌ Your responsibility | ✅ Supabase handles it |
| **Session management** | ❌ Manual | ✅ Automatic |
| **Token refresh** | ❌ Need to build | ✅ Built-in |
| **Rate limiting** | ❌ Need to build | ✅ Built-in |
| **MFA/2FA** | ❌ Complex to build | ✅ Available |

---

## 📊 Code Comparison

### Custom Auth (Current)

**Files needed:**
- `utils/auth.py` (140 lines) - JWT logic, password hashing
- `models/auth.py` (80 lines) - Request/response models  
- `routes/auth.py` (350 lines) - Signup, login, password change, etc.
- **Total: ~570 lines**

**Features we DON'T have:**
- Email verification
- Password reset via email
- OAuth providers
- Magic links
- Proper session management

---

### Supabase Auth (Recommended)

**Files needed:**
- `utils/supabase_auth.py` (90 lines) - Token validation only
- `routes/supabase_auth.py` (250 lines) - Thin wrappers around Supabase
- **Total: ~340 lines** (40% less code!)

**Features we GET for free:**
- ✅ Email verification
- ✅ Password reset via email
- ✅ OAuth (Google, GitHub, etc.)
- ✅ Magic links (passwordless)
- ✅ Session management
- ✅ Token refresh
- ✅ Rate limiting
- ✅ Security best practices

---

## 🚀 How to Migrate to Supabase Auth

### Step 1: Enable Supabase Auth (Dashboard)

1. Go to Supabase Dashboard → Authentication
2. Configure email settings:
   - **Email provider**: Choose Supabase SMTP or your own
   - **Email templates**: Customize confirmation/reset emails
3. Enable providers you want:
   - Email/Password ✅ (already enabled)
   - Google OAuth (optional)
   - GitHub OAuth (optional)
   - Magic Links (optional)

### Step 2: Update Database Schema

Supabase Auth uses `auth.users` table automatically. You just need to sync to `public.users`:

```sql
-- Create trigger to auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email, full_name, created_at)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data->>'full_name',
    NEW.created_at
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger on auth.users insert
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();
```

**What this does:**
- When Supabase creates user in `auth.users` → Automatically creates profile in `public.users`
- No manual sync needed!

### Step 3: Replace Files

**Delete old files:**
```bash
rm backend/utils/auth.py
rm backend/routes/auth.py
```

**Use new files:**
- `backend/utils/supabase_auth.py` (already created above)
- `backend/routes/supabase_auth.py` (already created above)

### Step 4: Update main.py

```python
# Change this import:
from routes import auth, values, chat, goals, transparency

# To this:
from routes import supabase_auth as auth, values, chat, goals, transparency

# Router registration stays the same
app.include_router(auth.router)
```

### Step 5: Update Route Files

**No changes needed!** The routes already use `get_current_user_id()` dependency.

Just update the import:

```python
# In values.py, chat.py, goals.py, transparency.py
# Change:
from utils.auth import get_current_user_id

# To:
from utils.supabase_auth import get_current_user_id
```

### Step 6: Update .env

Remove custom JWT settings:
```bash
# DELETE these (not needed with Supabase Auth):
# SECRET_KEY=...
# ALGORITHM=HS256
# ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Keep Supabase settings:
```bash
SUPABASE_URL=your_project_url
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
```

### Step 7: Test

```bash
# Start server
python main.py

# Test signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'

# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

---

## 🎁 Bonus Features You Get

### 1. Email Verification

**Automatic!** Just enable in Supabase Dashboard:
- Authentication → Email Auth → Confirm Email = ON
- Users must click link in email before login works

### 2. Password Reset

**Already implemented!** See `POST /api/auth/reset-password` endpoint:
```bash
curl -X POST http://localhost:8000/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

Supabase sends email with reset link automatically!

### 3. OAuth (Social Login)

Enable in Dashboard → Authentication → Providers:

**Google:**
1. Create OAuth app in Google Cloud Console
2. Add Client ID and Secret to Supabase
3. Done! Users can login with Google

**Frontend code:**
```javascript
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google'
})
```

**Backend:** No changes needed! Tokens work the same way.

### 4. Magic Links (Passwordless)

```javascript
// Frontend
const { data, error } = await supabase.auth.signInWithOtp({
  email: 'user@example.com'
})
// User clicks link in email → Automatically logged in!
```

### 5. Session Refresh

**Automatic!** Supabase JS client handles it:
```javascript
// Frontend - client auto-refreshes tokens
const supabase = createClient(url, key, {
  auth: {
    autoRefreshToken: true,  // Default: true
    persistSession: true      // Save to localStorage
  }
})
```

**Backend endpoint** (if you need manual refresh):
```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token"}'
```

---

## 🔐 Security Comparison

| Security Feature | Custom Auth | Supabase Auth |
|-----------------|-------------|---------------|
| Password hashing | Bcrypt (good) | Bcrypt (same) |
| Token signing | HS256 (symmetric) | RS256 (asymmetric, better) |
| Token validation | Manual | Automated |
| Session revocation | ❌ No | ✅ Yes |
| Rate limiting | ❌ No | ✅ Yes |
| Brute force protection | ❌ No | ✅ Yes |
| Email verification | ❌ No | ✅ Yes |
| Password strength | Basic check | Configurable rules |
| Audit logs | Manual | ✅ Built-in |
| Security updates | ❌ Your job | ✅ Automatic |

**Winner:** Supabase Auth (by far!)

---

## 💰 Cost Considerations

**Free tier** (both approaches):
- Up to 50,000 monthly active users
- Email/password auth
- OAuth providers
- Unlimited logins

**Paid tier** ($25/month):
- More active users
- Advanced security features
- Custom SMTP
- SLA guarantees

**Cost of maintaining custom auth:**
- Developer time for features
- Security audits
- Bug fixes
- Updates
- **Estimated:** 10-20 hours/month

**Verdict:** Supabase Auth is cheaper overall!

---

## 📝 Migration Checklist

- [ ] Enable Email Auth in Supabase Dashboard
- [ ] Configure email templates
- [ ] Create database trigger for user sync
- [ ] Replace `utils/auth.py` with `utils/supabase_auth.py`
- [ ] Replace `routes/auth.py` with `routes/supabase_auth.py`
- [ ] Update imports in route files
- [ ] Update `main.py` import
- [ ] Remove custom JWT env vars from `.env`
- [ ] Test signup flow
- [ ] Test login flow
- [ ] Test protected routes
- [ ] Test password reset
- [ ] (Optional) Enable OAuth providers
- [ ] (Optional) Enable magic links
- [ ] Update frontend auth code
- [ ] Update documentation

---

## 🤔 When to Use Custom Auth?

Use custom JWT auth only if:
- You need very specific auth logic
- You're building a specialized system
- You can't use third-party auth services
- You have dedicated security team

**For Ethic Companion:** Use Supabase Auth! ✅

---

## 🎯 Recommended Approach

1. **MVP (Now):** Supabase Auth with email/password
2. **v1.0:** Add Google OAuth
3. **v1.5:** Add magic links (passwordless)
4. **v2.0:** Add MFA/2FA for extra security

---

## ❓ FAQ

**Q: Can I switch from custom to Supabase auth later?**
A: Yes, but you'll need to migrate users. Better to start with Supabase!

**Q: What about existing users in my custom auth?**
A: You can migrate them using Supabase Admin API (requires password rehashing)

**Q: Does Supabase lock me in?**
A: No! It's open source (GoTrue). You can self-host if needed.

**Q: What if Supabase goes down?**
A: They have 99.9% uptime SLA. Your custom auth has... no SLA 😅

**Q: Is it really that much easier?**
A: **YES!** Compare the code files. 40% less code, 10x more features.

---

## 🚀 Next Steps

**Recommended:** Switch to Supabase Auth now before you have real users.

Want me to help you implement it? Just say:
- "Let's switch to Supabase Auth"
- I'll update all the files
- You run the SQL trigger
- Done! 🎉
