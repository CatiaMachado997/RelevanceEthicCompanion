# Frontend Component Tests & UX Polish — Design

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Fix broken dashboard test, add component tests for settings/notifications, add inline error display to notifications page.

---

## Track A: Component Tests

### Fix broken test

`__tests__/dashboard.test.tsx` fails because the dashboard component no longer renders "Loading your dashboard..." — it was updated. Fix the test to match current component output (uses `Skeleton` components during load, not a text string).

### New test: `__tests__/settings.test.tsx`

Mock `settingsApi` from `../lib/api`. Test:
- `test_settings_loads_on_mount` — `settingsApi.get()` called on render, switches reflect returned values
- `test_save_button_disabled_when_clean` — Save button is disabled initially (no changes made)
- `test_save_button_enabled_after_toggle` — toggling a switch enables the Save button
- `test_save_calls_api` — clicking Save calls `settingsApi.update()` with current values

### New test: `__tests__/notifications.test.tsx`

Mock `notificationsApi` from `../lib/api`. Test:
- `test_notifications_loads_on_mount` — `notificationsApi.list()` called, items rendered
- `test_mark_all_read_hidden_when_no_unread` — button absent when `unread_count === 0`
- `test_mark_all_read_visible_when_unread` — button present when `unread_count > 0`
- `test_click_unread_card_marks_read` — clicking unread card calls `notificationsApi.markRead(id)`

All tests use `jest.mock('../lib/api')`, `render()` from `@testing-library/react`, `screen` queries, and `userEvent` for interactions.

---

## Track D: UX Polish — Notifications error display

`frontend/app/dashboard/notifications/page.tsx` currently silently swallows errors from `markRead()` and `markAllRead()` via `console.error`. Add an inline error state:

- Add `error` state string, initially `null`
- On `markRead` or `markAllRead` failure: set `error` to `"Failed to update notification. Please try again."`
- Clear `error` on successful `load()`
- Render below the header: `{error && <p className="text-sm text-[#DC2626]">{error}</p>}`

This matches the existing pattern in `settings/page.tsx` (`saveError` state + `text-[#DC2626]` paragraph).

---

## Out of scope

- End-to-end or integration tests
- Chat UX (already handles errors by injecting an assistant error message)
- Settings UX (already has error display)
- Profile page changes
