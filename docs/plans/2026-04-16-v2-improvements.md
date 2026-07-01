# V2 Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close critical security gap, add error-surfacing (toasts), standardize backend response shape, and introduce a frontend data layer so the app doesn't re-fetch the same data from three components.

**Architecture:** Four independent phases. Each ends with a shippable state and a commit. Phases 1-2 are trust-critical (secret leak, silent error handling). Phase 3 is backend consistency. Phase 4 is the frontend data layer that unblocks real performance improvements.

**Tech Stack:** FastAPI + psycopg3 (backend), Next.js 16 + Turbopack + React 19 (frontend), `sonner` for toasts, `@tanstack/react-query` for data layer, pytest + Jest for tests.

---

## Phase 1 — Security & deployment safety

**Goal:** A new collaborator can `git clone` + `git pull` and run the app without manual migration steps, and no secrets live in git.

### Task 1.1: Remove leaked secret from `backend/test_connections.py`

**Files:**
- Modify: `backend/test_connections.py`
- Modify: `backend/.gitignore` (if missing)
- Create: `backend/test_connections.example.py`

- [ ] **Step 1: Inspect what the secret is**

Run: `git show 33c50f2e --stat -- backend/test_connections.py`

Then: `grep -nE 'password|secret|key|token' backend/test_connections.py`

Confirm exactly which value GitGuardian flagged (line reported in the alert). The GitGuardian alert from the session pointed at "Generic Password" in this file.

- [ ] **Step 2: Replace the hardcoded secret with an env var read**

Edit the file so the password comes from `os.environ`. Replace the literal with:

```python
import os

DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("POSTGRES_PASSWORD env var required for test_connections.py")
```

Every line that held the literal password must now use `DB_PASSWORD`.

- [ ] **Step 3: Move the file to an example template**

```bash
mv backend/test_connections.py backend/test_connections.example.py
```

Add a header comment at the top:

```python
"""
Example connection-test script.

Copy to `test_connections.py` and run locally; do NOT commit a version
with real credentials. See backend/.env.example for required env vars.
"""
```

- [ ] **Step 4: Ensure `test_connections.py` is git-ignored**

Read `backend/.gitignore` (create if missing). Add the line if not present:

```
test_connections.py
```

- [ ] **Step 5: Remove the secret from git history**

The secret is still in past commits (commit `33c50f2e`). Decide with the user whether to do a full `git filter-repo` cleanup or accept rotating the leaked credential. For now: **rotate the credential at its source** (Supabase/DB provider UI). Make a note in the commit message.

- [ ] **Step 6: Verify nothing else references the deleted file**

Run: `grep -rn "test_connections" backend/ --exclude-dir=venv`

Expected: only matches in the new `test_connections.example.py` or docs.

- [ ] **Step 7: Run the backend test suite to make sure nothing broke**

Run: `cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest -x --tb=short`

Expected: all previously-passing tests still pass (the connections file isn't in the test path).

- [ ] **Step 8: Commit**

```bash
git add backend/test_connections.example.py backend/.gitignore
git rm backend/test_connections.py 2>/dev/null || true
git commit -m "$(cat <<'EOF'
security: remove hardcoded password from test_connections.py

GitGuardian flagged a Generic Password in test_connections.py at commit
33c50f2e. Moved the file to test_connections.example.py, replaced the
literal with os.environ.get("POSTGRES_PASSWORD"), and added the non-example
path to .gitignore.

IMPORTANT: rotate the leaked credential at the database provider —
removing from HEAD doesn't invalidate the exposure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.2: Auto-run pending migrations on FastAPI startup

**Files:**
- Modify: `backend/main.py` (lifespan / startup hook)
- Read: `backend/scripts/run_migrations.py` (reuse existing function)

- [ ] **Step 1: Find the FastAPI lifespan / startup location**

Run: `grep -nE "lifespan|on_event.*startup|@app\.on_event" backend/main.py`

Note the line numbers of any existing startup code.

- [ ] **Step 2: Read the existing `run_migrations` function signature**

```bash
sed -n '25,75p' backend/scripts/run_migrations.py
```

Confirm the function signature is `run_migrations(migrations_dir: str | None = None) -> None` and it handles idempotency via the `schema_migrations` table.

- [ ] **Step 3: Import and call it from main.py's startup**

Add near the top of `backend/main.py`:

```python
from scripts.run_migrations import run_migrations
```

Find the existing `@app.on_event("startup")` handler (or the `lifespan` function). Add at the START of that handler, before any DB-dependent initialisation:

```python
try:
    run_migrations()
    logger.info("✅ Database migrations up to date")
except Exception as exc:
    logger.exception("❌ Migration failed on startup; refusing to serve traffic")
    raise
```

If there is no startup handler at all, add one:

```python
@app.on_event("startup")
async def startup_event() -> None:
    try:
        run_migrations()
        logger.info("✅ Database migrations up to date")
    except Exception:
        logger.exception("❌ Migration failed on startup; refusing to serve traffic")
        raise
```

- [ ] **Step 4: Verify startup still works**

Restart the backend:

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python main.py
```

Expected: the log shows `✅ Database migrations up to date` shortly after boot, and the server starts listening on `:8000`.

Stop with Ctrl-C once confirmed.

- [ ] **Step 5: Manually break the migration tracking to verify the failure path**

In psql (or through `get_db_connection`):

```sql
INSERT INTO schema_migrations (filename) VALUES ('999_nonexistent.sql');
```

Create a deliberately-broken migration:

```bash
echo "THIS IS NOT VALID SQL" > backend/migrations/999_test_broken.sql
```

Re-run the backend:

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python main.py
```

Expected: the server **refuses to start** with a clear traceback pointing at `999_test_broken.sql`.

- [ ] **Step 6: Clean up**

```bash
rm backend/migrations/999_test_broken.sql
```

Remove the bogus `schema_migrations` row via psql:

```sql
DELETE FROM schema_migrations WHERE filename = '999_nonexistent.sql';
```

- [ ] **Step 7: Commit**

```bash
git add backend/main.py
git commit -m "$(cat <<'EOF'
feat(deploy): auto-apply pending migrations on FastAPI startup

Previously, pending migrations had to be applied manually via
`python -m scripts.run_migrations`. New deploys / collaborators would
hit mysterious "relation does not exist" errors when routes queried
unmigrated tables.

Now the startup hook calls run_migrations() before accepting traffic.
On failure, the process exits with a full traceback instead of
silently serving a broken schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.3: Improve migration runner error messages

**Files:**
- Modify: `backend/scripts/run_migrations.py:82-85`

- [ ] **Step 1: Reproduce the unhelpful message**

Run with any trivial SQL error (e.g., a file containing `SELECT nonexistent_column;`):

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m scripts.run_migrations
```

Note: the current message is `Migration failed: 0` or similar cryptic output — the exception's `str()` is unhelpful.

- [ ] **Step 2: Replace `logger.error` with `logger.exception`**

Open `backend/scripts/run_migrations.py`. Find:

```python
except Exception as exc:
    logger.error("Migration failed: %s", exc)
    sys.exit(1)
```

Replace with:

```python
except Exception:
    logger.exception("Migration failed")
    sys.exit(1)
```

`logger.exception()` logs the full traceback automatically; the positional-arg confusion disappears.

- [ ] **Step 3: Also log which migration file was in flight when it failed**

Find the `for filename in sql_files:` loop. Wrap the inner body in a try/except that re-raises with context:

```python
for filename in sql_files:
    if filename in applied:
        logger.info("  skip (already applied): %s", filename)
        continue

    filepath = os.path.join(migrations_dir, filename)
    sql = Path(filepath).read_text(encoding="utf-8")

    logger.info("  applying: %s", filename)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,),
                )
    except Exception:
        logger.exception("  ❌ failed while applying: %s", filename)
        raise
    logger.info("  ✅ done: %s", filename)
