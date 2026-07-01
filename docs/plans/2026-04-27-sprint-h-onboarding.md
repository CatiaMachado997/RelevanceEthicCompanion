# Sprint H — First-run onboarding

Date: 2026-04-27
Status: Plan
Predecessors: Sprints A–G ✅

## Why this sprint exists

Every other sprint assumes a populated, configured account. A genuine first
login today lands on:

- Today: empty (no tasks, no email, no calendar — connectors aren't linked)
- Chat: empty list, no values to ground anything on
- Dashboard: hero with no goals, no projects
- Settings: sources unconnected, values blank

The user has no signal of what to do first, and the agent has no values, no
goals, and no data to work with even if they did chat. Every "trust over
engagement" affordance the ESL provides is moot when `user_values` is empty —
the engine has nothing to gate against.

A first-run wizard fixes this: connect at least one source, declare 2–3
values, seed one goal, land on Today with something already populated.
Skippable per step but persistently nudged until done.

## Goals

1. **First-time users land in the wizard, not the empty dashboard.** Detected
   server-side from a single `users.onboarded_at` column, surfaced via the
   existing `/api/auth/me` response.
2. **The wizard is three short steps, each skippable.** Connect a source →
   declare values → seed a goal. Each step persists immediately so a refresh
   doesn't lose progress.
3. **The agent has something to gate against on day one.** At least one
   user_value is the success criterion — without it the ESL has no teeth.
4. **Returning users see a "finish setup" nudge** in the dashboard sidebar
   until `onboarded_at` is set, but it's dismissable.

## Architecture decisions

- **Single boolean-shaped flag, not a multi-step state machine.**
  `users.onboarded_at TIMESTAMPTZ NULL`. Set when the user completes step 3 OR
  hits "Skip setup" on the wizard's intro. Anything more granular invites
  drift between the flag and the actual data — and the underlying tables
  (`data_sources`, `user_values`, `goals`) are the source of truth for what's
  been done.
- **Wizard is its own route, not a modal.** `/onboarding` with a redirect
  guard in dashboard layout. Modals over an empty dashboard look like a
  mistake; a dedicated route makes the first impression intentional.
- **Step persistence is "save on next-button-press," not auto-save.** Reuses
  the existing endpoints (`/api/data-sources/...`, `/api/values`, `/api/goals`)
  unchanged. No new write endpoints — only one new GET (`/api/onboarding/state`)
  and one PATCH (`/api/onboarding/complete`).
- **The "finish setup" nudge is a dashboard sidebar tile, not a global
  banner.** Banners across all pages feel pushy; one card in the home view
  is enough.

## Tasks (one commit each)

### 1. Backend onboarding state
- Migration `016_user_onboarded_at.sql`: `ALTER TABLE users ADD COLUMN onboarded_at TIMESTAMPTZ NULL;`
- `routes/onboarding.py` — new router:
  - `GET /api/onboarding/state` returns `{ onboarded_at, has_data_source, has_value, has_goal }`. Single query joining `users` against existence checks for the three downstream tables.
  - `POST /api/onboarding/complete` sets `onboarded_at = NOW()` if NULL.
- `routes/auth.py` `/me` response: include `onboarded_at` so the frontend can route on first paint without a second roundtrip.
- 1 test: state endpoint returns the three has-* flags correctly across (empty / partial / complete) fixtures.

### 2. Wizard route + step components
- `frontend/app/onboarding/page.tsx` — three-step wizard, query param `?step=1|2|3` for back/forward without remount.
- `components/onboarding/StepConnect.tsx` — lists Gmail / Google Calendar / Slack with an inline "Connect" button each (uses existing OAuth start endpoints). Step is "complete" when `has_data_source` flips true; "Continue" stays disabled-but-skippable until then. Skip → next step.
- `components/onboarding/StepValues.tsx` — three text inputs labeled "Something you want the assistant to honor" with three example placeholders ("Don't ping me after 7pm", "Avoid manipulative phrasing", "Prefer concise answers"). On Continue: POST each non-empty input as a `user_values` row, type=`boundary`, priority 5.
- `components/onboarding/StepGoal.tsx` — single text input + optional "by when" date. POST to `/api/goals` on Continue. Skip allowed.
- Final screen: "You're set. Take me to Today." → `POST /api/onboarding/complete` then `router.replace('/dashboard/today')`.
- Frontend typecheck must stay green.

### 3. Redirect guard
- `frontend/app/dashboard/layout.tsx` — read `user.onboarded_at` from the auth context (already loaded via `/api/auth/me`). If null AND we have no data_source AND no value AND no goal, redirect to `/onboarding`. The triple-AND is intentional: a returning user who skipped the wizard but has manually added one value shouldn't be re-trapped.
- Add `useOnboardingState()` hook that reads from `/api/onboarding/state` with React Query.

### 4. Sidebar "finish setup" nudge
- `components/sidebars/dashboard-sidebar.tsx` — when `onboarded_at` is null OR any of the three has-* flags is false, render a small card: "Finish setting up · 2 of 3 done" with a "Continue" link to `/onboarding`. Dismissable via localStorage flag (`ec_onboarding_nudge_dismissed`); reappears on next session if state is still incomplete.
- 1 frontend smoke test (or visual check if no test infra exists for the sidebar).

### 5. Full suite + push + PR update
- `pytest --tb=short -q` ; `cd frontend && npx tsc --noEmit`. Both green.
- Push. Update PR #48 body with a Sprint H section.

## Verification

```bash
cd backend
pytest tests/test_onboarding.py -v
pytest --tb=short -q

cd ../frontend
npx tsc --noEmit
```

**Manual checklist:**
1. Wipe state for the test user (or create a fresh account). Log in. Land on
   `/onboarding` automatically.
2. Walk through all three steps — connect Gmail, declare two values, seed a
   goal. Land on Today; goal is visible, ESL has values to gate against.
3. Refresh mid-wizard at step 2 — return to step 2, not step 1, with the
   already-saved value persisted.
4. Log in as a user with `onboarded_at = NULL` but with one existing value
   (e.g. an account where wizard was skipped earlier). Confirm no forced
   redirect; sidebar nudge is visible until completion or dismissal.
5. Click "Skip setup" on step 1 — `onboarded_at` is set, redirect to Today
   works, sidebar nudge still appears (not yet dismissed) reflecting the
   incomplete state.

## Out of scope

- **Re-onboarding flow** for users who want to redo the wizard — settings
  pages already cover edits.
- **Workspace/team setup** — single-tenant for now.
- **Tour/coachmarks over the dashboard.** The wizard collects data; a tour
  teaches the UI. Different problem, different sprint.
- **Onboarding email/notification.** ESL would gate that anyway and we'd
  rather not.

## Open questions deferred to execution

- Do we want the wizard to be reachable from settings (e.g. "Re-run setup")?
  Lean no for v1 — settings already lets you connect sources, add values,
  add goals individually.
- How wide is the values input — three fixed slots or "+ add another"?
  Start with three slots. Real users rarely articulate more than three on
  first pass; bloat invites blank rows.
- Should we pre-seed any "starter" values if the user types nothing?
  No. Empty values is honest. The nudge will keep reminding.
