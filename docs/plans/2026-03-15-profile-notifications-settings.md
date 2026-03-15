# Profile, Notifications & Settings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up three stubbed dashboard pages (profile, notifications, settings) to real backend data.

**Architecture:** Three new FastAPI route files + one DB migration. Notifications are generated inline when goals complete or ESL vetoes. Settings are upserted on every toggle change. Profile stats are computed live from existing tables.

**Tech Stack:** FastAPI (Python), PostgreSQL via `utils.db.get_db`, Next.js App Router, TypeScript, Tailwind. Tests use `fastapi.testclient.TestClient` with mocked DB and auth dependencies (see `tests/test_values_routes.py` for the pattern).

---

### Task 1: DB Migration

**Files:**
- Create: `backend/database/migration_profile_notifications_settings.sql`

**Step 1: Write the SQL migration**

```sql
-- Add profile fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Notifications
CREATE TABLE IF NOT EXISTS user_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type VARCHAR(50) NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_user_notifications_user_created
  ON user_notifications (user_id, created_at DESC);

-- Settings
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

**Step 2: Apply the migration**

```bash
cd backend
source venv/bin/activate
python -c "
from utils.db import get_db
sql = open('database/migration_profile_notifications_settings.sql').read()
with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
print('Migration applied')
"
```

Expected: `Migration applied`

**Step 3: Commit**

```bash
git add backend/database/migration_profile_notifications_settings.sql
git commit -m "feat: add migration for profile fields, notifications, settings tables"
```

---

### Task 2: Profile Backend

**Files:**
- Create: `backend/routes/profile.py`
- Create: `backend/tests/test_profile_routes.py`
- Modify: `backend/main.py` (register router)

**Step 1: Write the failing tests**

Create `backend/tests/test_profile_routes.py`:

```python
"""Profile Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_db_mock(fetchone_result=None, fetchall_result=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def make_app():
    from routes.profile import router as profile_router
    app = FastAPI()
    app.include_router(profile_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


SAMPLE_USER_ROW = {
    "id": TEST_USER_ID,
    "email": "test@example.com",
    "display_name": "Test User",
    "timezone": "UTC",
}

SAMPLE_STATS = {
    "values_count": 5,
    "goals_count": 3,
    "approval_rate": 0.87,
}


def test_get_profile_returns_user_data(client):
    """GET /api/profile/ → user data + stats."""
    mock_conn, mock_cursor = make_db_mock(fetchone_result=SAMPLE_USER_ROW)
    mock_cursor.fetchall.return_value = []

    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.get("/api/profile/")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"
    assert "stats" in data


def test_update_profile_saves_name_and_timezone(client):
    """PUT /api/profile/ → 200 with updated data."""
    updated_row = {**SAMPLE_USER_ROW, "display_name": "New Name", "timezone": "America/New_York"}
    mock_conn, _ = make_db_mock(fetchone_result=updated_row)

    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.put(
            "/api/profile/",
            json={"display_name": "New Name", "timezone": "America/New_York"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "New Name"
    assert data["timezone"] == "America/New_York"


def test_update_profile_requires_at_least_one_field(client):
    """PUT /api/profile/ with empty body → 400."""
    mock_conn, _ = make_db_mock()
    with patch("routes.profile.get_db", return_value=mock_conn):
        response = client.put("/api/profile/", json={})
    assert response.status_code == 400
```

**Step 2: Run to confirm they fail**

```bash
cd backend && source venv/bin/activate
pytest tests/test_profile_routes.py -v
```

Expected: `ImportError` or `3 failed` (route doesn't exist yet)

**Step 3: Implement `backend/routes/profile.py`**

```python
"""Profile API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from utils.db import get_db
from utils.serialization import serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    timezone: Optional[str] = None


