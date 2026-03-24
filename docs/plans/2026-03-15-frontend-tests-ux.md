# Frontend Component Tests & UX Polish — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix a broken dashboard test, add component tests for settings and notifications pages, and add inline error display to the notifications page.

**Architecture:** Four independent tasks. Tasks 1–3 are pure test work (no production code changes). Task 4 adds an `error` state to the notifications page component. All tests use `jest.mock('../lib/api')`, `render` + `screen` from `@testing-library/react`, and `userEvent` for interactions.

**Tech Stack:** Jest, React Testing Library, TypeScript, Next.js App Router

---

## Task 1: Fix `__tests__/dashboard.test.tsx`

**Files:**
- Modify: `frontend/__tests__/dashboard.test.tsx`

**Background:**

The test at line 29 asserts `screen.getByText('Loading your dashboard...')` but the dashboard component (`frontend/app/dashboard/page.tsx`) no longer renders that string — it replaced it with `<Skeleton>` components. The test also mocks only `transparencyApi` but the component now calls `goalsApi`, `valuesApi`, `transparencyApi.report()`, and `transparencyApi.logs()`.

**Step 1: Update the mock to cover all APIs used**

Replace the existing `jest.mock('../lib/api', ...)` block (lines 6–11) with:

```typescript
jest.mock('../lib/api', () => ({
  transparencyApi: {
    insights: jest.fn(),
    report: jest.fn(),
    logs: jest.fn(),
  },
  goalsApi: {
    list: jest.fn(),
  },
  valuesApi: {
    list: jest.fn(),
  },
}))
```

**Step 2: Update `beforeEach` mock setup**

Replace the existing `beforeEach` (lines 15–25) with:

```typescript
beforeEach(() => {
  (transparencyApi.insights as jest.Mock).mockClear()
  ;(transparencyApi.report as jest.Mock).mockResolvedValue({
    total_decisions: 100,
    approval_rate: 0.95,
    vetoed_count: 5,
    modified_count: 10,
  })
  ;(transparencyApi.logs as jest.Mock).mockResolvedValue({ logs: [] })
  ;(goalsApi.list as jest.Mock).mockResolvedValue({ goals: [] })
  ;(valuesApi.list as jest.Mock).mockResolvedValue({ values: [] })
})
```

**Step 3: Replace the broken loading-state test**

The test at line 27–30:
```typescript
it('shows loading state initially', () => {
  render(<DashboardPage />);
  expect(screen.getByText('Loading your dashboard...')).toBeInTheDocument();
});
```

Replace with a test that matches how the component actually signals loading — it still renders the greeting/date area immediately, and uses `Skeleton` during load. The cleanest assertion is that the stat values are not yet shown (they're replaced by Skeletons):

```typescript
it('renders without crashing', () => {
  render(<DashboardPage />)
  // Greeting card always renders immediately
  expect(screen.getByText('Active Goals')).toBeInTheDocument()
})
```

**Step 4: Update imports to add `goalsApi` and `valuesApi`**

Line 3 currently imports only `transparencyApi`. Add the new APIs:

```typescript
import { transparencyApi, goalsApi, valuesApi } from '../lib/api'
```

**Step 5: Run the tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx jest __tests__/dashboard.test.tsx --no-coverage 2>&1
```

Expected: 3 tests pass.

**Step 6: Commit**

```bash
git add frontend/__tests__/dashboard.test.tsx
git commit -m "fix: update dashboard test to match current component (Skeleton loading, expanded API mocks)"
```

---

## Task 2: New test — `__tests__/settings.test.tsx`

**Files:**
- Create: `frontend/__tests__/settings.test.tsx`

**Background:**

The settings page (`frontend/app/dashboard/settings/page.tsx`) has:
- `useEffect` → `settingsApi.get()` on mount, populates switches
- Five toggle switches (`email_notifications`, `push_notifications`, `esl_alerts`, `share_analytics`, `pii_protection`)
- A "Save Settings" button, disabled until a switch is toggled
- On save: calls `settingsApi.update()` with all five boolean values

**Step 1: Write the test file**

Create `frontend/__tests__/settings.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsPage from '../app/dashboard/settings/page'
import { settingsApi, dataSourcesApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  settingsApi: {
    get: jest.fn(),
    update: jest.fn(),
  },
  dataSourcesApi: {
    list: jest.fn(),
    getAuthUrl: jest.fn(),
    disconnect: jest.fn(),
    sync: jest.fn(),
  },
}))

