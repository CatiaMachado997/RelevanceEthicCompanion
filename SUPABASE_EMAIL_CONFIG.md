# Supabase Email Configuration Guide

## Problem
When signing up, Supabase sends a confirmation email and tries to redirect to a URL that doesn't exist locally.

## Solution: Disable Email Confirmation for Development

### Quick Fix (Recommended for Local Development)

1. **Open Supabase Dashboard** → https://supabase.com/dashboard
2. Navigate to your project: **ethic-companion** (or your project name)
3. Go to **Authentication** in the left sidebar
4. Click on **Email** (under Providers)
5. **Find "Confirm email" toggle**
6. **Turn it OFF** (disable it)
7. Click **Save**

Now users can sign up immediately without email confirmation!

---

## Alternative: Keep Email Confirmation (Production Setup)

If you want to keep email verification enabled:

### Step 1: Configure URLs

1. **Go to Authentication** → **URL Configuration**
2. **Set Site URL**: `http://localhost:3000`
3. **Add Redirect URLs**:
   ```
   http://localhost:3000/**
   http://localhost:3000/auth/callback
   ```
4. Click **Save**

### Step 2: Update Email Template

1. **Go to Authentication** → **Email Templates**
2. **Select "Confirm signup"**
3. **Update the confirmation URL** to:
   ```
   {{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=signup
   ```
4. Click **Save**

### Step 3: Test the Flow

1. Visit http://localhost:3000
2. Click "Sign up"
3. Enter email and password
4. Check your email for confirmation link
5. Click the link → should redirect to `/auth/callback` → then to `/dashboard`

---

## Frontend Changes Already Made

✅ Created `/app/auth/callback/page.tsx` - handles email confirmation redirects  
✅ Updated Supabase client with `detectSessionInUrl: true`  
✅ Updated login page to use callback URL  

---

## Testing After Configuration

1. **Test Signup**:
   ```bash
   # Visit in browser:
   http://localhost:3000
   ```

2. **Sign up with a test email**:
   - Email: `test@example.com`
   - Password: `SecurePassword123!`

3. **With email confirmation DISABLED**:
   - Should immediately redirect to `/dashboard`
   - No email sent

4. **With email confirmation ENABLED**:
   - You'll see "Check your email" message
   - Click confirmation link in email
   - Should redirect through `/auth/callback` to `/dashboard`

---

## Production Setup (Later)

For production deployment:

1. **Set Site URL** to your production domain:
   ```
   https://your-domain.com
   ```

2. **Update Redirect URLs**:
   ```
   https://your-domain.com/**
   https://your-domain.com/auth/callback
   ```

3. **Enable Email Confirmation** for security

4. **Configure SMTP** (optional):
   - Use a custom email provider (SendGrid, Mailgun, etc.)
   - Supabase → Settings → Auth → Email Provider

---

## Current Status

- ✅ Backend running: http://localhost:8000
- ✅ Frontend running: http://localhost:3000
- ✅ SQL migration executed
- ✅ Auth callback handler created
- ⏳ **Need to configure email settings in Supabase Dashboard** (see above)

Once you disable email confirmation or configure the redirect URLs, the signup flow will work perfectly!
