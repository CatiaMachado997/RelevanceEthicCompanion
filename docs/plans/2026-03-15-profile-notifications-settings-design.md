# Profile, Notifications & Settings — Design Document

**Goal:** Wire up three stubbed dashboard pages to real backend data.

---

## Section 1: Database

### Migration — `users` table additions
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';
```

### New table — `user_notifications`
```sql
CREATE TABLE IF NOT EXISTS user_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL,  -- 'esl_block', 'goal_completed', 'info'
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);
CREATE INDEX ON user_notifications (user_id, created_at DESC);
```

### New table — `user_settings`
```sql
CREATE TABLE IF NOT EXISTS user_settings (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  email_notifications BOOLEAN DEFAULT FALSE,
  push_notifications BOOLEAN DEFAULT FALSE,
  esl_alerts BOOLEAN DEFAULT TRUE,
  share_analytics BOOLEAN DEFAULT FALSE,
  pii_protection BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Section 2: Backend Routes

### `backend/routes/profile.py`
- `GET /api/profile/` — returns `display_name`, `timezone`, live stats (values count, active goals count, ESL approval rate from audit log)
- `PUT /api/profile/` — saves `display_name` and `timezone`

### `backend/routes/notifications.py`
- `GET /api/notifications/` — list for user, newest first; optional `?unread_only=true`
- `PATCH /api/notifications/{id}/read` — mark one read
- `PATCH /api/notifications/read-all` — mark all read

Notifications are inserted inline (no worker):
- `routes/goals.py::complete_goal` — insert `goal_completed` notification on success
- Any route where ESL returns VETOED — insert `esl_block` notification

### `backend/routes/settings.py`
- `GET /api/settings/` — returns toggles; upserts default row on first call
- `PUT /api/settings/` — saves all toggles atomically

---

## Section 3: Frontend

### `lib/api.ts` additions
- `profileApi.get()`, `profileApi.update(data)`
- `notificationsApi.list(unreadOnly?)`, `notificationsApi.markRead(id)`, `notificationsApi.markAllRead()`
- `settingsApi.get()`, `settingsApi.update(data)`

### `app/dashboard/profile/page.tsx`
- Load on mount → populate display_name, timezone, live stats
- Remove `disabled` from name + timezone inputs
- Save button → `PUT /api/profile/`
- Email stays read-only

### `app/dashboard/notifications/page.tsx`
- Load on mount → replace mock array with real data
- Click card → mark read
- "Mark all read" button
- Unread badge from live data

### `app/dashboard/settings/page.tsx`
- Load on mount → set Switch states from API
- Each Switch `onCheckedChange` → `PUT /api/settings/` immediately
