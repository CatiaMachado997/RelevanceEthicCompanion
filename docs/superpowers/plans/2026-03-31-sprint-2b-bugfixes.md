# Sprint 2b: Frontend Bug Fixes + UX Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all reported frontend bugs: login/logout robustness, settings state, sidebar conversation refresh, milestones, integrations stats, projects/tasks errors, and document upload.

**Architecture:** Next.js 15 App Router + Supabase Auth + FastAPI backend. Auth uses Bearer tokens for regular API calls (`apiRequest`) and HttpOnly cookies for EventSource streaming. Working directory: `.worktrees/sprint-2a`.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, Radix UI, Supabase JS SDK

---

## Root Causes Summary

| Bug | Root Cause |
|-----|-----------|
| Login/logout not robust | `signOut()` has no explicit redirect; login error states incomplete |
| Settings lose state | `setSaveError(null)` missing on some field change handlers |
| Sidebar doesn't refresh | `useEffect([], [])` — empty dep array, no mechanism to trigger refresh |
| Milestones silent fail | No try-catch in inline form submit handler |
| Integrations stats stale | `loadConnected()` called after sync but stats not refetched |
| Projects/Tasks errors hidden | `apiRequest` error message not always shown; backend may return 500/401 |
| Documents upload | Error display exists but upload error message from backend not extracted properly |

---

## Task BF-1: Auth — Login Robustness + Logout Redirect

**Files:** `frontend/app/login/page.tsx`, `frontend/hooks/useAuth.ts`

**Before writing, read both files fully.**

- [ ] **Step 1: Fix signOut to redirect explicitly**

  In `frontend/hooks/useAuth.ts`, update `signOut`:
  ```typescript
  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
    // Clear all local state immediately — don't wait for event
    localStorage.removeItem('ec_display')
    localStorage.removeItem('access_token') // belt-and-suspenders
    window.location.href = '/login'
  }, [])
  ```

- [ ] **Step 2: Fix login page — error display + loading state + redirect**

  Read `frontend/app/login/page.tsx`. Ensure it has:
  1. A visible `error` state shown in a red alert box (if not present, add it)
  2. A `loading` state that disables the submit button and shows spinner
  3. On successful sign-in: redirect to `/dashboard` (or `localStorage.getItem('ec_lastRoute') || '/dashboard'`)
  4. Auth errors from Supabase shown as user-friendly messages (not raw error codes)

  Common Supabase error messages to map:
  ```typescript
  function friendlyAuthError(msg: string): string {
    if (msg.includes('Invalid login credentials')) return 'Incorrect email or password.'
    if (msg.includes('Email not confirmed')) return 'Please verify your email first.'
    if (msg.includes('Too many requests')) return 'Too many attempts. Please wait a moment.'
    return msg
  }
  ```

- [ ] **Step 3: Save last route before redirect to login**

  In `frontend/app/dashboard/layout.tsx`, before redirecting:
  ```typescript
  // When redirecting to /login, save current route
  if (!loading && !isAuthenticated) {
    localStorage.setItem('ec_lastRoute', window.location.pathname)
    router.push('/login')
  }
  ```

  In login page, on success:
  ```typescript
  const lastRoute = localStorage.getItem('ec_lastRoute') || '/dashboard'
  localStorage.removeItem('ec_lastRoute')
  router.push(lastRoute)
  ```