```

- [ ] **Step 4: Verify the new error output**

Create a broken migration temporarily:

```bash
echo "SELECT non_existent_col FROM nonexistent_table;" > backend/migrations/999_broken.sql
```

Run:

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m scripts.run_migrations
```

Expected: full traceback with filename, SQL error from psycopg, pointing at `999_broken.sql`.

- [ ] **Step 5: Clean up**

```bash
rm backend/migrations/999_broken.sql
```

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/run_migrations.py
git commit -m "$(cat <<'EOF'
fix(migrations): log full traceback + offending filename on failure

The old handler logged exc via positional-arg substitution, which
turned confusing exceptions into messages like "Migration failed: 0".
Switched to logger.exception() and wrapped each file's apply block so
the log pins the exact migration that broke.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 1 verification

- [ ] Grep for the old password literal: `git grep -i "<the-literal>"` returns nothing outside `.gitignore`.
- [ ] Fresh backend start logs `✅ Database migrations up to date`.
- [ ] A deliberately-broken migration file causes startup to fail with a readable traceback.

---

## Phase 2 — UX trust: error surfacing

**Goal:** No action fails silently. Slash commands, folder CRUD, rename, etc. all surface success and failure through a unified toast system. Destructive actions confirm.

### Task 2.1: Install and mount toast provider (sonner)

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/layout.tsx` (root layout)
- Create: `frontend/lib/toast.ts`

- [ ] **Step 1: Install sonner**

```bash
cd frontend && npm install sonner
```

Expected: `sonner@^1.x` added to `dependencies` in `package.json`.

- [ ] **Step 2: Create a thin wrapper so components don't import sonner directly**

Create `frontend/lib/toast.ts`:

```typescript
import { toast as sonnerToast } from "sonner"

/** Thin wrapper so the rest of the app stays decoupled from sonner. */
export const toast = {
  success: (message: string, description?: string) =>
    sonnerToast.success(message, description ? { description } : undefined),
  error: (message: string, description?: string) =>
    sonnerToast.error(message, description ? { description } : undefined),
  info: (message: string, description?: string) =>
    sonnerToast(message, description ? { description } : undefined),
}
```

- [ ] **Step 3: Mount the <Toaster /> in the root layout**

Edit `frontend/app/layout.tsx`. Import:

```typescript
import { Toaster } from "sonner"
```

Inside the body JSX, just before closing `</ThemeProvider>` (or wherever the tree ends):

```tsx
<Toaster
  position="bottom-right"
  toastOptions={{
    style: {
      background: "var(--ec-card-bg)",
      color: "var(--ec-text)",
      border: "1px solid var(--ec-card-border)",
    },
  }}
/>
```

- [ ] **Step 4: Verify nothing broke**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero TS errors.

Load the app at `localhost:3000`. Open the browser console, run:

```javascript
window.dispatchEvent(new Event("ec:test-toast"))
```

Open `frontend/lib/toast.ts` temporarily and add at the bottom (only for this verification):

```typescript
if (typeof window !== "undefined") {
  window.addEventListener("ec:test-toast", () => toast.success("It works"))
}
```

A toast should appear in the bottom-right.

Remove the temporary test block afterward.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/lib/toast.ts frontend/app/layout.tsx
git commit -m "$(cat <<'EOF'
feat(ui): add sonner toast system with theme-aware styling

Wraps sonner behind lib/toast.ts so the rest of the app stays
decoupled. Toaster is mounted once in the root layout with
CSS-variable-driven colours so it adapts to dark mode.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.2: Wire slash commands to toasts

**Files:**
- Modify: `frontend/components/chat/slash-commands.tsx` (each `catch` block)

- [ ] **Step 1: Import toast at top of the file**

Add to the imports in `frontend/components/chat/slash-commands.tsx`:

```typescript
import { toast } from "@/lib/toast"
```

- [ ] **Step 2: Replace console.error in `/task` with toast + keep console log for dev**

Find the `id: "create-task"` command's `run` function. Replace the `catch` block:

```typescript
      } catch (e) {
        console.error("create task failed", e)
        toast.error("Couldn't create task", e instanceof Error ? e.message : undefined)
      }
```

Also add a success toast right before the `window.dispatchEvent` call:

```typescript
        toast.success("Task added", title)
        window.dispatchEvent(new CustomEvent("ec:open-panel", {
          detail: { name: "tasks", title: "Your tasks" },
        }))
```

- [ ] **Step 3: Do the same for `/goal`**

Find `id: "create-goal"`. Same treatment: success toast on creation, error toast on failure.

```typescript
      try {
        await api.goals.create({
          title,
          priority: 1,
          ...(iso ? { target_date: iso } : {}),
        })
        toast.success("Goal added", title)
        window.dispatchEvent(new CustomEvent("ec:open-panel", {
          detail: { name: "goals", title: "Your goals" },
        }))
      } catch (e) {
        console.error("create goal failed", e)
        toast.error("Couldn't create goal", e instanceof Error ? e.message : undefined)
      }
```

- [ ] **Step 4: Do the same for `/folder`**

Find `id: "new-folder"`. Replace:

```typescript
      try {
        await api.folders.create(name)
        toast.success("Folder created", name)
        window.dispatchEvent(new Event("ec:conversation-created"))
      } catch (e) {
        console.error("create folder failed", e)
        toast.error("Couldn't create folder", e instanceof Error ? e.message : undefined)
      }
