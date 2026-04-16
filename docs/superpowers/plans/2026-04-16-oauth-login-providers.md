# OAuth Login Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google, Microsoft, and GitHub OAuth buttons to the login page and apply sage green `#4a7c59` as a subtle accent throughout the existing app.

**Architecture:** Two surgical changes — (1) update CSS variables in `globals.css` to introduce sage green as the accent colour (focus rings, sidebar active state, CTA buttons), (2) add three OAuth provider buttons to the existing login page right panel above the email form. The `/auth/callback` route already handles all OAuth providers — no changes needed there. The `useAuth` hook's `onAuthStateChange` listener already calls `exchangeSessionCookie` on `SIGNED_IN` — OAuth sessions flow through it automatically.

**Tech Stack:** Next.js App Router, TypeScript, Tailwind CSS v4, `@supabase/supabase-js`, inline SVG provider logos (no extra packages)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/app/globals.css` | Modify | Add `--ec-accent`, `--ec-accent-hover`, `--ec-accent-muted` variables; update `--ring` and `--ec-sidebar-active` to use sage green |
| `frontend/app/login/page.tsx` | Modify | Add `handleOAuthSignIn` function; add Google, Microsoft, GitHub buttons above email form; change CTA button to sage green |

---

## Task 1: Apply sage green accent in globals.css

**Files:**
- Modify: `frontend/app/globals.css`

The app already uses `#4A7C59` for ESL-approved states and chat links. This task promotes it to the global accent by adding three new variables and updating two existing ones. No layout or structural changes — only colour values.

- [ ] **Step 1: Add the three new accent CSS variables**

Open `frontend/app/globals.css`. Find the `:root` block that contains `--esl-approved: #4A7C59;`. Add the three new variables directly below it:

```css
/* ── Sage green accent ── */
--ec-accent:       #4a7c59;   /* primary accent — buttons, active states */
--ec-accent-hover: #3d6b4a;   /* darker on hover */
--ec-accent-muted: rgba(74, 124, 89, 0.10); /* subtle background tint */
```

- [ ] **Step 2: Update `--ring` to use sage green**

In the same `:root` block, find:
```css
--ring: 0 0% 10%;                /* #1a1a1a */
```
Replace with:
```css
--ring: 145 25% 39%;             /* #4a7c59 — sage green focus rings */
```

- [ ] **Step 3: Update `--ec-sidebar-active` to use the muted green tint**

In the `:root` block containing `--ec-sidebar-active`, find:
```css
--ec-sidebar-active: #f0f0f0;
```
Replace with:
```css
--ec-sidebar-active: rgba(74, 124, 89, 0.10);
```

- [ ] **Step 4: Verify visually**

```bash
cd frontend && npm run dev
```

Open http://localhost:3000/dashboard. Check:
- Clicking any input shows a green focus ring (not black)
- Active/selected sidebar items have a subtle green tint background
- No layout shifts or broken styles

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: apply sage green accent — focus rings, sidebar active state"
```

---

## Task 2: Add OAuth provider buttons to login page

**Files:**
- Modify: `frontend/app/login/page.tsx`

Add a `handleOAuthSignIn` function and three provider buttons (Google, Microsoft, GitHub) above the existing email form in the right panel. Change the "Send magic link" button colour from `#1c1520` to `#4a7c59`. Keep the entire left panel and page structure untouched.

- [ ] **Step 1: Add `handleOAuthSignIn` and `oauthLoading` state**

Open `frontend/app/login/page.tsx`. Find the existing state declarations at the top of `LoginPage`:

```typescript
const [email, setEmail] = useState('')
const [sent, setSent] = useState(false)
const [isSubmitting, setIsSubmitting] = useState(false)
const [error, setError] = useState<string | null>(null)
const [signedOut, setSignedOut] = useState(false)
const { signIn } = useAuth()
```

Replace with:

```typescript
const [email, setEmail] = useState('')
const [sent, setSent] = useState(false)
const [isSubmitting, setIsSubmitting] = useState(false)
const [oauthLoading, setOauthLoading] = useState<string | null>(null)
const [error, setError] = useState<string | null>(null)
const [signedOut, setSignedOut] = useState(false)
const { signIn } = useAuth()

const handleOAuthSignIn = async (provider: 'google' | 'azure' | 'github') => {
  setOauthLoading(provider)
  setError(null)
  const redirectTo = `${process.env.NEXT_PUBLIC_SITE_URL ?? window.location.origin}/auth/callback`
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo },
  })
  if (error) {
    setError(friendlyAuthError(error.message))
    setOauthLoading(null)
  }
  // On success: browser redirects to provider — no further action needed here
}
```

