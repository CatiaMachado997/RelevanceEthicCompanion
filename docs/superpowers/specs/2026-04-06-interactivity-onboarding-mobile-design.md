# Design Spec: Interactivity, Bug Fixes, Onboarding & Mobile

**Date:** 2026-04-06
**Status:** Approved
**Branch:** feature/sprint-2a-foundation (worktree: `.worktrees/sprint-2a`)

---

## Overview

Seven distinct problem areas addressed in one sprint:

1. Tasks & Projects — side drawer for detail/edit/navigation
2. Goals — milestone input fix
3. Documents — PDF viewer
4. Relevance tuning — state persistence fix
5. Chat + sidebar — formatting and conversation grouping
6. Login/logout — flow hardening
7. Landing page + in-app onboarding + mobile responsiveness

---

## Tech Stack (unchanged)

Next.js 15 App Router · TypeScript · Tailwind CSS v4 · Radix UI · `@radix-ui/react-dialog` (already installed) · FastAPI backend · Supabase Auth

---

## 1. Tasks & Projects — Side Drawer Detail/Edit

### Problem
Users can create tasks and projects but items in the list are not clickable. There is no detail view, no edit form, and no way to navigate into a project.

### Components

**`frontend/components/drawers/DrawerShell.tsx`**
Shared shell built on `@radix-ui/react-dialog`. Renders as a right-side slide-in panel (width: 480px on desktop, full-width on mobile ≤ 768px). Props: `open`, `onClose`, `title`, `children`. Contains: close button (top-right X), scrollable body, sticky footer with action buttons.