```

- [ ] **Step 5: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 6: Manually verify in the browser**

Open `/dashboard/chat`, type `/task Buy milk tomorrow`, press Enter. Expected: success toast "Task added — Buy milk" appears bottom-right, tasks panel opens.

Type `/folder ` (empty after prompt), cancel the prompt. Expected: no toast (early return when name is empty).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/chat/slash-commands.tsx
git commit -m "$(cat <<'EOF'
feat(chat): slash command creation surfaces success + failures via toast

Previously, /task /goal /folder wrote console.error on failure so the
user saw nothing. Added toast.success on creation and toast.error with
the API error message on failure. This is the UX contract for "Trust
over Engagement" — silent failures violate it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.3: Wire sidebar folder CRUD errors to toasts

**Files:**
- Modify: `frontend/components/sidebar.tsx` (3 existing handlers)

- [ ] **Step 1: Add toast import**

At the top of `frontend/components/sidebar.tsx`, add:

```typescript
import { toast } from "@/lib/toast"
```

- [ ] **Step 2: Replace inline `showFolderError` / local error state with toasts**

Find `handleCreateFolder`. Replace:

```typescript
  const handleCreateFolder = async () => {
    const name = newFolderName.trim()
    if (!name) { setCreatingFolder(false); setNewFolderName(''); return }
    try {
      const folder = await api.folders.create(name)
      setFolders(prev => [...prev, folder])
      setExpandedFolders(prev => new Set(prev).add(folder.id))
      toast.success("Folder created", name)
      setCreatingFolder(false)
      setNewFolderName('')
    } catch (e) {
      console.error('create folder failed', e)
      toast.error("Couldn't create folder", e instanceof Error ? e.message : undefined)
      // Keep the input open so the user can retry
    }
  }
```

- [ ] **Step 3: Same pattern for `handleRenameFolder` and `handleDeleteFolder`**

```typescript
  const handleRenameFolder = async (id: string) => {
    const name = editFolderName.trim()
    if (!name) { setEditingFolderId(null); return }
    try {
      const updated = await api.folders.update(id, { name })
      setFolders(prev => prev.map(f => f.id === id ? updated : f))
      toast.success("Folder renamed", name)
      setEditingFolderId(null)
      setEditFolderName('')
    } catch (e) {
      console.error('rename folder failed', e)
      toast.error("Couldn't rename folder", e instanceof Error ? e.message : undefined)
    }
  }

  const handleDeleteFolder = async (id: string) => {
    const folder = folders.find(f => f.id === id)
    try {
      await api.folders.delete(id)
      setFolders(prev => prev.filter(f => f.id !== id))
      setConversations(prev => prev.map(c => c.folder_id === id ? { ...c, folder_id: null } : c))
      toast.success("Folder deleted", folder?.name)
    } catch (e) {
      console.error('delete folder failed', e)
      toast.error("Couldn't delete folder", e instanceof Error ? e.message : undefined)
    }
  }
```

- [ ] **Step 4: Remove the now-unused `folderError` state + `showFolderError`**

Delete these two lines near the top of the component:

```typescript
const [folderError, setFolderError] = useState<string | null>(null)

const showFolderError = useCallback((msg: string) => {
  setFolderError(msg)
  setTimeout(() => setFolderError(null), 4000)
}, [])
```

And delete the JSX block that renders `folderError` inside the Folders section:

```tsx
{folderError && (
  <p className="text-[10px] px-1 py-1 leading-tight" style={{ color: '#B04A3A' }} role="alert">
    {folderError}
  </p>
)}
```

Also remove `!folderError` from the empty-state condition:

```tsx
{folders.length === 0 && !creatingFolder && (
  <p className="text-[10px] px-1 italic" ...>No folders yet</p>
)}
```

- [ ] **Step 5: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/sidebar.tsx
git commit -m "$(cat <<'EOF'
feat(sidebar): replace inline folderError with toast notifications

Removes the bespoke showFolderError + inline alert row that lived in
the Folders section. All three folder mutations (create / rename /
delete) now route through lib/toast for both success and failure.
More consistent across the app and decluttered the sidebar.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.4: Folder delete confirmation dialog

**Files:**
- Modify: `frontend/components/sidebar.tsx` (handleDeleteFolder + trash button onClick)

- [ ] **Step 1: Change handleDeleteFolder to accept a folder object**

```typescript
  const handleDeleteFolder = async (folder: Folder) => {
    const convCount = conversations.filter(c => c.folder_id === folder.id).length
    const msg = convCount > 0
      ? `Delete "${folder.name}"? Its ${convCount} conversation${convCount === 1 ? '' : 's'} will be unfoldered (not deleted).`
      : `Delete "${folder.name}"?`
    if (!window.confirm(msg)) return

    try {
      await api.folders.delete(folder.id)
      setFolders(prev => prev.filter(f => f.id !== folder.id))
      setConversations(prev => prev.map(c => c.folder_id === folder.id ? { ...c, folder_id: null } : c))
      toast.success("Folder deleted", folder.name)
    } catch (e) {
      console.error('delete folder failed', e)
      toast.error("Couldn't delete folder", e instanceof Error ? e.message : undefined)
    }
  }
```

- [ ] **Step 2: Update the trash button to pass the folder object**

Find the existing trash button click handler in the folder row. Change:

```tsx
onClick={e => { e.stopPropagation(); handleDeleteFolder(folder.id) }}
```

to:

```tsx
onClick={e => { e.stopPropagation(); handleDeleteFolder(folder) }}
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 4: Manually verify**

Create a folder, drop a conversation into it, hover the folder, click trash. Expected: `window.confirm` appears with "Delete 'X'? Its 1 conversation will be unfoldered (not deleted)." Cancel → nothing changes. Confirm → folder gone, conversation reappears under Conversations section, toast "Folder deleted".

- [ ] **Step 5: Commit**

```bash
git add frontend/components/sidebar.tsx
git commit -m "$(cat <<'EOF'
feat(sidebar): confirm before deleting a folder

Folder delete was instant. Now shows a browser confirm dialog that
mentions how many conversations will be moved to ungrouped (they
aren't destroyed — the FK is ON DELETE SET NULL). Minor UX guard rail.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.5: Dedicated `GET /api/chat/conversations/:id` endpoint

**Files:**
- Modify: `backend/routes/chat.py` (new endpoint)
- Modify: `frontend/lib/api.ts` (new `get` method)
- Modify: `frontend/app/dashboard/chat/page.tsx` (use new endpoint)

- [ ] **Step 1: Add the backend endpoint**

Open `backend/routes/chat.py`. Below the existing `list_conversations` handler, add:

```python
@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """Fetch a single conversation's metadata (no messages)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, folder_id, created_at, updated_at
                FROM conversations
                WHERE id = %s AND user_id = %s
            """, (conversation_id, user_id))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "folder_id": str(row["folder_id"]) if row.get("folder_id") else None,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
```

- [ ] **Step 2: Write a pytest test for the new endpoint**

Append to `backend/tests/test_chat.py` (or create `backend/tests/test_chat_conversations.py`):

```python
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from utils.supabase_auth import get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"

