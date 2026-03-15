# Settings Feature Design

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Backend routes + frontend wiring for user settings

---

## Problem

The `user_settings` table exists and the frontend Settings page has UI toggles, but the switches are unconnected stubs — no backend routes, no API client, no state management.

---

## Design

### Backend

Two endpoints in `backend/routes/settings.py`, registered in `main.py`.

**GET /api/settings/**
- Auth: `get_current_read_user_id`
- Fetches the user's row from `user_settings`
- If no row exists, returns defaults: `esl_alerts=true`, all others `false`
- No ESL gate (read-only, no side effects)

**PUT /api/settings/**
- Auth: `get_current_user_id`
- ESL gate: `ActionType.DATA_COLLECTION`, `UrgencyLevel.LOW`
- Upserts all 5 fields in one query (`INSERT ... ON CONFLICT DO UPDATE`)
- Returns the saved row

**Request body:**
```json
{
  "email_notifications": false,
  "push_notifications": false,
  "esl_alerts": true,
  "share_analytics": false,
  "pii_protection": true
}
```

**Response envelope:**
```json
{ "status": "success", "data": { ...all fields + updated_at... } }
```

**Tests (`test_settings_routes.py`):**
- `test_get_settings_returns_defaults` — no DB row → defaults returned
- `test_get_settings_returns_saved` — DB row exists → values returned
- `test_update_settings_success` — PUT → 200, data matches payload
- `test_update_settings_vetoed_by_esl` — ESL vetoes → 403

Same mock pattern as `test_values_routes.py` (DB context manager mock, ESL dependency override).

---

### Frontend

**`lib/api.ts`** — add `settingsApi`:
```ts
settingsApi.get()       // GET /api/settings/
settingsApi.update(payload)  // PUT /api/settings/
```

**`app/dashboard/settings/page.tsx`** — wire the 5 switches:
- On mount: call `settingsApi.get()` → populate state
- Local state: 5 booleans + `dirty` flag (true when any switch changes)
- Single **"Save Settings"** button — disabled when `!dirty` or `saving`
- On save: call `settingsApi.update(...)` → success/error toast → reset `dirty`
- Data Management and Appearance cards remain disabled (no backend yet)

---

## Out of Scope

- Dark mode / theme switching
- Data export / account deletion
- Appearance preferences beyond what's in the table
