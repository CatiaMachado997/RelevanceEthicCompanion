# Security Patches, DB Health Check & Notifications Wiring — Design

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Three independent tracks — security CVE patches, real DB health check, notifications page wiring

---

## Track 1: Security Patches

### Backend (Python)

Bump the following pinned versions in `backend/requirements.txt` (patch-only, no API changes):

| Package | From | To | CVEs fixed |
|---------|------|----|------------|
| `cryptography` | 46.0.3 | 46.0.5 | CVE-2026-26007 |
| `pyasn1` | 0.6.1 | 0.6.2 | CVE-2026-23490 |
| `pyjwt[cryptography]` | 2.10.1 | 2.12.0 | CVE-2026-32597 |
| `python-multipart` | 0.0.20 | 0.0.22 | CVE-2026-24486 |
| `black` | 24.1.1 | 24.3.0 | PYSEC-2024-48 |

**Skipped (out of scope):**
- `langchain*` — fixes require 0.2.x which has breaking API changes
- `ecdsa` — no fix version available
- `protobuf` — fix requires major version bump (4→5)

After bumping, run `pip install -r requirements.txt` and full test suite.

### Frontend (npm)

Run `npm audit fix` to resolve `ajv`, `flatted`, `minimatch` (auto-resolvable).
Upgrade `next` from 16.0.3 → 16.1.6 (minor bump within v16, fixes critical RCE: GHSA-9qr9-h5gf-34mp, and 4 other CVEs).

After upgrading, verify `npm run build` compiles without errors.

---

## Track 2: Real DB Health Check

Replace the hardcoded `"database": "connected"` TODO in `GET /health` (`backend/main.py`) with a live `SELECT 1` ping.

Behaviour:
- On success: `"database": "connected"`
- On failure: `"database": "unavailable"` (never raises 500 — health endpoints must always respond)
- Overall `"status"` becomes `"degraded"` if DB is unavailable, otherwise `"healthy"`

No new dependencies — uses existing `get_db()` / `psycopg`.

---

## Track 3: Notifications Page Wiring

Replace the hardcoded mock array in `frontend/app/dashboard/notifications/page.tsx` with real API calls.

**Add `notificationsApi` to `frontend/lib/api.ts`:**
```ts
notificationsApi.list(unreadOnly?: boolean)   // GET /api/notifications/
notificationsApi.markRead(id: string)          // PATCH /api/notifications/{id}/read
notificationsApi.markAllRead()                 // PATCH /api/notifications/read-all
```

**Page behaviour:**
- On mount: `GET /api/notifications/` → populate list, show real unread count in badge
- Click a notification card → `PATCH /api/notifications/{id}/read` → re-fetch list
- "Mark all read" button → `PATCH /api/notifications/read-all` → re-fetch list
- Timestamps: format real ISO timestamps as relative time (e.g. "2 hours ago") using a simple helper — no new library
- Icon mapping: `goal_completed` → CheckCircle2, `esl_block`/ESL-related → ShieldAlert, default → Info
- Loading state while fetching, empty state when list is empty

---

## Out of Scope

- langchain, ecdsa, protobuf upgrades
- Push notification infrastructure
- Notification preferences beyond what's in settings