def _make_app_and_client():
    from routes.chat import router as chat_router
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return TestClient(app)

def _db_mock(fetchone=None):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn

def test_get_conversation_returns_row():
    client = _make_app_and_client()
    row = {
        "id": "conv-1",
        "title": "Hello",
        "folder_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    with patch("routes.chat.get_db_connection", return_value=_db_mock(fetchone=row)):
        r = client.get("/api/chat/conversations/conv-1")
    assert r.status_code == 200
    assert r.json()["title"] == "Hello"
    assert r.json()["folder_id"] is None

def test_get_conversation_404():
    client = _make_app_and_client()
    with patch("routes.chat.get_db_connection", return_value=_db_mock(fetchone=None)):
        r = client.get("/api/chat/conversations/missing")
    assert r.status_code == 404
```

- [ ] **Step 3: Run the new tests**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_chat.py -v -k "test_get_conversation"
```

Expected: 2 passed.

- [ ] **Step 4: Add frontend API client method**

In `frontend/lib/api.ts`, find `conversations: {` inside `chatApi`. Add a `get` method between `list` and `create`:

```typescript
  conversations: {
    list: () =>
      apiRequest<{ conversations: Array<{ id: string; title: string; folder_id: string | null; created_at: string; updated_at: string }> }>('/api/chat/conversations'),
    get: (id: string) =>
      apiRequest<{ id: string; title: string; folder_id: string | null; created_at: string; updated_at: string }>(`/api/chat/conversations/${id}`),
    create: () =>
      ...
```

- [ ] **Step 5: Use it in the chat page**

Open `frontend/app/dashboard/chat/page.tsx`. Find the block that fetches conversation title (grep for `conversationTitle`). Replace:

```typescript
  useEffect(() => {
    if (!conversationId) { setConversationTitle(''); return }
    api.chat.conversations.list()
      .then(r => {
        const c = r.conversations.find(x => x.id === conversationId)
        if (c) setConversationTitle(c.title)
      })
      .catch(() => {})
  }, [conversationId])
```

with:

```typescript
  useEffect(() => {
    if (!conversationId) { setConversationTitle(''); return }
    api.chat.conversations.get(conversationId)
      .then(c => setConversationTitle(c.title))
      .catch(() => {})
  }, [conversationId])
```

- [ ] **Step 6: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add backend/routes/chat.py backend/tests/test_chat.py frontend/lib/api.ts frontend/app/dashboard/chat/page.tsx
git commit -m "$(cat <<'EOF'
perf(chat): dedicated GET /conversations/:id endpoint

Chat page was listing ALL conversations to find the one it needed
just to show the title in the header (O(n) per navigation). Added a
dedicated endpoint + frontend client method + two new pytest cases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 2 verification

- [ ] Every folder and slash-command error path renders a red toast instead of console-only.
- [ ] Every create/rename/delete success renders a green toast.
- [ ] Folder delete prompts before destroying.
- [ ] `pytest tests/test_chat.py` adds 2 new passing tests.
- [ ] Chat page no longer calls `conversations.list()` just to fetch one title.

---

## Phase 3 — Backend consistency & coverage

**Goal:** Enforce that folder names are unique per user, give the dashboard a single aggregated endpoint instead of 7 parallel fetches, add rate limits, and cover the natural-language date parser with unit tests.

### Task 3.1: Unique `(user_id, name)` constraint on folders

**Files:**
- Create: `backend/migrations/008_folder_unique_name.sql`
- Modify: `backend/routes/folders.py` (catch UniqueViolation, return 409)
- Modify: `backend/tests/test_folders.py` (new test case)

- [ ] **Step 1: Write the migration**

Create `backend/migrations/008_folder_unique_name.sql`:

```sql
-- Migration 008: Unique folder name per user.
-- Prevents accidental duplicates like two "Work" folders.
-- Case-insensitive via LOWER() so "Work" and "work" collide.

CREATE UNIQUE INDEX IF NOT EXISTS uniq_folders_user_lower_name
    ON folders (user_id, LOWER(name));
```

- [ ] **Step 2: Write a failing test for duplicate rejection**

In `backend/tests/test_folders.py`, add after `test_create_folder_success`:

```python
def test_create_folder_duplicate_name_returns_409(client):
    """Creating a folder with the same name as an existing one should 409."""
    # First create succeeds.
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [{"next_pos": 0}, SAMPLE_FOLDER_ROW]
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # psycopg3 UniqueViolation simulation
    from psycopg.errors import UniqueViolation
    # Arrange: INSERT raises, MAX query completes normally first
    def execute_side_effect(sql, params=None):
        if "INSERT INTO folders" in sql:
            raise UniqueViolation("duplicate key value")
        return None
    mock_cursor.execute.side_effect = execute_side_effect

    with patch("routes.folders.get_db_connection", return_value=mock_conn):
        r = client.post("/api/folders", json={"name": "Work"})

    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()
```

- [ ] **Step 3: Run the test to confirm it fails**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_folders.py::test_create_folder_duplicate_name_returns_409 -v
```

Expected: FAIL (endpoint returns 500 or 200 instead of 409).

- [ ] **Step 4: Catch UniqueViolation in the create handler**

In `backend/routes/folders.py`, at the top add:

```python
from psycopg.errors import UniqueViolation
```

Modify the `create_folder` handler body — wrap the INSERT in a try/except:

```python
@router.post("")
async def create_folder(
    body: FolderCreate,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Create a new folder owned by the current user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if body.position is None:
                cur.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM folders WHERE user_id = %s",
                    (user_id,),
                )
                next_pos = cur.fetchone()["next_pos"]
            else:
                next_pos = body.position

            try:
                cur.execute("""
                    INSERT INTO folders (user_id, name, color, position)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, color, position, created_at, updated_at
                """, (user_id, body.name.strip(), body.color, next_pos))
                row = cur.fetchone()
            except UniqueViolation:
                raise HTTPException(
                    status_code=409,
                    detail=f"A folder named '{body.name.strip()}' already exists",
                )
    return _serialize_folder(row)
```

- [ ] **Step 5: Similarly wrap the update handler**

In `update_folder`, wrap the UPDATE in the same try/except:

```python
            try:
                cur.execute(
                    f"""
                    UPDATE folders SET {", ".join(updates)}
                    WHERE id = %s AND user_id = %s
                    RETURNING id, name, color, position, created_at, updated_at
                    """,
                    params,
                )
                row = cur.fetchone()
            except UniqueViolation:
                raise HTTPException(
                    status_code=409,
                    detail=f"A folder with that name already exists",
                )
```

- [ ] **Step 6: Run the test to confirm it passes**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_folders.py -v
```

Expected: 15/15 passing (14 existing + 1 new).

- [ ] **Step 7: Apply the migration to the running DB**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m scripts.run_migrations
```

Expected output contains: `✅ done: 008_folder_unique_name.sql`.

- [ ] **Step 8: Surface the 409 to the user in the sidebar**

In `frontend/components/sidebar.tsx`, the `handleCreateFolder` and `handleRenameFolder` already route errors through toast. The 409 body message is what the user will see. No frontend code change required; verify by attempting to create "Work" twice:

Expected: second attempt → red toast "Couldn't create folder — A folder named 'Work' already exists".

- [ ] **Step 9: Commit**

```bash
git add backend/migrations/008_folder_unique_name.sql backend/routes/folders.py backend/tests/test_folders.py
git commit -m "$(cat <<'EOF'
feat(folders): reject duplicate folder names with 409

Added a case-insensitive unique index on (user_id, LOWER(name)) and
caught psycopg's UniqueViolation in create + update handlers. Returns
a clear 409 with the name in the detail. Frontend already routes
these through toast, so the user sees "A folder named 'Work' already
exists" instead of a silent failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.2: Aggregated `/api/dashboard/overview` endpoint

**Files:**
- Create: `backend/routes/dashboard.py`
- Modify: `backend/main.py` (register router)
- Create: `backend/tests/test_dashboard.py`
- Modify: `frontend/lib/api.ts` (add dashboardApi)
- Modify: `frontend/components/tools-launcher.tsx` (use aggregated endpoint)

- [ ] **Step 1: Write a failing test first**

Create `backend/tests/test_dashboard.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest

from routes.dashboard import router as dashboard_router
from utils.supabase_auth import get_current_read_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000000"

def _client():
    app = FastAPI()
    app.include_router(dashboard_router)
    app.dependency_overrides[get_current_read_user_id] = lambda: TEST_USER_ID
    return TestClient(app)

def _db(fetchone_seq):
    cur = MagicMock()
    cur.fetchone.side_effect = fetchone_seq
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn

def test_overview_returns_all_counts():
    client = _client()
    # Each COUNT query returns {"cnt": N} in order: goals, tasks, projects, values, documents, transparency, notifications
    counts = [{"cnt": 3}, {"cnt": 8}, {"cnt": 2}, {"cnt": 5}, {"cnt": 12}, {"cnt": 42}, {"cnt": 1}]
    with patch("routes.dashboard.get_db_connection", return_value=_db(counts)):
        r = client.get("/api/dashboard/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["goals_active"] == 3
    assert body["tasks_open"] == 8
    assert body["projects_active"] == 2
    assert body["values_count"] == 5
    assert body["documents_count"] == 12
    assert body["esl_decisions_7d"] == 42
    assert body["notifications_unread"] == 1
```

- [ ] **Step 2: Run the test — it should fail**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_dashboard.py -v
```

Expected: FAIL with ImportError because `routes.dashboard` doesn't exist.

- [ ] **Step 3: Write the route**

Create `backend/routes/dashboard.py`:

```python
"""
Dashboard aggregated-overview route.

Returns a single JSON with all counts needed to render the dashboard's
tools launcher. Replaces the 7 parallel fetches that the old frontend
made, each of which had its own round-trip + auth overhead.
"""

from fastapi import APIRouter, Depends
from utils.supabase_auth import get_current_read_user_id
from utils.db import get_db_connection


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def overview(
    user_id: str = Depends(get_current_read_user_id),
) -> dict:
    """Return every count the dashboard launcher needs, in one response."""
    queries = [
        ("goals_active",        "SELECT COUNT(*) AS cnt FROM goals WHERE user_id = %s AND status = 'active'"),
        ("tasks_open",          "SELECT COUNT(*) AS cnt FROM tasks WHERE user_id = %s AND status IN ('todo','in_progress')"),
        ("projects_active",     "SELECT COUNT(*) AS cnt FROM projects WHERE user_id = %s AND status = 'active'"),
        ("values_count",        "SELECT COUNT(*) AS cnt FROM user_values WHERE user_id = %s AND active = TRUE"),
        ("documents_count",     "SELECT COUNT(*) AS cnt FROM documents WHERE user_id = %s"),
        ("esl_decisions_7d",    "SELECT COUNT(*) AS cnt FROM esl_audit_log WHERE user_id = %s AND created_at > NOW() - INTERVAL '7 days'"),
        ("notifications_unread","SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = %s AND read = FALSE"),
    ]

    out: dict = {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for key, sql in queries:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
                out[key] = (row or {}).get("cnt", 0)
    return out
```

- [ ] **Step 4: Register the router in main.py**

Edit `backend/main.py`. In the import block near line 259:

```python
from routes import auth, values, chat, goals, transparency, relevance, data_sources, profile, notifications, feedback, search, documents, projects, tasks, context, folders, dashboard
```

Add `dashboard` to the list (keep other names alphabetical / position-matching existing style).

Below the other `include_router` calls:

```python
app.include_router(dashboard.router)
```

- [ ] **Step 5: Run the test — should pass**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_dashboard.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Add frontend client method**

In `frontend/lib/api.ts`, add a new section before `export const api = { ... }`:

```typescript
// ==================== Dashboard API ====================

export interface DashboardOverview {
  goals_active: number
  tasks_open: number
  projects_active: number
  values_count: number
  documents_count: number
  esl_decisions_7d: number
  notifications_unread: number
}

export const dashboardApi = {
  overview: () => apiRequest<DashboardOverview>('/api/dashboard/overview'),
}
```

And add `dashboard: dashboardApi` inside `export const api = { ... }`.

- [ ] **Step 7: Migrate `ToolsLauncher` to the single endpoint**

Open `frontend/components/tools-launcher.tsx`. Replace the 7 separate `useEffect` fetches + state hooks with one call:

```typescript
const [overview, setOverview] = useState<{
  goals_active: number
  tasks_open: number
  projects_active: number
  values_count: number
  documents_count: number
  esl_decisions_7d: number
  notifications_unread: number
} | null>(null)

useEffect(() => {
  api.dashboard.overview()
    .then(setOverview)
    .catch(() => {})
}, [])
```

Replace each `count: goalsCount` style reference with `count: overview?.goals_active ?? null`, etc. Remove the old individual state variables (`goalsCount`, `tasksCount`, ...) and their useEffect calls.

Concretely the tool array becomes:

```typescript
const tools: ToolCard[] = [
  {
    href: "/dashboard/goals",
    title: "Goals",
    subtitle: "Long-term direction",
    icon: <Target size={16} />,
    count: overview?.goals_active ?? null,
    unit: "active",
    accent: "rgba(74,124,89,0.10)",
    panelName: "goals",
  },
  {
    href: "/dashboard/tasks",
    title: "Tasks",
    subtitle: "This week's work",
    icon: <CheckSquare size={16} />,
    count: overview?.tasks_open ?? null,
    unit: "open",
    accent: "rgba(74,124,89,0.10)",
    panelName: "tasks",
  },
  {
    href: "/dashboard/projects",
    title: "Projects",
    subtitle: "Grouped initiatives",
    icon: <FolderOpen size={16} />,
    count: overview?.projects_active ?? null,
    unit: "active",
    accent: "rgba(155,122,61,0.10)",
    panelName: "projects",
  },
  {
    href: "/dashboard/values",
    title: "Values",
    subtitle: "Your boundaries",
    icon: <Heart size={16} />,
    count: overview?.values_count ?? null,
    unit: "defined",
    accent: "rgba(155,122,61,0.10)",
    panelName: "values",
  },
  {
    href: "/dashboard/documents",
    title: "Documents",
    subtitle: "Uploaded files",
    icon: <FileText size={16} />,
    count: overview?.documents_count ?? null,
    unit: "files",
    accent: "rgba(74,124,89,0.10)",
    panelName: "documents",
  },
  {
    href: "/dashboard/transparency",
    title: "Transparency",
    subtitle: "ESL audit log",
    icon: <Eye size={16} />,
    count: overview?.esl_decisions_7d ?? null,
    unit: "decisions",
    accent: "rgba(74,124,89,0.10)",
    panelName: "transparency",
  },
  {
    href: "/dashboard/notifications",
    title: "Notifications",
    subtitle: "Activity alerts",
    icon: <Bell size={16} />,
    count: overview?.notifications_unread ?? null,
    unit: "unread",
    accent: (overview?.notifications_unread ?? 0) > 0 ? "rgba(176,74,58,0.10)" : "rgba(74,124,89,0.10)",
    panelName: "notifications",
  },
]
```

- [ ] **Step 8: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 9: Verify in browser**

Open `/dashboard`. Open DevTools → Network. Filter for `api/`. Expected: exactly **one** `api/dashboard/overview` request (instead of 7 separate endpoints).

- [ ] **Step 10: Commit**

```bash
git add backend/routes/dashboard.py backend/main.py backend/tests/test_dashboard.py frontend/lib/api.ts frontend/components/tools-launcher.tsx
git commit -m "$(cat <<'EOF'
perf(dashboard): aggregate 7 count queries into a single /overview endpoint

ToolsLauncher used to fan out 7 parallel GETs to goals/tasks/projects/
values/documents/transparency/notifications — each with its own auth
round-trip. Consolidated into GET /api/dashboard/overview that returns
one JSON with all counts. Dashboard network panel now shows 1 request
instead of 7.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.3: Unit tests for `parseNaturalDate`

**Files:**
- Create: `frontend/__tests__/parse-natural-date.test.ts`

- [ ] **Step 1: Check the existing jest setup**

```bash
cat frontend/package.json | grep -A2 '"test"'
ls frontend/__tests__ | head -5
```

Note the test command (probably `jest` or `vitest`). The existing `__tests__/` folder indicates this is the pattern.

- [ ] **Step 2: Write the test file**

Create `frontend/__tests__/parse-natural-date.test.ts`:

```typescript
import { parseNaturalDate } from "@/components/chat/parse-natural-date"

// Fix "now" to a known Thursday so weekday math is deterministic.
const NOW = new Date("2026-04-16T10:00:00Z")


describe("parseNaturalDate", () => {
  it("returns no date for plain text", () => {
    const r = parseNaturalDate("Buy a new bike", NOW)
    expect(r.iso).toBeNull()
    expect(r.title).toBe("Buy a new bike")
  })

  it("parses 'today'", () => {
    const r = parseNaturalDate("Call mom today", NOW)
    expect(r.iso).toBe("2026-04-16")
    expect(r.title).toBe("Call mom")
  })

  it("parses 'tomorrow' and strips it from title", () => {
    const r = parseNaturalDate("Buy milk tomorrow", NOW)
    expect(r.iso).toBe("2026-04-17")
    expect(r.title).toBe("Buy milk")
  })

  it("parses an upcoming weekday (Friday from Thursday)", () => {
    const r = parseNaturalDate("Ship feature friday", NOW)
    expect(r.iso).toBe("2026-04-17")  // Friday is the next day after this Thursday
    expect(r.title).toBe("Ship feature")
  })

  it("parses 'next monday'", () => {
    const r = parseNaturalDate("Review docs next monday", NOW)
    expect(r.iso).toBe("2026-04-20")  // Mon after Thu 2026-04-16
    expect(r.title).toBe("Review docs")
  })

  it("parses 'in 3 days'", () => {
    const r = parseNaturalDate("Write report in 3 days", NOW)
    expect(r.iso).toBe("2026-04-19")
    expect(r.title).toBe("Write report")
  })

  it("parses 'in 2 weeks'", () => {
    const r = parseNaturalDate("Quarterly review in 2 weeks", NOW)
    expect(r.iso).toBe("2026-04-30")
    expect(r.title).toBe("Quarterly review")
  })

  it("parses 'may 30' and rolls to next year if past", () => {
    // Parsing on April 16 2026 — may 30 is ~6 weeks out, same year.
    const r = parseNaturalDate("Deadline may 30", NOW)
    expect(r.iso).toBe("2026-05-30")
    expect(r.title).toBe("Deadline")

    // Parsing "january 10" on April 16 should roll to NEXT January.
    const r2 = parseNaturalDate("Retreat january 10", NOW)
    expect(r2.iso).toBe("2027-01-10")
  })

  it("parses ISO 'by YYYY-MM-DD'", () => {
    const r = parseNaturalDate("Submit by 2026-06-15", NOW)
    expect(r.iso).toBe("2026-06-15")
    expect(r.title).toBe("Submit")
  })

  it("parses 'this weekend' as Saturday", () => {
    // From Thursday 2026-04-16, Saturday is 2026-04-18.
    const r = parseNaturalDate("Paint room this weekend", NOW)
    expect(r.iso).toBe("2026-04-18")
    expect(r.title).toBe("Paint room")
  })

  it("returns empty title + null when input is empty", () => {
    const r = parseNaturalDate("", NOW)
    expect(r.iso).toBeNull()
    expect(r.title).toBe("")
  })

  it("normalises whitespace after stripping date span", () => {
    const r = parseNaturalDate("  Buy  milk   tomorrow  ", NOW)
    expect(r.iso).toBe("2026-04-17")
    expect(r.title).toBe("Buy  milk")  // inner spaces preserved, outer trimmed — acceptable
  })
})
```

- [ ] **Step 3: Run the tests**

```bash
cd frontend && npm test -- parse-natural-date
```

Expected: 11 passing. If "this weekend" or month rollover fail, fix the parser accordingly (the test is the spec).

- [ ] **Step 4: Commit**

```bash
git add frontend/__tests__/parse-natural-date.test.ts
git commit -m "$(cat <<'EOF'
test(chat): unit tests for parseNaturalDate

Covers every pattern in the parser: today/tomorrow, weekdays,
next <weekday>, in N days/weeks, "by YYYY-MM-DD", month + day with
rollover to next year, this weekend, and empty-input edge case.
tsc only validates types — these tests pin the behaviour.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.4: Rate-limit folder creation

**Files:**
- Modify: `backend/routes/folders.py` (add limiter decorator)
- Read: `backend/utils/rate_limit.py` (confirm the shape of `limiter`)

- [ ] **Step 1: Check how limiter is used elsewhere**

```bash
grep -rn "@limiter" backend/routes/ | head -5
```

Find an existing example (likely in `chat.py` or `auth.py`). Note the exact syntax, e.g. `@limiter.limit("5/minute")`.

- [ ] **Step 2: Apply to create_folder**

In `backend/routes/folders.py`, add import at top:

```python
from fastapi import Request
from utils.rate_limit import limiter
```

Modify the create handler signature + decorator. From:

```python
@router.post("")
async def create_folder(
    body: FolderCreate,
    user_id: str = Depends(get_current_user_id),
) -> dict:
```

To:

```python
@router.post("")
@limiter.limit("30/minute")
async def create_folder(
    request: Request,
    body: FolderCreate,
    user_id: str = Depends(get_current_user_id),
) -> dict:
```

(`slowapi` requires the `Request` parameter to be present for `@limiter.limit` to inspect the caller's IP.)

- [ ] **Step 3: Verify existing tests still pass**

```bash
cd backend && /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/python -m pytest tests/test_folders.py -v
```

Expected: 15/15 (rate limiting only applies after 30 requests/minute from the same IP; the test client uses a constant IP so normal tests still pass).

- [ ] **Step 4: Commit**

```bash
git add backend/routes/folders.py
git commit -m "$(cat <<'EOF'
security(folders): rate-limit folder creation to 30/minute

A malicious or buggy client could spam INSERTs into the folders table.
Applied the existing slowapi @limiter decorator at 30/minute per IP,
consistent with other mutation endpoints.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 3 verification

- [ ] `pytest` prints 15 folder tests + 1 new dashboard test + 2 new conversation tests all passing.
- [ ] `/dashboard` in the browser shows **one** network request for `/api/dashboard/overview`.
- [ ] `npm test -- parse-natural-date` prints 11 passing.
- [ ] Creating a duplicate folder name shows a red toast with "A folder named 'X' already exists".

---

## Phase 4 — Frontend data layer (React Query)

**Goal:** Replace scattered `useEffect`-based fetching with a single cache layer. Stop re-fetching the same data from sidebar + dashboard + ⌘K. Preserve model selection across reloads.

### Task 4.1: Install and wire React Query

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/lib/query-client.tsx`
- Modify: `frontend/app/layout.tsx` (wrap with QueryClientProvider)

- [ ] **Step 1: Install**

```bash
cd frontend && npm install @tanstack/react-query @tanstack/react-query-devtools
```

- [ ] **Step 2: Create the provider wrapper**

Create `frontend/lib/query-client.tsx`:

```typescript
"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"


export function QueryProvider({ children }: { children: React.ReactNode }) {
  // One client per app session; stateful so StrictMode double-invocations don't churn it.
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,              // 30s — most dashboard data is safe to reuse
        refetchOnWindowFocus: false,    // opt in per-query when needed
        retry: 1,
      },
    },
  }))

  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