**`frontend/components/drawers/TaskDrawer.tsx`**
Opens when a task row is clicked. Displays and edits:
- Title (text input)
- Description (textarea)
- Priority (select: low / medium / high / urgent)
- Status (select: todo / in_progress / done / cancelled)
- Due date (date input)
- Project assignment (select from user's projects)
- Notes (textarea, freeform)

On save: `PATCH /api/tasks/{id}` with changed fields. On delete: `DELETE /api/tasks/{id}` then close + refresh list. On close without save: confirm if dirty.

**`frontend/components/drawers/ProjectDrawer.tsx`**
Opens when a project row is clicked. Displays and edits:
- Name (text input)
- Description (textarea)
- Status (select: active / on_hold / completed / archived)

Below the edit form: **embedded task list** — shows all tasks for this project (`GET /api/tasks/?project_id={id}`). Each task is a compact row with a checkbox (toggle status) and title. "Add task" inline form at the bottom.

On save: `PATCH /api/projects/{id}`. On archive: sets status to `archived`. On close without save: confirm if dirty.

### List Row Changes

**`tasks/page.tsx`:** Each task row becomes `cursor-pointer` with `hover:ring-1 hover:ring-[var(--ec-card-border)]` styling. `onClick` sets `selectedTask` state and opens `TaskDrawer`. Drawer `onClose` calls `loadTasks()`.

**`projects/page.tsx`:** Same pattern — `selectedProject` state, `ProjectDrawer`, refresh on close.

### Data Flow
```
User clicks row → setSelectedItem(item) + setDrawerOpen(true)
→ DrawerShell renders with item data pre-filled
→ User edits → PATCH → success → close + refresh list
                       → error → show inline error in drawer footer
```

---

## 2. Goals — Milestone Input Fix

### Problem
Users cannot type in the milestone input lines. Root cause: the milestone form is inside a collapsible section that may apply `pointer-events: none` or `overflow: hidden` on the container, blocking input focus.

### Fix
- Audit the collapsible wrapper in `goals/page.tsx` for any CSS that blocks pointer events or clips the input.
- Ensure the milestone `<input>` has explicit `tabIndex={0}` and `onClick={e => e.stopPropagation()}` to prevent the collapsible toggle from intercepting clicks.
- Add `autoFocus` only when the milestone section is expanded.
- Verify the milestone add button is `type="submit"` inside its own `<form>` tag (not inside the goal's outer form if one exists).

---

## 3. Documents — PDF Viewer

### Problem
Users upload PDFs but cannot view them — only metadata is shown.

### Approach
Native browser PDF rendering via `<iframe>` inside a Radix Dialog modal. No new npm packages.

### Backend
Add `GET /api/documents/{id}/view` route that:
1. Fetches the document record from DB, verifies ownership
2. Streams the file bytes with `Content-Type: application/pdf` and `Content-Disposition: inline`
3. Returns 404 if not found, 403 if wrong user

### Frontend
**`components/DocumentViewer.tsx`**
A `@radix-ui/react-dialog` modal (full-screen on all sizes). Contains:
- Header: filename + download button (`<a href={viewUrl} download>`)
- Body: `<iframe src={viewUrl} className="w-full h-full" />`
- Close button top-right

In `documents/page.tsx`: document rows get a "View" button (eye icon) that opens `DocumentViewer` with the selected document id. Only shown when `document.status === 'ready'`. The view URL passed to the iframe is `/api/documents/{id}/view` with the Bearer token as a query param (`?token=...`) since iframes cannot set Authorization headers — the backend accepts token via either header or `?token` query param for this route only.

---

## 4. Relevance Tuning — State Persistence Fix

### Problem
`GET /api/values/` returns `{ status, count, data: UserValue[] }` but `frontend/lib/api.ts` `valuesApi.list()` reads `response.values` which is `undefined`. Result: empty values list, relevance tuning appears to reset on every load.

### Fix (frontend-only, one line)
In `frontend/lib/api.ts`, `valuesApi.list()`:
```typescript
// Before:
return response.values ?? []
// After:
return response.data ?? response.values ?? []
```

This is backward-compatible: reads `data` first (current backend), falls back to `values` (old format).

### Reorder refresh fix
After `PATCH /api/values/reorder` succeeds, the frontend re-fetches the full values list (`api.values.list()`) rather than relying on the response body (which returns no data). This ensures UI reflects server state.

---

## 5. Chat Formatting + Sidebar Grouping

### Chat Formatting
The chat page uses `react-markdown` + `remark-gfm`. Known issues to fix:
- Whitespace: consecutive newlines in AI responses collapse to single line — add `white-space: pre-wrap` to the markdown prose container, or use a `remark-breaks` plugin.
- Code blocks: ensure `<CodeBlock>` component handles language-less fences (` ``` ` with no lang tag).
- Inline code: verify `bg-muted` class applies on dark mode.
- Message bubbles: user messages right-aligned, assistant messages left-aligned with correct max-width (≤ 75% on desktop, 90% on mobile).

### Sidebar Conversation Grouping
In `chat-sidebar.tsx`:
1. Sort conversations by `updated_at` descending (most recent first) before rendering.
2. Group into date buckets client-side:
   - **Today** — `updated_at` on current calendar day
   - **Yesterday** — previous calendar day
   - **Last 7 days** — 2–7 days ago
   - **Older** — beyond 7 days
3. Each bucket is a collapsible section with a subtle label (`text-xs text-muted-foreground uppercase tracking-wide`). Buckets with no conversations are hidden. All buckets start expanded.
4. Within each bucket: conversations sorted most-recent-first.

---

## 6. Login / Logout Flow

### Login
- After magic link sent: show countdown timer ("Link expires in 10:00") that decrements every second.
- Poll `supabase.auth.getSession()` every 3 seconds — when session detected, read `ec_lastRoute` from localStorage and `router.push(lastRoute || '/dashboard')`.
- All Supabase error codes mapped to friendly messages in `friendlyAuthError()`.
- No `alert()` anywhere — all errors shown inline in the red banner.

### Logout
Sequence (in `useAuth.ts` `signOut()`):
1. Call `DELETE /api/auth/session` (clears HttpOnly backend cookie)
2. Call `supabase.auth.signOut()` (clears Supabase session)
3. Clear `localStorage.removeItem('ec_display')` and `localStorage.removeItem('ec_lastRoute')`
4. `window.location.href = '/login?signed_out=1'`

On login page mount: if `?signed_out=1` in URL params, show a subtle success banner ("You've been signed out") for 3 seconds then clear the param. This gives users confirmation without a permanent message.

### Dashboard auth guard (`app/dashboard/layout.tsx`)
Save current path to `ec_lastRoute` before redirecting to `/login` when session expires, so the user lands back where they were after re-auth.

---

## 7. Landing Page + In-App Onboarding + Mobile

### Landing Page (`app/page.tsx`)

Single viewport — no scroll. Full-height flex layout, centered vertically and horizontally.

```
[Logo / Wordmark]
[Tagline — 1 line, large]
[Description — 2 sentences, muted]
[Sign in →  button — primary, large touch target]
```

- Tagline: "Your AI work companion that respects your boundaries"
- Description: "Ethic Companion helps you make decisions, manage work, and stay focused — without dark patterns, manipulation, or engagement traps. Powered by an Ethical Safeguard Layer that puts your values first."
- Button links to `/login`
- Dark-mode aware (CSS variables already set up)
- On mobile: same layout, button is full-width, 48px tall

### In-App Empty States

Each section gets a rich empty state when the user has zero items. Pattern:

```
[Section icon — 48px, muted]
[Section title]
[One-sentence what-it-does explanation]
[Primary CTA button]
[Optional: secondary hint text]
```

Applied to:

| Section | Explanation | CTA |
|---------|-------------|-----|
| Tasks | "Tasks help you track what needs doing. Ethic Companion can extract tasks from your conversations." | "Add your first task" |
| Projects | "Projects group related tasks and goals. Keep your work organised by context." | "Create a project" |
| Goals | "Goals let you define what matters. Ethic Companion uses them to guide its responses." | "Set a goal" |
| Documents | "Upload PDFs, notes, or reports. Ethic Companion uses them to answer questions." | "Upload a document" |
| Integrations | "Connect Calendar and Gmail so Ethic Companion knows your schedule and context." | "Connect an integration" |
| Values | "Values tell Ethic Companion what you care about — your Ethical Safeguard Layer enforces them." | "Add a value" |

### Mobile Responsiveness

**Breakpoint:** `md` = 768px (Tailwind default).

| Element | Mobile (< 768px) | Desktop |
|---------|-----------------|---------|
| Sidebar | Hidden; hamburger icon top-left opens bottom sheet | Always visible left rail |
| Detail drawers | Full-screen overlay | 480px right-side panel |
| Task/project cards | Full-width single column | Grid or list |
| Chat input | Sticky bottom, `env(safe-area-inset-bottom)` padding | Normal flow |
| Touch targets | Min 44×44px on all interactive elements | Standard |
| Conversation sidebar | Bottom sheet (swipe up to expand) | Left panel |

Mobile nav bottom sheet: slides up from bottom when hamburger tapped. Contains the same nav links as the desktop sidebar. Closes on route change or tap outside.

---

## Error Handling (all areas)

- All mutations show inline error messages (never silent fail, never `alert()`).
- All loading states show a spinner or skeleton — no blank flashes.
- Network errors show a retry button where applicable.
- 401 responses trigger the existing `onUnauthorized()` flow (redirect to login).

---

## Testing

- Backend: add tests for `GET /api/documents/{id}/view` (auth check, 404, content-type header).
- Frontend: manual smoke test checklist (no automated frontend tests added in this sprint).
- ESL: no changes — ESL remains intact for all write actions.

---

## Out of Scope

- Real-time collaboration
- Push notifications
- New AI capabilities
- Changes to the ESL engine