const DEFAULT_SETTINGS = {
  email_notifications: false,
  push_notifications: false,
  esl_alerts: true,
  share_analytics: false,
  pii_protection: true,
}

beforeEach(() => {
  ;(settingsApi.get as jest.Mock).mockResolvedValue(DEFAULT_SETTINGS)
  ;(settingsApi.update as jest.Mock).mockResolvedValue(DEFAULT_SETTINGS)
  ;(dataSourcesApi.list as jest.Mock).mockResolvedValue({ sources: [] })
})

test('test_settings_loads_on_mount', async () => {
  render(<SettingsPage />)
  await waitFor(() => {
    expect(settingsApi.get).toHaveBeenCalledTimes(1)
  })
})

test('test_save_button_disabled_when_clean', async () => {
  render(<SettingsPage />)
  // Wait for settings to load
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())
  const saveButton = screen.getByRole('button', { name: /save settings/i })
  expect(saveButton).toBeDisabled()
})

test('test_save_button_enabled_after_toggle', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  // Toggle the Email Notifications switch (currently off → on)
  const emailSwitch = screen.getByRole('switch', { name: /email notifications/i })
  await userEvent.click(emailSwitch)

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  expect(saveButton).not.toBeDisabled()
})

test('test_save_calls_api', async () => {
  render(<SettingsPage />)
  await waitFor(() => expect(settingsApi.get).toHaveBeenCalled())

  // Make a change so Save is enabled
  const emailSwitch = screen.getByRole('switch', { name: /email notifications/i })
  await userEvent.click(emailSwitch)

  const saveButton = screen.getByRole('button', { name: /save settings/i })
  await userEvent.click(saveButton)

  await waitFor(() => {
    expect(settingsApi.update).toHaveBeenCalledWith(
      expect.objectContaining({ email_notifications: true })
    )
  })
})
```

**Step 2: Run the tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx jest __tests__/settings.test.tsx --no-coverage 2>&1
```

Expected: 4 tests pass.

**Step 3: Commit**

```bash
git add frontend/__tests__/settings.test.tsx
git commit -m "test: add settings component tests (loads, save button state, API call)"
```

---

## Task 3: New test — `__tests__/notifications.test.tsx`

**Files:**
- Create: `frontend/__tests__/notifications.test.tsx`

**Background:**

The notifications page (`frontend/app/dashboard/notifications/page.tsx`) has:
- `useEffect` → `notificationsApi.list()` on mount, populates `notifications` and `unreadCount`
- "Mark all read" button only rendered when `unreadCount > 0`
- Clicking an unread notification card calls `notificationsApi.markRead(id)`

**Step 1: Write the test file**