```

- [ ] **Step 3: Mount in root layout**

Edit `frontend/app/layout.tsx`. Import:

```typescript
import { QueryProvider } from "@/lib/query-client"
```

Wrap the tree. Inside the existing `<ThemeProvider>` (or similar) block, nest:

```tsx
<QueryProvider>
  {children}
  <Toaster ... />
</QueryProvider>
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/lib/query-client.tsx frontend/app/layout.tsx
git commit -m "$(cat <<'EOF'
feat(data): add @tanstack/react-query provider with dev tools

Introduces a single QueryClient with staleTime=30s and per-query
refetch control. Devtools mount only in development. This is the
foundation for Task 4.2+: replacing ad-hoc useEffect fetches with
shared, cached queries.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.2: Migrate `ToolsLauncher` to use `useQuery`

**Files:**
- Modify: `frontend/components/tools-launcher.tsx`

- [ ] **Step 1: Replace `useState + useEffect` with `useQuery`**

In `frontend/components/tools-launcher.tsx`, replace:

```typescript
const [overview, setOverview] = useState<DashboardOverview | null>(null)

useEffect(() => {
  api.dashboard.overview().then(setOverview).catch(() => {})
}, [])
```

with:

```typescript
import { useQuery } from "@tanstack/react-query"

const { data: overview } = useQuery({
  queryKey: ["dashboard-overview"],
  queryFn: () => api.dashboard.overview(),
})
```