- [ ] **Step 4: Commit**
  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a && git add frontend/app/login/ frontend/hooks/useAuth.ts frontend/app/dashboard/layout.tsx
  git commit -m "fix(auth): explicit logout redirect, friendly login errors, last-route restore"
  ```

---

## Task BF-2: Settings — State Persistence

**Files:** `frontend/app/dashboard/settings/page.tsx`

**Read the full file before making changes.**

- [ ] **Step 1: Clear error on ANY field change**

  Find every `onChange` handler in the settings page. Ensure each one calls `setSaveError(null)` and `setSaveSuccess(false)`:
  ```typescript
  // Pattern for every select/input onChange:
  onChange={e => {
    setSettings(prev => ({ ...prev, fieldName: e.target.value || undefined }))
    setDirty(true)
    setSaveSuccess(false)
    setSaveError(null)  // ← ensure this exists on every handler
  }}
  ```

- [ ] **Step 2: Prevent form reset when navigating back**

  Settings should load from backend on mount (already exists). Make sure:
  - The initial load sets ALL fields (including timezone, language, new fields)
  - The form's `onSubmit` does not re-initialize state after save (only clears dirty flag)

- [ ] **Step 3: Fix appearance section localStorage hydration**

  If `localStorage` is accessed during SSR it throws. Wrap in `useEffect`:
  ```typescript
  const [appearance, setAppearance] = useState<Record<string, unknown>>({})
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ec_appearance')
      if (saved) setAppearance(JSON.parse(saved))
    } catch {}
  }, [])
  ```

- [ ] **Step 4: Show success/error feedback**

  After save, show a transient success message. If already shown, verify it auto-dismisses after 3s:
  ```typescript
  useEffect(() => {
    if (saveSuccess) {
      const t = setTimeout(() => setSaveSuccess(false), 3000)
      return () => clearTimeout(t)
    }
  }, [saveSuccess])
  ```

- [ ] **Step 5: Commit**
  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a && git add frontend/app/dashboard/settings/
  git commit -m "fix(settings): clear error on field change, fix SSR localStorage, auto-dismiss success"
  ```

---

## Task BF-3: Chat Sidebar — Live Conversation List

**Files:** `frontend/components/sidebars/chat-sidebar.tsx`, `frontend/app/dashboard/chat/page.tsx`

**Read both files fully before writing.**

The sidebar's conversation list only loads once on mount. New conversations created in the chat page are not reflected. Fix this with a polling mechanism (simplest solution that avoids prop drilling or context changes).

- [ ] **Step 1: Add polling to sidebar**

  In `frontend/components/sidebars/chat-sidebar.tsx`, change the useEffect to refresh every 10 seconds while mounted:

  ```typescript
  useEffect(() => {
    let cancelled = false

    const load = () => {
      api.chat.conversations.list()
        .then(res => {
          if (!cancelled) setConversations(res.conversations ?? [])
        })
        .catch(() => {})
        .finally(() => { if (!cancelled) setLoading(false) })
    }

    load() // immediate first load

    const interval = setInterval(load, 10_000) // refresh every 10s
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])
  ```

- [ ] **Step 2: Optimistic update when new chat created**

  In `frontend/app/dashboard/chat/page.tsx`, after creating a conversation, ensure the sidebar gets the new conversation. Since polling handles eventual consistency, also dispatch a `storage` event as a cheap cross-component signal:

  ```typescript
  // After creating conversation:
  const newConv = await api.chat.conversations.create()
  // Signal sidebar to refresh
  window.dispatchEvent(new Event('ec:conversation-created'))
  ```

  In sidebar:
  ```typescript
  useEffect(() => {
    const handler = () => {
      api.chat.conversations.list()
        .then(res => setConversations(res.conversations ?? []))
        .catch(() => {})
    }
    window.addEventListener('ec:conversation-created', handler)
    return () => window.removeEventListener('ec:conversation-created', handler)
  }, [])
  ```

- [ ] **Step 3: Better empty state**

  If conversations is empty and not loading:
  ```tsx
  {!loading && conversations.length === 0 && (
    <div className="px-3 py-6 text-center text-muted-foreground">
      <p className="text-sm">No conversations yet.</p>
      <p className="text-xs mt-1">Start chatting to create one.</p>
    </div>
  )}
  ```