@router.get("/", response_model=dict)
async def get_profile(user_id: str = Depends(get_current_read_user_id)):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # User data
                cur.execute(
                    "SELECT id, email, display_name, timezone FROM users WHERE id = %s",
                    (str(user_id),),
                )
                user = cur.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")

                # Live stats
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM user_values WHERE user_id = %s AND active = TRUE",
                    (str(user_id),),
                )
                values_count = (cur.fetchone() or {}).get("cnt", 0)

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM goals WHERE user_id = %s AND status = 'active'",
                    (str(user_id),),
                )
                goals_count = (cur.fetchone() or {}).get("cnt", 0)

                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE decision_status = 'APPROVED') AS approved,
                      COUNT(*) AS total
                    FROM esl_audit_log WHERE user_id = %s
                    """,
                    (str(user_id),),
                )
                row = cur.fetchone() or {}
                total = row.get("total") or 0
                approved = row.get("approved") or 0
                approval_rate = round(approved / total, 2) if total > 0 else 0.0

        result = serialize_row(user)
        result["stats"] = {
            "values_count": values_count,
            "goals_count": goals_count,
            "approval_rate": approval_rate,
        }
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


@router.put("/", response_model=dict)
async def update_profile(
    request: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
):
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params = list(updates.values()) + [str(user_id)]

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE users SET {set_clause} WHERE id = %s RETURNING id, email, display_name, timezone",
                    tuple(params),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="User not found")

        return serialize_row(updated)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")
```

**Step 4: Register router in `backend/main.py`**

In `main.py`, find the imports block:
```python
from routes import auth, values, chat, goals, transparency, relevance, data_sources
```
Change to:
```python
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, settings
```

And add after existing `app.include_router` calls:
```python
app.include_router(profile.router)
app.include_router(notifications.router)
app.include_router(settings.router)
```

(Add all three now — `notifications` and `settings` route files will exist after Tasks 3 & 4.)

**Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_profile_routes.py -v
```

Expected: `3 passed`

**Step 6: Commit**

```bash
git add backend/routes/profile.py backend/tests/test_profile_routes.py backend/main.py
git commit -m "feat: add profile GET/PUT routes with live stats"
```

---

### Task 3: Notifications Backend

**Files:**
- Create: `backend/routes/notifications.py`
- Create: `backend/tests/test_notifications_routes.py`
- Modify: `backend/routes/goals.py` (insert notification after complete_goal succeeds)

**Step 1: Write the failing tests**

Create `backend/tests/test_notifications_routes.py`:

```python
"""Notifications Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_db_mock(fetchone_result=None, fetchall_result=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def make_app():
    from routes.notifications import router as notif_router
    app = FastAPI()
    app.include_router(notif_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


SAMPLE_NOTIF = {
    "id": "notif-001",
    "user_id": TEST_USER_ID,
    "type": "goal_completed",
    "title": "Goal Completed",
    "message": "You completed Launch MVP",
    "read": False,
    "created_at": datetime(2026, 3, 15, tzinfo=UTC),
    "metadata": {},
}


def test_list_notifications_returns_data(client):
    """GET /api/notifications/ → list of notifications."""
    mock_conn, _ = make_db_mock(fetchall_result=[SAMPLE_NOTIF])
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["notifications"][0]["type"] == "goal_completed"


def test_list_notifications_unread_filter(client):
    """GET /api/notifications/?unread_only=true → only unread."""
    mock_conn, mock_cursor = make_db_mock(fetchall_result=[SAMPLE_NOTIF])
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.get("/api/notifications/?unread_only=true")
    assert response.status_code == 200
    # Verify the query was called (cursor.execute called)
    mock_cursor.execute.assert_called()


def test_mark_one_read(client):
    """PATCH /api/notifications/{id}/read → marks read."""
    mock_conn, _ = make_db_mock(fetchone_result={**SAMPLE_NOTIF, "read": True})
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.patch("/api/notifications/notif-001/read")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_mark_all_read(client):
    """PATCH /api/notifications/read-all → 200."""
    mock_conn, _ = make_db_mock()
    with patch("routes.notifications.get_db", return_value=mock_conn):
        response = client.patch("/api/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

**Step 2: Run to confirm they fail**

```bash
pytest tests/test_notifications_routes.py -v
```

Expected: `ImportError` or `4 failed`

**Step 3: Implement `backend/routes/notifications.py`**

```python
"""Notifications API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from utils.db import get_db
from utils.serialization import serialize_rows, serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def create_notification(conn, user_id: str, type: str, title: str, message: str, metadata: dict = None):
    """Helper — insert a notification row. Call inside an existing DB connection."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_notifications (user_id, type, title, message, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(user_id), type, title, message, metadata or {}),
        )


@router.get("/", response_model=dict)
async def list_notifications(
    unread_only: bool = False,
    user_id: str = Depends(get_current_read_user_id),
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM user_notifications WHERE user_id = %s"
                params = [str(user_id)]
                if unread_only:
                    query += " AND read = FALSE"
                query += " ORDER BY created_at DESC LIMIT 50"
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        notifications = serialize_rows(rows)
        return {
            "status": "success",
            "count": len(notifications),
            "unread_count": sum(1 for n in notifications if not n.get("read")),
            "notifications": notifications,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")


@router.patch("/read-all", response_model=dict)
async def mark_all_read(user_id: str = Depends(get_current_user_id)):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_notifications SET read = TRUE WHERE user_id = %s AND read = FALSE",
                    (str(user_id),),
                )
        return {"status": "success", "message": "All notifications marked as read"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating notifications: {str(e)}")


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_one_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_notifications SET read = TRUE WHERE id = %s AND user_id = %s RETURNING *",
                    (notification_id, str(user_id)),
                )
                updated = cur.fetchone()

        if not updated:
            raise HTTPException(status_code=404, detail="Notification not found")

        return {"status": "success", "data": serialize_row(updated)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating notification: {str(e)}")
```

**Step 4: Add notification insert to `complete_goal` in `backend/routes/goals.py`**

Find the success return in `complete_goal` (after `updated_goal = cur.fetchone()`):

```python
# BEFORE (existing):
        if not updated_goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        return {
            "status": "success",
            "message": "Goal completed! 🎉",
            "data": serialize_row(updated_goal)
        }
```

Change to:

```python
        if not updated_goal:
            raise HTTPException(status_code=404, detail="Goal not found")

        # Insert notification
        from routes.notifications import create_notification
        goal_title = updated_goal.get("title", goal_id)
        with get_db() as notif_conn:
            create_notification(
                notif_conn, user_id,
                type="goal_completed",
                title="Goal Completed",
                message=f'You completed "{goal_title}"',
            )

        return {
            "status": "success",
            "message": "Goal completed! 🎉",
            "data": serialize_row(updated_goal)
        }
```

**Step 5: Run tests**

```bash
pytest tests/test_notifications_routes.py -v
```

Expected: `4 passed`

**Step 6: Run full suite to confirm nothing broke**

```bash
pytest tests/ -q
```

Expected: all passing

**Step 7: Commit**

```bash
git add backend/routes/notifications.py backend/tests/test_notifications_routes.py backend/routes/goals.py
git commit -m "feat: add notifications routes; insert goal_completed notification on complete_goal"
```

---

### Task 4: Settings Backend

**Files:**
- Create: `backend/routes/settings.py`
- Create: `backend/tests/test_settings_routes.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_settings_routes.py`:

```python
"""Settings Route Integration Tests — TDD first."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest

from utils.supabase_auth import get_current_user_id, get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def make_db_mock(fetchone_result=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def make_app():
    from routes.settings import router as settings_router
    app = FastAPI()
    app.include_router(settings_router)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return app


@pytest.fixture
def client():
    return TestClient(make_app())


SAMPLE_SETTINGS = {
    "user_id": TEST_USER_ID,
    "email_notifications": False,
    "push_notifications": False,
    "esl_alerts": True,
    "share_analytics": False,
    "pii_protection": True,
}


def test_get_settings_returns_defaults(client):
    """GET /api/settings/ → returns settings row."""
    mock_conn, _ = make_db_mock(fetchone_result=SAMPLE_SETTINGS)
    with patch("routes.settings.get_db", return_value=mock_conn):
        response = client.get("/api/settings/")
    assert response.status_code == 200
    data = response.json()
    assert data["esl_alerts"] is True
    assert data["pii_protection"] is True


def test_update_settings_saves_toggles(client):
    """PUT /api/settings/ → 200 with updated settings."""
    updated = {**SAMPLE_SETTINGS, "email_notifications": True}
    mock_conn, _ = make_db_mock(fetchone_result=updated)
    with patch("routes.settings.get_db", return_value=mock_conn):
        response = client.put(
            "/api/settings/",
            json={"email_notifications": True, "push_notifications": False,
                  "esl_alerts": True, "share_analytics": False, "pii_protection": True},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["email_notifications"] is True
```

**Step 2: Run to confirm they fail**

```bash
pytest tests/test_settings_routes.py -v
```

Expected: `ImportError` or `2 failed`

**Step 3: Implement `backend/routes/settings.py`**

```python
"""Settings API Routes"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, UTC

from utils.db import get_db
from utils.serialization import serialize_row
from utils.supabase_auth import get_current_user_id, get_current_read_user_id

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class UpdateSettingsRequest(BaseModel):
    email_notifications: bool
    push_notifications: bool
    esl_alerts: bool
    share_analytics: bool
    pii_protection: bool


@router.get("/", response_model=dict)
async def get_settings(user_id: str = Depends(get_current_read_user_id)):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Upsert default row on first access
                cur.execute(
                    """
                    INSERT INTO user_settings (user_id)
                    VALUES (%s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (str(user_id),),
                )
                cur.execute(
                    "SELECT * FROM user_settings WHERE user_id = %s",
                    (str(user_id),),
                )
                row = cur.fetchone()

        return serialize_row(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching settings: {str(e)}")


@router.put("/", response_model=dict)
async def update_settings(
    request: UpdateSettingsRequest,
    user_id: str = Depends(get_current_user_id),
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_settings
                      (user_id, email_notifications, push_notifications, esl_alerts,
                       share_analytics, pii_protection, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                      email_notifications = EXCLUDED.email_notifications,
                      push_notifications  = EXCLUDED.push_notifications,
                      esl_alerts          = EXCLUDED.esl_alerts,
                      share_analytics     = EXCLUDED.share_analytics,
                      pii_protection      = EXCLUDED.pii_protection,
                      updated_at          = EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (
                        str(user_id),
                        request.email_notifications,
                        request.push_notifications,
                        request.esl_alerts,
                        request.share_analytics,
                        request.pii_protection,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                updated = cur.fetchone()

        return serialize_row(updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")
```

**Step 4: Run tests**

```bash
pytest tests/test_settings_routes.py -v
```

Expected: `2 passed`

**Step 5: Run full suite**

```bash
pytest tests/ -q
```

Expected: all passing

**Step 6: Commit**

```bash
git add backend/routes/settings.py backend/tests/test_settings_routes.py
git commit -m "feat: add settings GET/PUT routes with upsert-on-first-access"
```

---

### Task 5: Frontend API Functions

**Files:**
- Modify: `frontend/lib/api.ts`

**Step 1: Add the three API objects before the `const api = {` block**

```typescript
// ---- Profile ----

export interface ProfileStats {
  values_count: number
  goals_count: number
  approval_rate: number
}

export interface ProfileData {
  id: string
  email: string
  display_name: string | null
  timezone: string
  stats: ProfileStats
}

export const profileApi = {
  get: () => apiRequest<ProfileData>('/api/profile/'),
  update: (data: { display_name?: string; timezone?: string }) =>
    apiRequest<ProfileData>('/api/profile/', { method: 'PUT', body: JSON.stringify(data) }),
}

// ---- Notifications ----

export interface Notification {
  id: string
  type: string
  title: string
  message: string
  read: boolean
  created_at: string
  metadata: Record<string, unknown>
}

export const notificationsApi = {
  list: (unreadOnly = false) =>
    apiRequest<{ count: number; unread_count: number; notifications: Notification[] }>(
      `/api/notifications/${unreadOnly ? '?unread_only=true' : ''}`
    ),
  markRead: (id: string) =>
    apiRequest<{ status: string }>(`/api/notifications/${id}/read`, { method: 'PATCH' }),
  markAllRead: () =>
    apiRequest<{ status: string }>('/api/notifications/read-all', { method: 'PATCH' }),
}

// ---- Settings ----

export interface UserSettings {
  email_notifications: boolean
  push_notifications: boolean
  esl_alerts: boolean
  share_analytics: boolean
  pii_protection: boolean
}

export const settingsApi = {
  get: () => apiRequest<UserSettings>('/api/settings/'),
  update: (data: UserSettings) =>
    apiRequest<UserSettings>('/api/settings/', { method: 'PUT', body: JSON.stringify(data) }),
}
```

**Step 2: Add to the default export object**

Find:
```typescript
const api = {
  values: valuesApi,
  chat: chatApi,
  goals: goalsApi,
  transparency: transparencyApi,
  relevance: relevanceApi,
  dataSources: dataSourcesApi,
};
```

Change to:
```typescript
const api = {
  values: valuesApi,
  chat: chatApi,
  goals: goalsApi,
  transparency: transparencyApi,
  relevance: relevanceApi,
  dataSources: dataSourcesApi,
  profile: profileApi,
  notifications: notificationsApi,
  settings: settingsApi,
};
```

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|✓"
```

Expected: build succeeds with no errors

**Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add profileApi, notificationsApi, settingsApi to lib/api.ts"
```

---

### Task 6: Wire Up Profile Page

**Files:**
- Modify: `frontend/app/dashboard/profile/page.tsx`

**Step 1: Replace the page with a wired-up version**

Full replacement of `frontend/app/dashboard/profile/page.tsx`:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useAuth } from '@/hooks/useAuth'
import { User, Calendar, Shield } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { profileApi, ProfileData } from '@/lib/api'

export default function ProfilePage() {
  const { user } = useAuth()
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [timezone, setTimezone] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    profileApi.get().then((data) => {
      setProfile(data)
      setDisplayName(data.display_name ?? '')
      setTimezone(data.timezone ?? 'UTC')
    }).catch(console.error)
  }, [])

  const getInitials = (email: string) =>
    email.split('@')[0].substring(0, 2).toUpperCase()

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await profileApi.update({ display_name: displayName, timezone })
      setProfile(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setDisplayName(profile?.display_name ?? '')
    setTimezone(profile?.timezone ?? 'UTC')
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">Profile</h1>
              <p className="text-[#6b6b6b]">Manage your personal information</p>
            </div>

            {/* Profile Card */}
            <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <Avatar className="h-20 w-20">
                    <AvatarFallback className="bg-[#0a0a0a] text-white text-2xl font-semibold">
                      {user?.email ? getInitials(user.email) : 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <CardTitle className="text-[#0a0a0a]">
                      {displayName || user?.email?.split('@')[0] || 'User'}
                    </CardTitle>
                    <CardDescription className="text-[#6b6b6b]">{user?.email}</CardDescription>
                    <div className="flex gap-2 mt-2">
                      <Badge variant="outline" className="rounded-full text-xs">
                        <Shield className="h-3 w-3 mr-1" />
                        Protected by ESL
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardHeader>
            </Card>

            {/* Personal Information */}
            <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-[#0a0a0a]" />
                  <CardTitle className="text-[#0a0a0a]">Personal Information</CardTitle>
                </div>
                <CardDescription className="text-[#6b6b6b]">Update your personal details</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="name" className="text-[#0a0a0a]">Display Name</Label>
                  <Input
                    id="name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Enter your name"
                    className="rounded-xl"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="email" className="text-[#0a0a0a]">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={user?.email || ''}
                    className="rounded-xl"
                    disabled
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="timezone" className="text-[#0a0a0a]">Timezone</Label>
                  <Input
                    id="timezone"
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    placeholder="UTC"
                    className="rounded-xl"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Account Stats */}
            {profile?.stats && (
              <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-[#0a0a0a]" />
                    <CardTitle className="text-[#0a0a0a]">Account Statistics</CardTitle>
                  </div>
                  <CardDescription className="text-[#6b6b6b]">Your activity summary</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-4 rounded-xl bg-[#fafafa]">
                      <div className="text-2xl font-bold text-[#0a0a0a]">{profile.stats.values_count}</div>
                      <div className="text-sm text-[#6b6b6b] mt-1">Values Set</div>
                    </div>
                    <div className="text-center p-4 rounded-xl bg-[#fafafa]">
                      <div className="text-2xl font-bold text-[#0a0a0a]">{profile.stats.goals_count}</div>
                      <div className="text-sm text-[#6b6b6b] mt-1">Active Goals</div>
                    </div>
                    <div className="text-center p-4 rounded-xl bg-[#fafafa]">
                      <div className="text-2xl font-bold text-[#0a0a0a]">
                        {(profile.stats.approval_rate * 100).toFixed(0)}%
                      </div>
                      <div className="text-sm text-[#6b6b6b] mt-1">ESL Approval Rate</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="flex gap-3">
              <Button
                onClick={handleSave}
                disabled={saving}
                className="rounded-full bg-[#0a0a0a] hover:bg-[#333333] text-white"
              >
                {saving ? 'Saving…' : saved ? 'Saved!' : 'Save Changes'}
              </Button>
              <Button variant="outline" onClick={handleCancel} className="rounded-full">
                Cancel
              </Button>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|✓" | head -5
```

Expected: no errors

**Step 3: Commit**

```bash
git add frontend/app/dashboard/profile/page.tsx
git commit -m "feat: wire up profile page to real API with live stats"
```

---

### Task 7: Wire Up Notifications Page

**Files:**
- Modify: `frontend/app/dashboard/notifications/page.tsx`

**Step 1: Replace the page**

Full replacement of `frontend/app/dashboard/notifications/page.tsx`:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Bell, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react'
import { notificationsApi, Notification } from '@/lib/api'

const ICON_MAP: Record<string, React.ElementType> = {
  esl_block: ShieldAlert,
  goal_completed: CheckCircle2,
  warning: AlertTriangle,
  info: Info,
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const loadNotifications = async () => {
    try {
      const data = await notificationsApi.list()
      setNotifications(data.notifications)
      setUnreadCount(data.unread_count)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadNotifications() }, [])

  const handleMarkRead = async (id: string) => {
    await notificationsApi.markRead(id)
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    )
    setUnreadCount((c) => Math.max(0, c - 1))
  }

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    setUnreadCount(0)
  }

  const formatTime = (ts: string) =>
    new Date(ts).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
    })

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold tracking-tight text-[#0a0a0a]">Notifications</h1>
                <p className="text-[#6b6b6b]">Stay updated with your activity and ESL decisions</p>
              </div>
              <div className="flex items-center gap-3">
                {unreadCount > 0 && (
                  <Badge variant="outline" className="rounded-full">
                    {unreadCount} unread
                  </Badge>
                )}
                {unreadCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleMarkAllRead}
                    className="rounded-full text-xs"
                  >
                    Mark all read
                  </Button>
                )}
              </div>
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[rgba(0,0,0,0.08)] border-t-[#0a0a0a]" />
              </div>
            ) : notifications.length === 0 ? (
              <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] p-12 text-center">
                <Bell className="h-10 w-10 mx-auto text-[#9e9e9e]" />
                <h3 className="font-semibold mt-4 text-lg text-[#0a0a0a]">All caught up!</h3>
                <p className="text-[#6b6b6b] mt-2">No notifications yet</p>
              </Card>
            ) : (
              <div className="space-y-3">
                {notifications.map((n) => {
                  const Icon = ICON_MAP[n.type] ?? Info
                  return (
                    <Card
                      key={n.id}
                      onClick={() => !n.read && handleMarkRead(n.id)}
                      className={`rounded-2xl border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)] transition-all cursor-pointer hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] ${
                        !n.read ? 'bg-[#fafafa]' : 'bg-white'
                      }`}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start gap-4">
                          <div className="mt-1 text-[#6b6b6b]">
                            <Icon className="h-4 w-4" />
                          </div>
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <CardTitle className="text-base text-[#0a0a0a]">{n.title}</CardTitle>
                              {!n.read && <div className="h-2 w-2 rounded-full bg-[#0a0a0a]" />}
                            </div>
                            <p className="text-sm text-[#6b6b6b]">{n.message}</p>
                            <p className="text-xs text-[#9e9e9e]">{formatTime(n.created_at)}</p>
                          </div>
                        </div>
                      </CardHeader>
                    </Card>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|✓" | head -5
```

Expected: no errors

**Step 3: Commit**

```bash
git add frontend/app/dashboard/notifications/page.tsx
git commit -m "feat: wire up notifications page to real API with mark-as-read"
```

---

### Task 8: Wire Up Settings Page

**Files:**
- Modify: `frontend/app/dashboard/settings/page.tsx`

**Step 1: Add state management to settings toggles**

Find the top of `SettingsPage` component and add after existing state:

```tsx
const [settings, setSettings] = useState({
  email_notifications: false,
  push_notifications: false,
  esl_alerts: true,
  share_analytics: false,
  pii_protection: true,
})
const [settingsLoading, setSettingsLoading] = useState(true)
```

Add import at top:
```tsx
import { settingsApi, UserSettings } from '@/lib/api'
```

Add inside the existing `useEffect(() => { loadDataSources() }, [])` — add a second `useEffect`:
```tsx
useEffect(() => {
  settingsApi.get()
    .then((data) => setSettings(data))
    .catch(console.error)
    .finally(() => setSettingsLoading(false))
}, [])
```

Add a toggle handler:
```tsx
const handleSettingChange = async (key: keyof UserSettings, value: boolean) => {
  const updated = { ...settings, [key]: value }
  setSettings(updated)
  try {
    await settingsApi.update(updated)
  } catch (e) {
    console.error(e)
    setSettings(settings) // revert on error
  }
}
```

**Step 2: Wire the Switches**

Replace the Notifications section switches:
```tsx
<Switch
  checked={settings.email_notifications}
  onCheckedChange={(v) => handleSettingChange('email_notifications', v)}
/>
...
<Switch
  checked={settings.push_notifications}
  onCheckedChange={(v) => handleSettingChange('push_notifications', v)}
/>
...
<Switch
  checked={settings.esl_alerts}
  onCheckedChange={(v) => handleSettingChange('esl_alerts', v)}
/>
```

Replace Privacy section switches:
```tsx
<Switch
  checked={settings.share_analytics}
  onCheckedChange={(v) => handleSettingChange('share_analytics', v)}
/>
...
<Switch
  checked={settings.pii_protection}
  onCheckedChange={(v) => handleSettingChange('pii_protection', v)}
/>
```

**Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|✓" | head -5
```

Expected: no errors

**Step 4: Run all backend tests one final time**

```bash
cd backend && source venv/bin/activate && pytest tests/ -q
```

Expected: all passing

**Step 5: Commit**

```bash
git add frontend/app/dashboard/settings/page.tsx
git commit -m "feat: wire up settings toggles to real API with immediate persistence"
```