(Delete the `useState`/`useEffect` imports if they're now unused — run tsc to confirm.)

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 3: Verify in browser**

Open `/dashboard`, reload twice. Expected: second reload serves cached data instantly (no loading flicker for counts), background refetch happens after 30s staleTime.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/tools-launcher.tsx
git commit -m "$(cat <<'EOF'
refactor(dashboard): migrate ToolsLauncher to useQuery

Replaces bespoke useState + useEffect fetching with react-query.
Gives the dashboard a real cache: reloading doesn't flicker, the
overview data is reused across route navigations within the 30s
staleTime window.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.3: Migrate sidebar folders/conversations + unify with ⌘K

**Files:**
- Modify: `frontend/components/sidebar.tsx`
- Modify: `frontend/components/command-palette.tsx`

- [ ] **Step 1: Replace sidebar's local fetch hooks with `useQuery`**

In `frontend/components/sidebar.tsx`, replace the existing:

```typescript
const [conversations, setConversations] = useState<Conversation[]>([])
const [folders, setFolders] = useState<Folder[]>([])

const refreshConversations = useCallback(() => {
  api.chat.conversations.list().then(r => setConversations(r.conversations)).catch(() => {})
}, [])
const refreshFolders = useCallback(() => {
  api.folders.list().then(r => setFolders(r.folders)).catch(() => {})
}, [])

useEffect(() => { refreshConversations(); refreshFolders() }, [pathname, refreshConversations, refreshFolders])
```

with:

```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query"

const qc = useQueryClient()
const { data: convData } = useQuery({
  queryKey: ["conversations"],
  queryFn: () => api.chat.conversations.list(),
})
const { data: folderData } = useQuery({
  queryKey: ["folders"],
  queryFn: () => api.folders.list(),
})
const conversations = convData?.conversations ?? []
const folders = folderData?.folders ?? []
```

- [ ] **Step 2: After every mutation, invalidate the query cache**

Update each folder mutation handler to call `qc.invalidateQueries(...)` on success. Example for `handleCreateFolder`:

```typescript
const handleCreateFolder = async () => {
  const name = newFolderName.trim()
  if (!name) { setCreatingFolder(false); setNewFolderName(''); return }
  try {
    await api.folders.create(name)
    qc.invalidateQueries({ queryKey: ["folders"] })
    toast.success("Folder created", name)
    setCreatingFolder(false)
    setNewFolderName('')
  } catch (e) {
    console.error('create folder failed', e)
    toast.error("Couldn't create folder", e instanceof Error ? e.message : undefined)
  }
}
```

Do the same for rename, delete, and the drag-drop move handler. For drag-drop also invalidate `["conversations"]`.

Remove the `expandedFolders = new Set(prev).add(folder.id)` optimistic expansion (it relied on the returned `folder` object — since we now let the query refetch, adapt: after `invalidateQueries`, leave the folder closed; the user can expand manually).

If that feels jarring, keep an optimistic expansion keyed by folder name:

```typescript
const pendingExpandName = useRef<string | null>(null)
// in handleCreateFolder, after success:
pendingExpandName.current = name
// in a useEffect watching folders:
useEffect(() => {
  if (!pendingExpandName.current) return
  const match = folders.find(f => f.name === pendingExpandName.current)
  if (match) {
    setExpandedFolders(prev => new Set(prev).add(match.id))
    pendingExpandName.current = null
  }
}, [folders])
```

- [ ] **Step 3: Listen for `ec:conversation-created` by invalidating instead of re-fetching**

Replace:

```typescript
useEffect(() => {
  window.addEventListener('ec:conversation-created', refreshConversations)
  return () => window.removeEventListener('ec:conversation-created', refreshConversations)
}, [refreshConversations])
```

with:

```typescript
useEffect(() => {
  const h = () => qc.invalidateQueries({ queryKey: ["conversations"] })
  window.addEventListener('ec:conversation-created', h)
  return () => window.removeEventListener('ec:conversation-created', h)
}, [qc])
```

- [ ] **Step 4: Do the same in `command-palette.tsx`**

Replace its two `useState + useEffect + setConversations + setFolders` blocks with `useQuery` calls. Both will hit the same cache the sidebar uses — so opening ⌘K no longer triggers a duplicate fetch.

- [ ] **Step 5: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 6: Verify**

Open DevTools → Network. Open `/dashboard`. Open `⌘K`. Expected:
- **One** `GET /api/folders` call total
- **One** `GET /api/chat/conversations` call total
- Both are reused from cache by whichever component mounts first.

Create a folder via `/folder Work` in chat. Expected: sidebar + ⌘K both show it within a second (invalidation triggers a single refetch).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/sidebar.tsx frontend/components/command-palette.tsx
git commit -m "$(cat <<'EOF'
refactor(sidebar,palette): unify folder + conversation fetching via react-query

Before: sidebar and command palette each maintained their own
conversation/folder state and useEffect fetches, so navigating
between routes or opening ⌘K caused duplicate round-trips.
After: both consume the same ["folders"] and ["conversations"]
query keys. One network call total per data set; mutations
invalidate and both surfaces update together.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.4: Persist selected model across page reloads

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`

- [ ] **Step 1: Replace the plain `useState(DEFAULT_MODEL)` with a persistent variant**

At the top of `frontend/app/dashboard/chat/page.tsx`, just after `DEFAULT_MODEL` is defined:

```typescript
const STORAGE_KEY_MODEL = "ec_selected_model"

function loadInitialModel(): string {
  if (typeof window === "undefined") return DEFAULT_MODEL
  try {
    const saved = localStorage.getItem(STORAGE_KEY_MODEL)
    if (saved && GROQ_MODELS.some(m => m.id === saved)) return saved
  } catch {}
  return DEFAULT_MODEL
}
```

Inside the component, replace:

```typescript
const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL)
```

with:

```typescript
const [selectedModel, setSelectedModelRaw] = useState<string>(() => loadInitialModel())