- [ ] **Step 2: Add the three OAuth provider buttons above the email form**

In the right panel JSX, find the `<form onSubmit={handleSubmit}>` element. Insert the following block **immediately before** the `<form>` tag:

```tsx
{/* OAuth provider buttons */}
<div className="flex flex-col gap-2 mb-6">
  {/* Google */}
  <button
    type="button"
    onClick={() => handleOAuthSignIn('google')}
    disabled={!!oauthLoading}
    className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
    style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = '#4a7c59' }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
  >
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
    {oauthLoading === 'google' ? 'Redirecting…' : 'Continue with Google'}
  </button>

  {/* Microsoft */}
  <button
    type="button"
    onClick={() => handleOAuthSignIn('azure')}
    disabled={!!oauthLoading}
    className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
    style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = '#4a7c59' }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
  >
    <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
      <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
      <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
    </svg>
    {oauthLoading === 'azure' ? 'Redirecting…' : 'Continue with Microsoft'}
  </button>

  {/* GitHub */}
  <button
    type="button"
    onClick={() => handleOAuthSignIn('github')}
    disabled={!!oauthLoading}
    className="w-full h-11 rounded-xl flex items-center gap-3 px-4 text-sm font-medium border transition-all disabled:opacity-50"
    style={{ background: '#fff', borderColor: '#e0e0e0', color: '#111' }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = '#4a7c59' }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = '#e0e0e0' }}
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
    {oauthLoading === 'github' ? 'Redirecting…' : 'Continue with GitHub'}
  </button>
</div>

{/* Divider */}
<div className="flex items-center gap-3 mb-6">
  <div className="flex-1 h-px" style={{ background: '#e0e0e0' }} />
  <span className="text-xs" style={{ color: '#9e9e9e' }}>or continue with email</span>
  <div className="flex-1 h-px" style={{ background: '#e0e0e0' }} />
</div>
```

- [ ] **Step 3: Change the "Send magic link" button colour to sage green**

Find the existing submit button:
```tsx
style={{ background: '#1c1520', color: '#ffffff' }}
onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = '#2e2434' }}
onMouseLeave={(e) => { e.currentTarget.style.background = '#1c1520' }}
```

Replace with:
```tsx
style={{ background: '#4a7c59', color: '#ffffff' }}
onMouseEnter={(e) => { if (!isSubmitting) e.currentTarget.style.background = '#3d6b4a' }}
onMouseLeave={(e) => { e.currentTarget.style.background = '#4a7c59' }}
```

- [ ] **Step 4: Verify in the browser**

```bash
cd frontend && npm run dev
```

Open http://localhost:3000/login. Check:
- Three provider buttons appear above the email form
- Each button shows a hover border in sage green
- "Send magic link" button is sage green
- Left dark panel is unchanged
- On mobile (resize window): buttons stack correctly

- [ ] **Step 5: Commit**

```bash
git add frontend/app/login/page.tsx
git commit -m "feat: add Google, Microsoft, GitHub OAuth buttons to login page"
```

---

## Manual Setup Checklist (not code — do once in dashboards)

These must be completed before the OAuth buttons work in production.

### Supabase project reference
Find it at: https://supabase.com/dashboard → your project → Settings → General → Reference ID
Callback URL to use everywhere: `https://<ref>.supabase.co/auth/v1/callback`

### Google
1. [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials → Edit your OAuth 2.0 Client
2. Add `https://<ref>.supabase.co/auth/v1/callback` to **Authorized redirect URIs**
3. Supabase Dashboard → Authentication → Providers → Google → Enable → paste Client ID + Secret from `.env.local`

### Microsoft / Azure
1. [portal.azure.com](https://portal.azure.com) → App registrations → New registration
   - Name: `Ethic Companion`
   - Redirect URI: `https://<ref>.supabase.co/auth/v1/callback`
2. Certificates & Secrets → New client secret → copy the **Value** (not the ID)
3. Copy the **Application (client) ID** from Overview
4. Supabase Dashboard → Authentication → Providers → Azure → Enable → paste App ID + Secret

### GitHub
1. [github.com/settings/developers](https://github.com/settings/developers) → OAuth Apps → New OAuth App
   - Homepage URL: `https://your-app-url.com`
   - Callback URL: `https://<ref>.supabase.co/auth/v1/callback`
2. Copy Client ID + generate a Client Secret
3. Supabase Dashboard → Authentication → Providers → GitHub → Enable → paste values

### Local dev redirect
For local testing add `http://localhost:3000/auth/callback` to each provider's redirect/callback list (in addition to the production Supabase URL).
