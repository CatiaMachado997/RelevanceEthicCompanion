# OAuth Login Providers — Design Spec

**Date:** 2026-04-16
**Scope:** Frontend login page only — no other files touched

---

## Goal

Add Google, Microsoft/Outlook, and GitHub OAuth buttons to the existing login page alongside the current email magic link flow. Users get one-click sign-in via their existing accounts.

---

## Providers

| Provider | Supabase slug | Status |
|----------|--------------|--------|
| Google | `google` | Credentials already in `.env.local`; needs enabling in Supabase Dashboard |
| Microsoft / Outlook | `azure` | Requires Azure app registration (free); then configure in Supabase |
| GitHub | `github` | Requires GitHub OAuth app; then configure in Supabase |
| Email magic link | — | Already working; kept as fallback |

---

## Auth Flow (same for all OAuth providers)

1. User clicks a provider button
2. `supabase.auth.signInWithOAuth({ provider, options: { redirectTo } })` — redirects to provider
3. Provider authenticates and redirects to `/auth/callback?code=...`
4. Existing `/auth/callback` route calls `supabase.auth.exchangeCodeForSession(code)` — no changes needed here
5. Frontend calls `POST /api/auth/session` with the access token → backend sets HttpOnly cookie
6. User lands on `/dashboard`

The callback route (`frontend/app/auth/callback/page.tsx`) already handles all OAuth providers — no changes required there.

---

## Visual Design

**Style:** Light base — white card on light grey background (`#f2f2f2`), black text, grey borders.

**Accent colour:** Sage green `#4a7c59` — used on the primary CTA button (magic link send) and hover states on OAuth buttons.

**Layout — login card (centred, unchanged structure):**

```
┌─────────────────────────────────┐
│  [logo]  Ethic Companion        │
│  Welcome back                   │
│  Sign in to continue            │
│                                 │
│  [ G  Continue with Google    ] │
│  [ ⊞  Continue with Microsoft ] │
│  [ ⌥  Continue with GitHub    ] │
│                                 │
│  ────────────── or ──────────── │
│                                 │
│  [ your@email.com             ] │
│  [ Send magic link →          ] │  ← sage green
└─────────────────────────────────┘
```

**OAuth button style:**
- White background, 1px grey border (`#e0e0e0`)
- Official provider logo (SVG, inline) on the left
- Grey label text
- On hover: border colour shifts to `#4a7c59`, subtle background tint

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/app/login/page.tsx` | Replace OTP-only form with new layout: 3 OAuth buttons + divider + existing email form |

**No other files change.** The rest of the app — dashboard, sidebar, settings, chat — is untouched.

---

## Manual Setup (one-time, not code)

These steps must be completed in external dashboards before the buttons work:

### Google
1. Supabase Dashboard → Authentication → Providers → Google
2. Enable, paste Client ID and Client Secret from `.env.local`
3. Add `https://<project-ref>.supabase.co/auth/v1/callback` to Google OAuth authorised redirect URIs

### Microsoft / Azure
1. Azure Portal → App registrations → New registration
2. Redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`
3. Certificates & secrets → New client secret → copy value
4. Supabase Dashboard → Authentication → Providers → Azure → enable, paste App ID + Secret

### GitHub
1. github.com/settings/developers → OAuth Apps → New OAuth App
2. Callback URL: `https://<project-ref>.supabase.co/auth/v1/callback`
3. Copy Client ID + Client Secret
4. Supabase Dashboard → Authentication → Providers → GitHub → enable, paste values

---

## What Is Not In Scope

- Redesigning any page other than login
- Changing the dashboard colour scheme
- Adding Slack or any other provider
- Dark mode
- User profile / account management