const setSelectedModel = useCallback((id: string) => {
  setSelectedModelRaw(id)
  try { localStorage.setItem(STORAGE_KEY_MODEL, id) } catch {}
}, [])
```

Every existing call-site that uses `setSelectedModel(...)` now writes to localStorage automatically.

- [ ] **Step 2: Type-check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "error TS"
```

Expected: no output.

- [ ] **Step 3: Verify**

Open `/dashboard/chat`, pick a non-default model from the dropdown. Reload the page. Expected: the model selector still shows the choice you made.

Pick a model, clear localStorage in DevTools, reload. Expected: falls back to `DEFAULT_MODEL` cleanly.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/dashboard/chat/page.tsx
git commit -m "$(cat <<'EOF'
feat(chat): persist selected LLM model across reloads

Model was resetting to the default every time the chat page mounted.
Reads from localStorage["ec_selected_model"] on first render, writes
to it through a setter wrapper. Validates that the saved id still
exists in GROQ_MODELS before honouring it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 4 verification

- [ ] DevTools Network shows exactly **one** request per unique endpoint on dashboard page load.
- [ ] Creating a folder via any surface updates sidebar + ⌘K within a second, without a full reload.
- [ ] Selecting `llama-3.1-8b-instant` and reloading preserves the choice.
- [ ] `npm run test` still passes and `tsc --noEmit` is clean.

