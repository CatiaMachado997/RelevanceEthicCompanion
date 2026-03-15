# Security Patches, DB Health Check & Notifications Wiring — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix known CVEs in Python and npm dependencies, add a real DB connectivity check to the health endpoint, and wire the notifications page to the live API.

**Architecture:** Three independent tracks executed in sequence. Track 1 bumps pinned versions and verifies tests still pass. Track 2 replaces a hardcoded TODO with a live `SELECT 1` ping. Track 3 adds `notificationsApi` to the frontend client and replaces the mock data page.

**Tech Stack:** Python/pip, Next.js/npm, FastAPI, psycopg3, TypeScript

---

## Critical Files

| File | Change |
|------|--------|
| `backend/requirements.txt` | Bump 5 package versions |
| `backend/main.py` | Replace TODO health check with real DB ping |
| `frontend/package.json` | Bump `next` to 16.1.6 |
| `frontend/lib/api.ts` | Add `notificationsApi` |
| `frontend/app/dashboard/notifications/page.tsx` | Replace mock data with real API calls |

---

## Task 1: Backend security patches

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Bump the five vulnerable packages**

In `backend/requirements.txt`, make these exact changes:

```
# Change:
cryptography==46.0.3        →  cryptography==46.0.5
pyasn1==0.6.1  (if pinned)  →  pyasn1==0.6.2
PyJWT[cryptography]==2.10.1 →  PyJWT[cryptography]==2.12.0
python-multipart==0.0.20    →  python-multipart==0.0.22
black==24.1.1               →  black==24.3.0
```

Note: `pyasn1` may appear as a transitive dependency without a pin. Check the file first — only add/change it if it appears. `pyjwt` may be listed as `python-jose` in the file; check carefully.

**Step 2: Install updated packages**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pip install -r requirements.txt 2>&1 | tail -5
```

Expected: No errors. Packages install or upgrade cleanly.

**Step 3: Run full backend test suite**

```bash
pytest tests/ -v 2>&1 | tail -10
```

Expected: 82 tests pass.

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix: bump cryptography, pyasn1, pyjwt, python-multipart, black to patch CVEs"
```

---

## Task 2: Frontend security patches

**Files:**
- Modify: `frontend/package.json`

**Step 1: Fix auto-resolvable vulnerabilities**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npm audit fix 2>&1
```

Expected: Fixes `ajv`, `flatted`, `minimatch`. May show Next.js still needing manual fix.

**Step 2: Upgrade Next.js to fix critical RCE CVE**

```bash
npm install next@16.1.6 2>&1 | tail -5
```

Expected: `next@16.1.6` installed.

**Step 3: Verify build compiles**

```bash
npx tsc --noEmit 2>&1
```

Expected: No new errors (pre-existing `@types/jest` errors in `__tests__/` are acceptable — they existed before this change).

**Step 4: Verify audit is clean**

```bash
npm audit 2>&1
```

Expected: 0 critical vulnerabilities. Moderate/low from transitive deps acceptable if no fix is available.

**Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "fix: upgrade next to 16.1.6, run npm audit fix to patch CVEs"
```

---

## Task 3: Real DB health check

**Files:**
- Modify: `backend/main.py`

**Step 1: Replace the health endpoint**

Find this in `backend/main.py`:

```python
@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "ethical_safeguard_layer": "active",
        "components": {
            "api": "operational",
            "esl": "active",
            "database": "connected"  # TODO: Add actual health checks
        }
    }
```

Replace with:

```python
@app.get("/health")
async def health():
    """Detailed health check with live DB ping"""
    from utils.db import get_db
    db_status = "unavailable"
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        pass

    overall = "healthy" if db_status == "connected" else "degraded"
    return {
        "status": overall,
        "ethical_safeguard_layer": "active",
        "components": {
            "api": "operational",
            "esl": "active",
            "database": db_status,
        },
    }
```

**Step 2: Verify the app still starts**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
python -c "from main import app; print('OK')" 2>&1
```

Expected: `OK`

**Step 3: Run full backend test suite**

```bash
pytest tests/ -v 2>&1 | tail -10
```

Expected: 82 tests pass.

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add real DB ping to /health endpoint"
```

---

## Task 4: Add `notificationsApi` to frontend API client

**Files:**
- Modify: `frontend/lib/api.ts`

**Step 1: Append notifications API after the `settingsApi` block**

At the very end of `frontend/lib/api.ts`, append:

```typescript
// ==================== Notifications API ====================

export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  read: boolean
  metadata?: Record<string, unknown>
  created_at: string
}

export const notificationsApi = {
  list: async (unreadOnly = false): Promise<{ notifications: Notification[]; unread_count: number }> => {
    const url = unreadOnly ? '/api/notifications/?unread_only=true' : '/api/notifications/'
    const response = await apiRequest<{
      status: string
      notifications: Notification[]
      unread_count: number
    }>(url)
    return { notifications: response.notifications || [], unread_count: response.unread_count || 0 }
  },

  markRead: async (id: string): Promise<void> => {
    await apiRequest(`/api/notifications/${id}/read`, { method: 'PATCH' })
  },

  markAllRead: async (): Promise<void> => {
    await apiRequest('/api/notifications/read-all', { method: 'PATCH' })
  },
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1
```

Expected: No new errors.

**Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add notificationsApi to frontend API client"
```

---

## Task 5: Wire notifications page

**Files:**
- Modify: `frontend/app/dashboard/notifications/page.tsx`

**Step 1: Replace the full file**

```tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { TopHeader } from '@/components/top-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Bell, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react'
import { notificationsApi, Notification } from '@/lib/api'

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

function iconForType(type: string) {
  if (type === 'goal_completed') return CheckCircle2
  if (type.includes('esl') || type.includes('block') || type.includes('shield')) return ShieldAlert
  if (type === 'warning') return AlertTriangle
  return Info
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [markingAll, setMarkingAll] = useState(false)

  const load = useCallback(async () => {
    try {
      const { notifications: data, unread_count } = await notificationsApi.list()
      setNotifications(data)
      setUnreadCount(unread_count)
    } catch (error) {
      console.error('Failed to load notifications:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleMarkRead = async (id: string) => {
    try {
      await notificationsApi.markRead(id)
      await load()
    } catch (error) {
      console.error('Failed to mark notification as read:', error)
    }
  }

  const handleMarkAllRead = async () => {
    setMarkingAll(true)
    try {
      await notificationsApi.markAllRead()
      await load()
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <div className="max-w-4xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Notifications</h1>
                <p className="text-[#525252]">Stay updated with your activity and ESL decisions</p>
              </div>
              <div className="flex items-center gap-3">
                {unreadCount > 0 && (
                  <Badge variant="outline" className="bg-[#171717]/10 text-[#171717] border-[#171717]/20 rounded-full">
                    {unreadCount} unread
                  </Badge>
                )}
                {unreadCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-lg"
                    disabled={markingAll}
                    onClick={handleMarkAllRead}
                  >
                    {markingAll ? 'Marking…' : 'Mark all read'}
                  </Button>
                )}
              </div>
            </div>

            {/* Loading */}
            {loading && (
              <p className="text-sm text-[#525252]">Loading notifications…</p>
            )}

            {/* Notifications List */}
            {!loading && notifications.length > 0 && (
              <div className="space-y-3">
                {notifications.map((notification) => {
                  const Icon = iconForType(notification.type)
                  return (
                    <Card
                      key={notification.id}
                      className={`border-[#E5E5E5] rounded-lg shadow-md transition-all hover:shadow-md cursor-pointer ${
                        !notification.read ? 'bg-[#FAFAFA]' : ''
                      }`}
                      onClick={() => !notification.read && handleMarkRead(notification.id)}
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start gap-4">
                          <div className={`mt-1 ${notification.read ? 'text-[#525252]' : 'text-[#171717]'}`}>
                            <Icon className="h-4 w-4" />
                          </div>
                          <div className="flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              <CardTitle className="text-base text-[#171717]">
                                {notification.title}
                              </CardTitle>
                              {!notification.read && (
                                <div className="h-2 w-2 rounded-full bg-[#171717]" />
                              )}
                            </div>
                            <p className="text-sm text-[#525252]">{notification.message}</p>
                            <p className="text-xs text-[#A3A3A3]">{timeAgo(notification.created_at)}</p>
                          </div>
                        </div>
                      </CardHeader>
                    </Card>
                  )
                })}
              </div>
            )}

            {/* Empty state */}
            {!loading && notifications.length === 0 && (
              <Card className="border-[#E5E5E5] rounded-lg shadow-md p-12 text-center">
                <Bell className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                <h3 className="font-semibold mt-4 text-lg text-[#171717]">All caught up!</h3>
                <p className="text-[#525252] mt-2">You have no notifications</p>
              </Card>
            )}
          </div>
        </div>
      </main>
    </>
  )
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1
```

Expected: No new errors.

**Step 3: Commit**

```bash
git add frontend/app/dashboard/notifications/page.tsx
git commit -m "feat: wire notifications page to live API with mark-read and mark-all-read"
```

---

## Task 6: Final verification and push

**Step 1: Run full backend test suite**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/backend
source venv/bin/activate
pytest tests/ -v 2>&1 | tail -10
```

Expected: 82 tests pass.

**Step 2: Push**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion
git push origin master 2>&1
```