Create `frontend/__tests__/notifications.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NotificationsPage from '../app/dashboard/notifications/page'
import { notificationsApi } from '../lib/api'

jest.mock('../lib/api', () => ({
  notificationsApi: {
    list: jest.fn(),
    markRead: jest.fn(),
    markAllRead: jest.fn(),
  },
}))

const MOCK_NOTIFICATION = {
  id: 'notif-1',
  user_id: 'user-1',
  type: 'goal_completed',
  title: 'Goal achieved!',
  message: 'You completed your first goal.',
  read: false,
  created_at: new Date().toISOString(),
}

beforeEach(() => {
  ;(notificationsApi.list as jest.Mock).mockResolvedValue({
    notifications: [MOCK_NOTIFICATION],
    unread_count: 1,
  })
  ;(notificationsApi.markRead as jest.Mock).mockResolvedValue(undefined)
  ;(notificationsApi.markAllRead as jest.Mock).mockResolvedValue(undefined)
})

test('test_notifications_loads_on_mount', async () => {
  render(<NotificationsPage />)
  await waitFor(() => {
    expect(notificationsApi.list).toHaveBeenCalledTimes(1)
  })
  expect(await screen.findByText('Goal achieved!')).toBeInTheDocument()
})

test('test_mark_all_read_hidden_when_no_unread', async () => {
  ;(notificationsApi.list as jest.Mock).mockResolvedValue({
    notifications: [{ ...MOCK_NOTIFICATION, read: true }],
    unread_count: 0,
  })

  render(<NotificationsPage />)
  await waitFor(() => expect(notificationsApi.list).toHaveBeenCalled())

  expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument()
})

test('test_mark_all_read_visible_when_unread', async () => {
  render(<NotificationsPage />)
  await waitFor(() => expect(notificationsApi.list).toHaveBeenCalled())

  expect(await screen.findByRole('button', { name: /mark all read/i })).toBeInTheDocument()
})

test('test_click_unread_card_marks_read', async () => {
  render(<NotificationsPage />)
  // Wait for the notification card to appear
  const card = await screen.findByText('Goal achieved!')
  await userEvent.click(card)

  await waitFor(() => {
    expect(notificationsApi.markRead).toHaveBeenCalledWith('notif-1')
  })
})
```

**Step 2: Run the tests**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx jest __tests__/notifications.test.tsx --no-coverage 2>&1
```

Expected: 4 tests pass.

**Step 3: Commit**

```bash
git add frontend/__tests__/notifications.test.tsx
git commit -m "test: add notifications component tests (loads, mark-all button visibility, mark-read on click)"
```

---

## Task 4: Inline error display on notifications page

**Files:**
- Modify: `frontend/app/dashboard/notifications/page.tsx`

**Background:**

`handleMarkRead` and `handleMarkAllRead` currently swallow errors silently via `console.error`. The design requires an `error` state that shows `"Failed to update notification. Please try again."` inline below the header. On successful `load()`, the error is cleared. Pattern mirrors `saveError` in `settings/page.tsx`.

**Step 1: Add `error` state**

In `NotificationsPage`, after the existing `useState` declarations (currently line 33), add:

```typescript
const [error, setError] = useState<string | null>(null)
```

**Step 2: Clear error on successful load**

In the `load` callback, after `setUnreadCount(unread_count)` (currently line 39), add:

```typescript
setError(null)
```

**Step 3: Set error on markRead failure**

In `handleMarkRead`, replace the `catch` block:

```typescript
// OLD:
} catch (error) {
  console.error('Failed to mark notification as read:', error)
}

// NEW:
} catch {
  setError('Failed to update notification. Please try again.')
}
```

**Step 4: Set error on markAllRead failure**

In `handleMarkAllRead`, replace the `catch` block:

```typescript
// OLD:
} catch (error) {
  console.error('Failed to mark all as read:', error)
}

// NEW:
} catch {
  setError('Failed to update notification. Please try again.')
}
```

**Step 5: Render the error message below the header**

After the closing `</div>` of the header section (currently after line 100), add:

```tsx
{error && <p className="text-sm text-[#DC2626]">{error}</p>}
```

The rendered structure becomes:
```tsx
{/* Header */}
<div className="flex items-center justify-between">
  ...
</div>

{error && <p className="text-sm text-[#DC2626]">{error}</p>}

{/* Loading */}
```

**Step 6: Verify TypeScript compiles**

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx tsc --noEmit 2>&1
```

Expected: No new errors.

**Step 7: Run the full frontend test suite**

```bash
npx jest --no-coverage 2>&1
```

Expected: All tests pass (dashboard: 3, settings: 4, notifications: 4, plus any pre-existing).

**Step 8: Commit**

```bash
git add frontend/app/dashboard/notifications/page.tsx
git commit -m "feat: add inline error state to notifications page for markRead/markAllRead failures"
```

---

## Final Verification

```bash
cd /Users/catiamachado/RelevanceEthicCompanion/frontend
npx jest --no-coverage 2>&1 | tail -15
```

Expected: All tests pass, 0 failures.