- [ ] **Step 4: Commit**
  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a && git add frontend/components/sidebars/chat-sidebar.tsx frontend/app/dashboard/chat/
  git commit -m "fix(chat): sidebar polls conversations every 10s + event-driven refresh on new chat"
  ```

---

## Task BF-4: Goals Milestones + Integrations Stats

**Files:** `frontend/app/dashboard/goals/page.tsx`, `frontend/app/dashboard/integrations/page.tsx`

**Read both files before writing.**

### Goals — Milestone Add

- [ ] **Step 1: Add try-catch + error display to milestone form**

  Find the inline `onSubmit` for the milestone form. Replace with:
  ```typescript
  onSubmit={async e => {
    e.preventDefault()
    const title = (milestoneInput[goal.id] || '').trim()
    if (!title) return
    try {
      await api.goals.milestones.create(goal.id, title)
      setMilestoneInput(prev => ({ ...prev, [goal.id]: '' }))
      loadMilestones(goal.id)
    } catch (err) {
      // Show inline error near the form
      setMilestoneError(prev => ({
        ...prev,
        [goal.id]: err instanceof Error ? err.message : 'Failed to add milestone'
      }))
    }
  }}
  ```

  Add state: `const [milestoneError, setMilestoneError] = useState<Record<string, string>>({})` at the top.

  Show error under the form:
  ```tsx
  {milestoneError[goal.id] && (
    <p className="text-xs text-destructive mt-1">{milestoneError[goal.id]}</p>
  )}
  ```

  Clear error when input changes:
  ```tsx
  onChange={e => {
    setMilestoneInput(prev => ({ ...prev, [goal.id]: e.target.value }))
    setMilestoneError(prev => ({ ...prev, [goal.id]: '' }))
  }}
  ```

### Integrations — Stats Refresh After Sync

- [ ] **Step 2: Refetch stats after sync**

  Find `handleSync`. After `loadConnected()`, also refresh stats:
  ```typescript
  const handleSync = async (type: SourceType) => {
    setSyncing(type)
    try {
      await dataSourcesApi.sync(type)
      await loadConnected()
      // Refresh stats after sync
      try {
        const s = await dataSourcesApi.stats()
        setStats(s)
      } catch { /* stats non-critical */ }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(null)
    }
  }
  ```

- [ ] **Step 3: Show connection success message after OAuth callback**

  In the integrations page, check for `?connected=<source>` URL param on mount and show a success banner:
  ```typescript
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('connected')
    if (connected) {
      setSuccess(`${connected} connected successfully!`)
      // Clean up URL
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])
  ```

- [ ] **Step 4: Commit**
  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a && git add frontend/app/dashboard/goals/ frontend/app/dashboard/integrations/
  git commit -m "fix(goals): milestone add try-catch + error display; fix(integrations): refetch stats after sync + OAuth success banner"
  ```

---

## Task BF-5: Projects, Tasks, Documents — Error Hardening

**Files:** `frontend/app/dashboard/projects/page.tsx`, `frontend/app/dashboard/tasks/page.tsx`, `frontend/app/dashboard/documents/page.tsx`, `frontend/lib/api.ts`

**Read all four files before writing.**

The error handling exists in UI but the error message from `apiRequest` may not extract the backend's error message clearly.

- [ ] **Step 1: Improve `apiRequest` error extraction**

  In `frontend/lib/api.ts`, find the `apiRequest` function error handling. When the response is not OK, ensure it extracts the `detail` or `message` field from the JSON body:
  ```typescript
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail || body.message || body.error || detail
    } catch {}
    throw new Error(detail)
  }
  ```

  **Do NOT change this if it already does this correctly** — just verify and improve.

- [ ] **Step 2: Projects — verify error display**

  In `frontend/app/dashboard/projects/page.tsx`:
  - Verify `createError` is displayed prominently above or below the form
  - Add a "Try again" affordance by not clearing the form on error
  - Log to console for debugging: `console.error('Project create failed:', e)`

- [ ] **Step 3: Tasks — verify error display**

  Same as projects — verify `createError` is shown, form keeps its values on error.

- [ ] **Step 4: Documents — verify upload error**

  In `frontend/app/dashboard/documents/page.tsx`:
  - Verify `uploadError` is displayed to the user (not just in a hidden div)
  - The document upload uses `fetch` directly (not `apiRequest`) — verify the error response body is extracted:
  ```typescript
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || body.message || `Upload failed (${response.status})`)
  }
  ```

- [ ] **Step 5: Check backend projects + tasks routes exist**
  ```bash
  source /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/activate && cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/backend && python -c "
  from main import app
  routes = [r.path for r in app.routes]
  for r in routes:
      if 'project' in r or 'task' in r:
          print(r)
  "
  ```
  If routes don't exist, note it — do NOT create them in this task.

- [ ] **Step 6: Commit**
  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a && git add frontend/lib/api.ts frontend/app/dashboard/projects/ frontend/app/dashboard/tasks/ frontend/app/dashboard/documents/
  git commit -m "fix(api): extract backend error detail; fix(projects/tasks/docs): keep form on error, improve error visibility"
  ```