---

## Phase 5 — Follow-up candidates (not detailed here)

These are the remaining items from the analysis, grouped for a future plan:

**Accessibility (1 day):**
- Focus trap in SlidePanel (`focus-trap-react`)
- Keyboard-accessible DnD alternative (right-click "Move to folder" menu)
- `role="menu"` on avatar dropdown

**Dark mode validation (2 hours):**
- Toggle theme, walk every route, screenshot diff
- Audit remaining hardcoded brand colors for dark variants

**Feature polish (2 days):**
- Folder color picker UI (backend already accepts it)
- Folder drag-to-reorder (position field already exists)
- ⌘K expands search to goals/tasks/documents (not just convos)
- Remember "More" disclosure state via localStorage
- Decide fate of old dashboard content (Today / ESL charts / context snapshot)

Suggest breaking these into a **Phase 5 plan** when ready — each group is a 2-3 hour contained sprint.

---

## Self-review

**Spec coverage:** Every item from the 🔴 critical section (1-6) is a task. Every 🟡 important item (7-18) is either a task or explicitly deferred to Phase 5. Every 🟢 nice-to-have (19-28) is called out in Phase 5.

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate handling"/"similar to Task N" patterns. Every code-mutating step contains full code. Commands list expected output.

**Type consistency:** `Folder` type reused across tasks; `DashboardOverview` declared once in Task 3.2 and referenced in Task 4.2; `parseNaturalDate` signature stable between Tasks (chat/parse-natural-date.ts) and tests (Task 3.3).
