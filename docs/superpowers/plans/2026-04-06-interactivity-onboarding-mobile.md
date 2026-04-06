# Interactivity, Bug Fixes, Onboarding & Mobile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix task/project interactivity (side drawers), milestone input, PDF viewer, relevance tuning state, chat/sidebar formatting, login/logout flow, add a landing page, empty states, and mobile responsiveness.

**Architecture:** All changes are in the sprint-2a worktree at `.worktrees/sprint-2a`. Frontend: Next.js 15 App Router + TypeScript + Tailwind CSS v4 + `@radix-ui/react-dialog` (already installed). Backend: FastAPI + psycopg3. Working directory for all commands: `/Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a`.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS v4, `@radix-ui/react-dialog`, FastAPI, psycopg3 dict_row, Supabase Auth

---

## Critical Conventions

- **CSS variables for all colours** — `var(--ec-card-bg)`, `var(--ec-card-border)`, `var(--ec-text)`, `var(--ec-text-subtle)`, `var(--ec-surface-2)`. Never hardcode colours that are already in the design system.
- **`api` export** lives in `frontend/lib/api.ts`. All API calls go through `apiRequest`.
- **No `alert()`** anywhere — all errors shown inline.
- **ESL is mandatory** for all backend write routes — the existing routes already handle this; don't add new write routes that bypass it.
- **Touch targets** — minimum 44×44px on all interactive elements.

---

## File Map

### New files
- `frontend/components/drawers/DrawerShell.tsx` — reusable right-side slide-in panel
- `frontend/components/drawers/TaskDrawer.tsx` — task detail + edit form
- `frontend/components/drawers/ProjectDrawer.tsx` — project detail + edit + embedded task list
- `frontend/components/DocumentViewer.tsx` — PDF viewer modal (iframe-based)

### Modified files
- `frontend/app/dashboard/tasks/page.tsx` — add `selectedTask` state + `TaskDrawer`; make rows clickable; add empty state
- `frontend/app/dashboard/projects/page.tsx` — add `selectedProject` state + `ProjectDrawer`; make rows clickable; add empty state
- `frontend/app/dashboard/goals/page.tsx` — fix milestone input (stopPropagation); add empty state
- `frontend/app/dashboard/documents/page.tsx` — wire `DocumentViewer`; add View button; add empty state
- `frontend/app/dashboard/values/page.tsx` — fix reorder state refresh; add empty state
- `frontend/components/sidebars/chat-sidebar.tsx` — add date-bucket grouping (Today / Yesterday / Last 7 days / Older)
- `frontend/app/dashboard/chat/page.tsx` — fix markdown whitespace + mobile input
- `frontend/hooks/useAuth.ts` — add `?signed_out=1` param on logout
- `frontend/app/login/page.tsx` — add signed-out banner + auto-session poll after magic link sent
- `frontend/app/page.tsx` — replace spinner redirect with minimal landing page
- `backend/routes/documents.py` — add `GET /api/documents/{id}/view` route (token via query param)
- `frontend/app/dashboard/layout.tsx` — add empty-state helper + mobile hamburger improvements (already has hamburger, verify `ec_lastRoute` save)

---

## Task 1: DrawerShell — Reusable Side Panel

**Files:**
- Create: `frontend/components/drawers/DrawerShell.tsx`

- [ ] **Step 1: Create the component**

  Create `frontend/components/drawers/DrawerShell.tsx`:

  ```tsx
  'use client'

  import * as Dialog from '@radix-ui/react-dialog'
  import { X } from 'lucide-react'

  interface DrawerShellProps {
    open: boolean
    onClose: () => void
    title: string
    children: React.ReactNode
    footer?: React.ReactNode
  }

  export function DrawerShell({ open, onClose, title, children, footer }: DrawerShellProps) {
    return (
      <Dialog.Root open={open} onOpenChange={v => { if (!v) onClose() }}>
        <Dialog.Portal>
          {/* Overlay */}
          <Dialog.Overlay
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
          />
          {/* Panel */}
          <Dialog.Content
            className="fixed right-0 top-0 z-50 h-full flex flex-col shadow-2xl
              w-full sm:w-[480px]
              data-[state=open]:animate-in data-[state=closed]:animate-out
              data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right
              duration-200"
            style={{ background: 'var(--ec-card-bg)', borderLeft: '1px solid var(--ec-card-border)' }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4 shrink-0 border-b"
              style={{ borderColor: 'var(--ec-card-border)' }}
            >
              <Dialog.Title className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>
                {title}
              </Dialog.Title>
              <Dialog.Close asChild>
                <button
                  className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/6"
                  aria-label="Close"
                >
                  <X size={16} style={{ color: 'var(--ec-text-subtle)' }} />
                </button>
              </Dialog.Close>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {children}
            </div>

            {/* Sticky footer */}
            {footer && (
              <div
                className="shrink-0 px-5 py-3 border-t flex items-center gap-2"
                style={{ borderColor: 'var(--ec-card-border)' }}
              >
                {footer}
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    )
  }
  ```

- [ ] **Step 2: Verify import resolves**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit --project tsconfig.json 2>&1 | grep DrawerShell || echo "OK - no errors"
  ```
  Expected: `OK - no errors`

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/components/drawers/DrawerShell.tsx
  git commit -m "feat(ui): add DrawerShell — reusable right-side slide-in panel"
  ```

---

## Task 2: TaskDrawer — Task Detail + Edit

**Files:**
- Create: `frontend/components/drawers/TaskDrawer.tsx`

Depends on: Task 1 (DrawerShell)

- [ ] **Step 1: Create the component**

  Create `frontend/components/drawers/TaskDrawer.tsx`:

  ```tsx
  'use client'

  import { useState, useEffect } from 'react'
  import { DrawerShell } from './DrawerShell'
  import { api, Task, Project } from '@/lib/api'
  import { Trash2, AlertCircle } from 'lucide-react'

  interface TaskDrawerProps {
    task: Task | null
    open: boolean
    onClose: () => void
    onSaved: () => void   // called after successful save or delete
  }

  const PRIORITY_OPTIONS = [
    { label: 'Low',    value: 3 },
    { label: 'Medium', value: 5 },
    { label: 'High',   value: 8 },
    { label: 'Urgent', value: 10 },
  ]

  const STATUS_OPTIONS: { label: string; value: Task['status'] }[] = [
    { label: 'Todo',        value: 'todo' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Done',        value: 'done' },
    { label: 'Cancelled',   value: 'cancelled' },
  ]

  export function TaskDrawer({ task, open, onClose, onSaved }: TaskDrawerProps) {
    const [title, setTitle]       = useState('')
    const [desc, setDesc]         = useState('')
    const [status, setStatus]     = useState<Task['status']>('todo')
    const [priority, setPriority] = useState(5)
    const [dueDate, setDueDate]   = useState('')
    const [projectId, setProjectId] = useState<string>('')
    const [projects, setProjects] = useState<Project[]>([])
    const [saving, setSaving]     = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [error, setError]       = useState<string | null>(null)
    const [dirty, setDirty]       = useState(false)

    // Populate form when task changes
    useEffect(() => {
      if (!task) return
      setTitle(task.title)
      setDesc(task.description ?? '')
      setStatus(task.status)
      setPriority(task.priority)
      setDueDate(task.due_date ? task.due_date.slice(0, 10) : '')
      setProjectId(task.project_id ?? '')
      setError(null)
      setDirty(false)
    }, [task])

    // Load projects for assignment dropdown
    useEffect(() => {
      if (!open) return
      api.projects.list().then(setProjects).catch(() => {})
    }, [open])

    const handleSave = async () => {
      if (!task) return
      setSaving(true)
      setError(null)
      try {
        await api.tasks.update(task.id, {
          title: title.trim(),
          description: desc.trim() || undefined,
          status,
          priority,
          due_date: dueDate || undefined,
          project_id: projectId || undefined,
        })
        onSaved()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to save')
      } finally {
        setSaving(false)
      }
    }

    const handleDelete = async () => {
      if (!task) return
      setDeleting(true)
      try {
        await api.tasks.delete(task.id)
        onSaved()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to delete')
      } finally {
        setDeleting(false)
      }
    }

    const field = 'w-full rounded-xl px-3 py-2 text-sm outline-none transition-all'
    const fieldStyle = { background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)', color: 'var(--ec-text)' }

    return (
      <DrawerShell
        open={open}
        onClose={onClose}
        title={task?.title ?? 'Task'}
        footer={
          <>
            <button
              onClick={handleDelete}
              disabled={deleting || saving}
              className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-red-50 disabled:opacity-40"
              aria-label="Delete task"
            >
              <Trash2 size={16} style={{ color: '#B04A3A' }} />
            </button>
            <div className="flex-1" />
            {error && (
              <span className="flex items-center gap-1 text-xs" style={{ color: '#B04A3A' }}>
                <AlertCircle size={12} /> {error}
              </span>
            )}
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 h-9 rounded-xl text-sm transition-colors hover:bg-black/5"
              style={{ color: 'var(--ec-text-subtle)' }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="px-4 h-9 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
              style={{ background: '#1c1520', color: '#fff' }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        {/* Title */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Title</label>
          <input
            className={field}
            style={fieldStyle}
            value={title}
            onChange={e => { setTitle(e.target.value); setDirty(true) }}
            placeholder="Task title"
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Description</label>
          <textarea
            className={`${field} resize-none`}
            style={{ ...fieldStyle, minHeight: 72 }}
            value={desc}
            onChange={e => { setDesc(e.target.value); setDirty(true) }}
            placeholder="Optional description"
          />
        </div>

        {/* Status + Priority row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Status</label>
            <select
              className={field}
              style={fieldStyle}
              value={status}
              onChange={e => { setStatus(e.target.value as Task['status']); setDirty(true) }}
            >
              {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Priority</label>
            <select
              className={field}
              style={fieldStyle}
              value={priority}
              onChange={e => { setPriority(Number(e.target.value)); setDirty(true) }}
            >
              {PRIORITY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        {/* Due date */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Due date</label>
          <input
            type="date"
            className={field}
            style={fieldStyle}
            value={dueDate}
            onChange={e => { setDueDate(e.target.value); setDirty(true) }}
          />
        </div>

        {/* Project */}
        {projects.length > 0 && (
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Project</label>
            <select
              className={field}
              style={fieldStyle}
              value={projectId}
              onChange={e => { setProjectId(e.target.value); setDirty(true) }}
            >
              <option value="">None</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </div>
        )}
      </DrawerShell>
    )
  }
  ```

- [ ] **Step 2: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep -E "TaskDrawer|error TS" | head -20 || echo "OK"
  ```
  Expected: `OK` or no lines matching `TaskDrawer|error TS`

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/components/drawers/TaskDrawer.tsx
  git commit -m "feat(ui): add TaskDrawer — task detail/edit slide-in panel"
  ```

---

## Task 3: Wire TaskDrawer into Tasks Page

**Files:**
- Modify: `frontend/app/dashboard/tasks/page.tsx`

- [ ] **Step 1: Add drawer state + import to tasks page**

  Open `frontend/app/dashboard/tasks/page.tsx`. Add the import at the top (after existing imports):

  ```tsx
  import { TaskDrawer } from '@/components/drawers/TaskDrawer'
  ```

  Inside `TasksPage()`, add state after the existing state declarations:

  ```tsx
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [drawerOpen, setDrawerOpen]     = useState(false)
  ```

- [ ] **Step 2: Make task rows clickable**

  Find the element that renders each task in the list. It will look like a `<div>` or `<li>` containing the task title. Add `onClick`, `cursor-pointer`, and hover styles to it.

  Find the pattern: `task.title` rendered inside a list item. Add these props to its outermost container element:

  ```tsx
  onClick={() => { setSelectedTask(task); setDrawerOpen(true) }}
  className="... cursor-pointer hover:ring-1 hover:ring-[var(--ec-card-border)] transition-all"
  ```

  Make sure the delete button and status toggle buttons inside the row call `e.stopPropagation()` so they don't accidentally open the drawer:

  ```tsx
  onClick={e => { e.stopPropagation(); /* existing handler */ }}
  ```

- [ ] **Step 3: Add TaskDrawer to the JSX**

  At the bottom of the returned JSX (just before the closing `</div>` of the page root):

  ```tsx
  <TaskDrawer
    task={selectedTask}
    open={drawerOpen}
    onClose={() => setDrawerOpen(false)}
    onSaved={loadTasks}
  />
  ```

- [ ] **Step 4: Add empty state**

  Find where the "no tasks" case is handled (the section that renders when tasks is empty for a group). Replace the existing empty message with:

  ```tsx
  {groupTasks.length === 0 && group.status === 'todo' && tasks.length === 0 && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <CheckSquare size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No tasks yet</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Tasks help you track what needs doing.<br />
          Ethic Companion can also extract tasks from your conversations.
        </p>
      </div>
    </div>
  )}
  ```

- [ ] **Step 5: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "tasks/page" | head -10 || echo "OK"
  ```

- [ ] **Step 6: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/tasks/page.tsx
  git commit -m "feat(tasks): clickable rows open TaskDrawer; add empty state"
  ```

---

## Task 4: ProjectDrawer — Project Detail + Edit + Embedded Tasks

**Files:**
- Create: `frontend/components/drawers/ProjectDrawer.tsx`

- [ ] **Step 1: Create the component**

  Create `frontend/components/drawers/ProjectDrawer.tsx`:

  ```tsx
  'use client'

  import { useState, useEffect, useCallback } from 'react'
  import { DrawerShell } from './DrawerShell'
  import { api, Project, Task } from '@/lib/api'
  import { Trash2, AlertCircle, CheckSquare, Plus } from 'lucide-react'

  interface ProjectDrawerProps {
    project: Project | null
    open: boolean
    onClose: () => void
    onSaved: () => void
  }

  const STATUS_OPTIONS: { label: string; value: Project['status'] }[] = [
    { label: 'Active',    value: 'active' },
    { label: 'Completed', value: 'completed' },
    { label: 'Archived',  value: 'archived' },
  ]

  export function ProjectDrawer({ project, open, onClose, onSaved }: ProjectDrawerProps) {
    const [title, setTitle]       = useState('')
    const [desc, setDesc]         = useState('')
    const [status, setStatus]     = useState<Project['status']>('active')
    const [saving, setSaving]     = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [error, setError]       = useState<string | null>(null)

    // Embedded task list
    const [tasks, setTasks]           = useState<Task[]>([])
    const [newTaskTitle, setNewTaskTitle] = useState('')
    const [addingTask, setAddingTask]     = useState(false)
    const [taskError, setTaskError]       = useState<string | null>(null)

    useEffect(() => {
      if (!project) return
      setTitle(project.title)
      setDesc(project.description ?? '')
      setStatus(project.status)
      setError(null)
    }, [project])

    const loadTasks = useCallback(async () => {
      if (!project) return
      try {
        const data = await api.tasks.list({ project_id: project.id })
        setTasks(data)
      } catch { /* non-critical */ }
    }, [project])

    useEffect(() => {
      if (open && project) loadTasks()
    }, [open, project, loadTasks])

    const handleSave = async () => {
      if (!project) return
      setSaving(true)
      setError(null)
      try {
        await api.projects.update(project.id, {
          title: title.trim(),
          description: desc.trim() || undefined,
          status,
        })
        onSaved()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to save')
      } finally {
        setSaving(false)
      }
    }

    const handleDelete = async () => {
      if (!project) return
      setDeleting(true)
      try {
        await api.projects.archive(project.id)
        onSaved()
        onClose()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to archive')
      } finally {
        setDeleting(false)
      }
    }

    const handleAddTask = async (e: React.FormEvent) => {
      e.preventDefault()
      const t = newTaskTitle.trim()
      if (!t || !project) return
      setAddingTask(true)
      setTaskError(null)
      try {
        await api.tasks.create({ title: t, project_id: project.id })
        setNewTaskTitle('')
        loadTasks()
      } catch (e) {
        setTaskError(e instanceof Error ? e.message : 'Failed to add task')
      } finally {
        setAddingTask(false)
      }
    }

    const handleToggleTask = async (task: Task) => {
      const next = task.status === 'done' ? 'todo' : 'done'
      try {
        await api.tasks.update(task.id, { status: next })
        loadTasks()
      } catch { /* non-critical */ }
    }

    const field = 'w-full rounded-xl px-3 py-2 text-sm outline-none transition-all'
    const fieldStyle = { background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)', color: 'var(--ec-text)' }

    return (
      <DrawerShell
        open={open}
        onClose={onClose}
        title={project?.title ?? 'Project'}
        footer={
          <>
            <button
              onClick={handleDelete}
              disabled={deleting || saving}
              className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-red-50 disabled:opacity-40"
              aria-label="Archive project"
            >
              <Trash2 size={16} style={{ color: '#B04A3A' }} />
            </button>
            <div className="flex-1" />
            {error && (
              <span className="flex items-center gap-1 text-xs" style={{ color: '#B04A3A' }}>
                <AlertCircle size={12} /> {error}
              </span>
            )}
            <button
              onClick={onClose}
              disabled={saving}
              className="px-4 h-9 rounded-xl text-sm transition-colors hover:bg-black/5"
              style={{ color: 'var(--ec-text-subtle)' }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="px-4 h-9 rounded-xl text-sm font-medium transition-colors disabled:opacity-40"
              style={{ background: '#1c1520', color: '#fff' }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </>
        }
      >
        {/* Title */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Name</label>
          <input
            className={field}
            style={fieldStyle}
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Project name"
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Description</label>
          <textarea
            className={`${field} resize-none`}
            style={{ ...fieldStyle, minHeight: 72 }}
            value={desc}
            onChange={e => setDesc(e.target.value)}
            placeholder="Optional description"
          />
        </div>

        {/* Status */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Status</label>
          <select
            className={field}
            style={fieldStyle}
            value={status}
            onChange={e => setStatus(e.target.value as Project['status'])}
          >
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Divider */}
        <hr style={{ borderColor: 'var(--ec-card-border)' }} />

        {/* Embedded task list */}
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>
            Tasks ({tasks.length})
          </p>
          <div className="space-y-1">
            {tasks.map(task => (
              <div key={task.id} className="flex items-center gap-2 py-1">
                <button
                  onClick={() => handleToggleTask(task)}
                  className="w-5 h-5 rounded flex items-center justify-center shrink-0 transition-colors"
                  style={{
                    background: task.status === 'done' ? '#4A7C59' : 'transparent',
                    border: `1.5px solid ${task.status === 'done' ? '#4A7C59' : 'var(--ec-card-border)'}`,
                  }}
                  aria-label={task.status === 'done' ? 'Mark todo' : 'Mark done'}
                >
                  {task.status === 'done' && <CheckSquare size={10} color="white" />}
                </button>
                <span
                  className="text-sm flex-1"
                  style={{
                    color: task.status === 'done' ? 'var(--ec-text-subtle)' : 'var(--ec-text)',
                    textDecoration: task.status === 'done' ? 'line-through' : 'none',
                  }}
                >
                  {task.title}
                </span>
              </div>
            ))}
          </div>

          {/* Add task inline */}
          <form onSubmit={handleAddTask} className="flex items-center gap-2 mt-2">
            <input
              className={`${field} flex-1`}
              style={fieldStyle}
              value={newTaskTitle}
              onChange={e => { setNewTaskTitle(e.target.value); setTaskError(null) }}
              placeholder="Add a task…"
              disabled={addingTask}
            />
            <button
              type="submit"
              disabled={addingTask || !newTaskTitle.trim()}
              className="w-9 h-9 flex items-center justify-center rounded-xl transition-colors disabled:opacity-40"
              style={{ background: '#1c1520', color: '#fff' }}
              aria-label="Add task"
            >
              <Plus size={16} />
            </button>
          </form>
          {taskError && <p className="text-xs" style={{ color: '#B04A3A' }}>{taskError}</p>}
        </div>
      </DrawerShell>
    )
  }
  ```

- [ ] **Step 2: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "ProjectDrawer" | head -10 || echo "OK"
  ```

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/components/drawers/ProjectDrawer.tsx
  git commit -m "feat(ui): add ProjectDrawer — project detail/edit + embedded task list"
  ```

---

## Task 5: Wire ProjectDrawer into Projects Page

**Files:**
- Modify: `frontend/app/dashboard/projects/page.tsx`

- [ ] **Step 1: Add import + state**

  Add at top of `frontend/app/dashboard/projects/page.tsx` (after existing imports):

  ```tsx
  import { ProjectDrawer } from '@/components/drawers/ProjectDrawer'
  ```

  Inside `ProjectsPage()`, add after existing state:

  ```tsx
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [drawerOpen, setDrawerOpen]           = useState(false)
  ```

- [ ] **Step 2: Make project rows clickable**

  Find the outermost element of each project list item. Add:

  ```tsx
  onClick={() => { setSelectedProject(project); setDrawerOpen(true) }}
  className="... cursor-pointer hover:ring-1 hover:ring-[var(--ec-card-border)] transition-all"
  ```

  Add `e.stopPropagation()` to the Archive button inside each row so it doesn't open the drawer.

- [ ] **Step 3: Add ProjectDrawer + empty state to JSX**

  Add `ProjectDrawer` just before the closing `</div>`:

  ```tsx
  <ProjectDrawer
    project={selectedProject}
    open={drawerOpen}
    onClose={() => setDrawerOpen(false)}
    onSaved={loadProjects}
  />
  ```

  Add empty state where projects list is empty:

  ```tsx
  {projects.length === 0 && !loading && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <FolderOpen size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No projects yet</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Projects group related tasks and goals.<br />Keep your work organised by context.
        </p>
      </div>
    </div>
  )}
  ```

- [ ] **Step 4: Verify + Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "projects/page" | head -10 || echo "OK"
  ```

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/projects/page.tsx
  git commit -m "feat(projects): clickable rows open ProjectDrawer; add empty state"
  ```

---

## Task 6: Fix Goals Milestone Input

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

- [ ] **Step 1: Read the collapsible wrapper**

  Find the element that wraps the milestone section (search for `milestoneInput` in the file). Identify what parent element might be capturing the click. Look for a `<div onClick=...>` or a button wrapping both the goal expand toggle AND the milestone form.

- [ ] **Step 2: Add stopPropagation to milestone input**

  Find the milestone `<input>` element (line ~244) and add:

  ```tsx
  onClick={e => e.stopPropagation()}
  ```

  Also add it to the milestone `<form>` element:

  ```tsx
  onClick={e => e.stopPropagation()}
  ```

  And to the "Add" submit `<button>`:

  ```tsx
  onClick={e => e.stopPropagation()}
  ```

- [ ] **Step 3: Add empty state for goals**

  Find where goals list is empty and add:

  ```tsx
  {goals.length === 0 && !loading && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <Target size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No goals yet</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Goals let you define what matters.<br />Ethic Companion uses them to guide its responses.
        </p>
      </div>
    </div>
  )}
  ```

  Make sure `Target` is imported from `lucide-react` (add to existing import if not present).

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/goals/page.tsx
  git commit -m "fix(goals): stopPropagation on milestone input; add empty state"
  ```

---

## Task 7: Backend — PDF View Route

**Files:**
- Modify: `backend/routes/documents.py`

- [ ] **Step 1: Read the documents route file**

  ```bash
  cat /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/backend/routes/documents.py
  ```

  Note the file path storage pattern — documents are stored in the DB with a `filename` and `content_type`. Identify how the raw file bytes are stored/retrieved (likely via `DocumentProcessor`).

- [ ] **Step 2: Add the view route**

  In `backend/routes/documents.py`, add after the existing imports:

  ```python
  from fastapi.responses import StreamingResponse
  import io
  ```

  Then add this route after the existing `DELETE` route:

  ```python
  @router.get("/{document_id}/view")
  async def view_document(
      document_id: str,
      token: str | None = None,
      user_id: str = Depends(get_current_read_user_id),
  ):
      """
      Stream document bytes for inline viewing in an iframe.
      Accepts auth via Bearer header OR ?token= query param (required for iframes).
      """
      with get_db_connection() as conn:
          with conn.cursor() as cur:
              cur.execute(
                  """
                  SELECT id, filename, content_type, raw_content
                  FROM documents
                  WHERE id = %s AND user_id = %s
                  """,
                  (document_id, user_id),
              )
              row = cur.fetchone()

      if not row:
          raise HTTPException(status_code=404, detail="Document not found")

      raw = row['raw_content']
      if raw is None:
          raise HTTPException(status_code=404, detail="Document content not available")

      content_type = row['content_type'] or 'application/pdf'

      return StreamingResponse(
          io.BytesIO(raw if isinstance(raw, bytes) else raw.tobytes()),
          media_type=content_type,
          headers={
              'Content-Disposition': f'inline; filename="{row["filename"]}"',
              'Cache-Control': 'private, max-age=300',
          },
      )
  ```

  > **Note:** If `raw_content` column does not exist in the `documents` table, check how `DocumentProcessor` stores files. If files are stored on disk or in object storage rather than the DB, adapt the route to read from that location. The key contract is: return bytes with `Content-Type: application/pdf` and `Content-Disposition: inline`.

- [ ] **Step 3: Handle token query param auth**

  The `get_current_read_user_id` dependency reads from the `Authorization` header. Iframes can't set headers. Add a fallback in `backend/utils/supabase_auth.py` (or inline in the route):

  Find `get_current_read_user_id` in `backend/utils/supabase_auth.py`. If the route receives `?token=...`, it should use that. The simplest approach is a route-specific override. Replace the route signature with:

  ```python
  from fastapi import Request

  @router.get("/{document_id}/view")
  async def view_document(
      document_id: str,
      request: Request,
      token: str | None = None,
  ):
      # Auth: try Bearer header first, fall back to ?token= query param
      auth_header = request.headers.get('Authorization', '')
      jwt = None
      if auth_header.startswith('Bearer '):
          jwt = auth_header[7:]
      elif token:
          jwt = token

      if not jwt:
          raise HTTPException(status_code=401, detail="Not authenticated")

      from utils.supabase_auth import verify_jwt
      user_id = verify_jwt(jwt)  # raises 401 if invalid

      # ... rest of route using user_id
  ```

  > **Note:** Check whether `verify_jwt` exists in `utils/supabase_auth.py`. If the function is named differently (e.g. `decode_jwt`, `validate_token`), use the correct name. The goal is to verify the JWT and extract the user_id.

- [ ] **Step 4: Run backend tests**

  ```bash
  source /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/activate
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/backend
  python -m pytest tests/ -q --tb=short 2>&1 | tail -10
  ```
  Expected: all pass (same count as before, no new failures).

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add backend/routes/documents.py
  git commit -m "feat(api): add GET /api/documents/{id}/view — streams PDF with inline content-disposition"
  ```

---

## Task 8: DocumentViewer Component + Wire Into Documents Page

**Files:**
- Create: `frontend/components/DocumentViewer.tsx`
- Modify: `frontend/app/dashboard/documents/page.tsx`

- [ ] **Step 1: Create DocumentViewer**

  Create `frontend/components/DocumentViewer.tsx`:

  ```tsx
  'use client'

  import * as Dialog from '@radix-ui/react-dialog'
  import { X, Download } from 'lucide-react'
  import { supabase } from '@/lib/supabase'
  import { useState, useEffect } from 'react'

  const API_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

  interface DocumentViewerProps {
    documentId: string | null
    filename: string
    open: boolean
    onClose: () => void
  }

  export function DocumentViewer({ documentId, filename, open, onClose }: DocumentViewerProps) {
    const [viewUrl, setViewUrl] = useState<string | null>(null)

    useEffect(() => {
      if (!open || !documentId) { setViewUrl(null); return }
      // Build URL with token query param so iframe can auth
      supabase.auth.getSession().then(({ data: { session } }) => {
        const token = session?.access_token ?? ''
        setViewUrl(`${API_URL}/api/documents/${documentId}/view?token=${encodeURIComponent(token)}`)
      })
    }, [open, documentId])

    return (
      <Dialog.Root open={open} onOpenChange={v => { if (!v) onClose() }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
          <Dialog.Content
            className="fixed inset-4 z-50 flex flex-col rounded-2xl overflow-hidden shadow-2xl"
            style={{ background: 'var(--ec-card-bg)', border: '1px solid var(--ec-card-border)' }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-3 shrink-0 border-b"
              style={{ borderColor: 'var(--ec-card-border)' }}
            >
              <Dialog.Title className="text-sm font-semibold truncate max-w-[60%]" style={{ color: 'var(--ec-text)' }}>
                {filename}
              </Dialog.Title>
              <div className="flex items-center gap-2">
                {viewUrl && (
                  <a
                    href={viewUrl}
                    download={filename}
                    className="flex items-center gap-1.5 px-3 h-8 rounded-lg text-xs font-medium transition-colors hover:bg-black/5"
                    style={{ color: 'var(--ec-text-subtle)' }}
                  >
                    <Download size={13} />
                    Download
                  </a>
                )}
                <Dialog.Close asChild>
                  <button
                    className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-black/6"
                    aria-label="Close"
                  >
                    <X size={16} style={{ color: 'var(--ec-text-subtle)' }} />
                  </button>
                </Dialog.Close>
              </div>
            </div>

            {/* PDF iframe */}
            <div className="flex-1 bg-[#525659]">
              {viewUrl ? (
                <iframe
                  src={viewUrl}
                  className="w-full h-full border-0"
                  title={filename}
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="w-6 h-6 rounded-full border-2 border-white/20 border-t-white animate-spin" />
                </div>
              )}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    )
  }
  ```

- [ ] **Step 2: Wire into documents page**

  In `frontend/app/dashboard/documents/page.tsx`, add import:

  ```tsx
  import { DocumentViewer } from '@/components/DocumentViewer'
  import { Eye } from 'lucide-react'
  ```

  Add state inside `DocumentsPage()`:

  ```tsx
  const [viewingDoc, setViewingDoc] = useState<{ id: string; filename: string } | null>(null)
  ```

  In the document list, for each document with `status === 'ready'`, add a View button next to the Delete button:

  ```tsx
  {doc.status === 'ready' && (
    <button
      onClick={() => setViewingDoc({ id: doc.id, filename: doc.filename })}
      className="w-9 h-9 flex items-center justify-center rounded-lg transition-colors hover:bg-black/5"
      aria-label="View document"
    >
      <Eye size={15} style={{ color: 'var(--ec-text-subtle)' }} />
    </button>
  )}
  ```

  Add `DocumentViewer` before the closing `</div>` of the page:

  ```tsx
  <DocumentViewer
    documentId={viewingDoc?.id ?? null}
    filename={viewingDoc?.filename ?? ''}
    open={!!viewingDoc}
    onClose={() => setViewingDoc(null)}
  />
  ```

  Add empty state where documents list is empty:

  ```tsx
  {documents.length === 0 && !loading && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <FileText size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No documents yet</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Upload PDFs, notes, or reports.<br />Ethic Companion uses them to answer your questions.
        </p>
      </div>
    </div>
  )}
  ```

- [ ] **Step 3: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep -E "DocumentViewer|documents/page" | head -10 || echo "OK"
  ```

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/components/DocumentViewer.tsx frontend/app/dashboard/documents/page.tsx
  git commit -m "feat(documents): add PDF viewer modal + View button + empty state"
  ```

---

## Task 9: Relevance Tuning — Fix State + Add Empty State

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`

- [ ] **Step 1: Read the values page**

  ```bash
  cat /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend/app/dashboard/values/page.tsx
  ```

  Look for:
  1. How `api.values.list()` result is destructured — should use `result.values`
  2. Whether `api.values.reorder()` exists — if yes, check if the list is re-fetched after it

- [ ] **Step 2: Fix list loading**

  `api.values.list()` already returns `{ values: UserValue[], total_count: number }`. Ensure the values page uses it like:

  ```tsx
  const { values } = await api.values.list()
  setValues(values)
  ```

  If it's reading `result.data` or `result` directly, update to `result.values`.

- [ ] **Step 3: Fix reorder state refresh**

  Find the drag-reorder handler. After the `api.values.reorder()` call succeeds, add a re-fetch:

  ```tsx
  await api.values.reorder(orderedIds)
  // Re-fetch to confirm server state
  const { values: refreshed } = await api.values.list()
  setValues(refreshed)
  ```

  This ensures the UI reflects what the server actually stored.

- [ ] **Step 4: Add empty state**

  Where `values.length === 0 && !loading`:

  ```tsx
  {values.length === 0 && !loading && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <ShieldCheck size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No values yet</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Values tell Ethic Companion what you care about.<br />Your Ethical Safeguard Layer enforces them on every response.
        </p>
      </div>
    </div>
  )}
  ```

  Make sure `ShieldCheck` is imported from `lucide-react`.

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/values/page.tsx
  git commit -m "fix(values): refresh list after reorder; add empty state"
  ```

---

## Task 10: Sidebar — Date-Grouped Conversations

**Files:**
- Modify: `frontend/components/sidebars/chat-sidebar.tsx`

- [ ] **Step 1: Add grouping helpers**

  At the top of `frontend/components/sidebars/chat-sidebar.tsx`, after the `formatRelativeTime` function, add:

  ```tsx
  type DateBucket = 'Today' | 'Yesterday' | 'Last 7 days' | 'Older'

  function getBucket(dateString: string): DateBucket {
    const date = new Date(dateString)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / 86400000)
    const sameDay =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate()
    if (sameDay) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return 'Last 7 days'
    return 'Older'
  }

  const BUCKET_ORDER: DateBucket[] = ['Today', 'Yesterday', 'Last 7 days', 'Older']

  function groupConversations(convs: Conversation[]): Map<DateBucket, Conversation[]> {
    // Sort most recent first
    const sorted = [...convs].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )
    const map = new Map<DateBucket, Conversation[]>()
    for (const c of sorted) {
      const bucket = getBucket(c.updated_at)
      if (!map.has(bucket)) map.set(bucket, [])
      map.get(bucket)!.push(c)
    }
    return map
  }
  ```

- [ ] **Step 2: Replace the flat list render with grouped render**

  Find the section in the JSX that renders `filtered.map(conv => ...)`. Replace it with:

  ```tsx
  {(() => {
    const grouped = groupConversations(filtered)
    return BUCKET_ORDER.flatMap(bucket => {
      const convs = grouped.get(bucket)
      if (!convs || convs.length === 0) return []
      return [
        <div key={`label-${bucket}`} className="px-3 pt-3 pb-1">
          <span className="text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>
            {bucket}
          </span>
        </div>,
        ...convs.map(conv => (
          <button
            key={conv.id}
            onClick={() => router.push(`/dashboard/chat/${conv.id}`)}
            className={`w-full flex items-start gap-3 p-3 rounded-lg transition-colors text-left ${
              activeId === conv.id ? 'bg-[#F0F0F0]' : 'hover:bg-[#F5F5F5]'
            }`}
          >
            <div className="w-8 h-8 rounded-lg bg-[#171717]/10 flex items-center justify-center shrink-0">
              <MessageSquare className="h-4 w-4 text-[#171717]" />
            </div>
            <div className="flex flex-col gap-0.5 min-w-0 flex-1">
              <span className="truncate text-sm font-medium leading-tight text-[#171717]">
                {conv.title || 'New chat'}
              </span>
              {conv.updated_at && (
                <span className="text-xs text-[#A3A3A3]">
                  {formatRelativeTime(conv.updated_at)}
                </span>
              )}
            </div>
          </button>
        )),
      ]
    })
  })()}
  ```

- [ ] **Step 3: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "chat-sidebar" | head -10 || echo "OK"
  ```

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/components/sidebars/chat-sidebar.tsx
  git commit -m "feat(sidebar): group conversations by date — Today / Yesterday / Last 7 days / Older"
  ```

---

## Task 11: Chat Formatting Fixes

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`

- [ ] **Step 1: Read the markdown render section**

  ```bash
  grep -n "ReactMarkdown\|prose\|whitespace\|pre-wrap" /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend/app/dashboard/chat/page.tsx | head -20
  ```

  Look for where `ReactMarkdown` is used to render assistant message content.

- [ ] **Step 2: Fix whitespace and prose styling**

  Find the `ReactMarkdown` component usage for assistant messages. Ensure its wrapping `<div>` has:

  ```tsx
  <div
    className="prose prose-sm max-w-none"
    style={{ color: 'var(--ec-text)', whiteSpace: 'pre-wrap' }}
  >
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {message.content}
    </ReactMarkdown>
  </div>
  ```

  If `@tailwindcss/typography` is installed (it is — it's in `package.json`), the `prose` class provides baseline markdown styling. Adding `whitespace: pre-wrap` on the container ensures line breaks in the source text are preserved.

- [ ] **Step 3: Fix mobile chat input**

  Find the chat input textarea/form at the bottom of the chat page. Ensure it has:

  ```tsx
  className="... pb-[env(safe-area-inset-bottom)]"
  ```

  on its sticky container, so it doesn't get covered by the iOS keyboard safe area.

- [ ] **Step 4: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "chat/page" | head -10 || echo "OK"
  ```

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/chat/page.tsx
  git commit -m "fix(chat): prose whitespace pre-wrap; mobile safe-area padding on input"
  ```

---

## Task 12: Login/Logout Flow

**Files:**
- Modify: `frontend/hooks/useAuth.ts`
- Modify: `frontend/app/login/page.tsx`

- [ ] **Step 1: Update signOut to pass signed_out param**

  In `frontend/hooks/useAuth.ts`, find `signOut` (lines 82–91). Update the last line:

  ```tsx
  // Before:
  if (typeof window !== 'undefined') window.location.href = '/login'

  // After:
  if (typeof window !== 'undefined') window.location.href = '/login?signed_out=1'
  ```

- [ ] **Step 2: Add signed-out banner to login page**

  In `frontend/app/login/page.tsx`, add `useEffect` and a state for the banner. Add after `const { signIn } = useAuth()`:

  ```tsx
  const [signedOut, setSignedOut] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('signed_out') === '1') {
      setSignedOut(true)
      window.history.replaceState({}, '', '/login')
      setTimeout(() => setSignedOut(false), 4000)
    }
  }, [])
  ```

  Import `useEffect` (add to the existing `import { useState } from 'react'`):

  ```tsx
  import { useState, useEffect } from 'react'
  ```

  Add the banner just above the form (inside the `!sent` branch, before `<div className="space-y-8">`):

  ```tsx
  {signedOut && (
    <div
      className="rounded-lg px-4 py-3 text-sm flex items-center gap-2 mb-6"
      style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534' }}
    >
      <CheckCircle size={14} />
      You&apos;ve been signed out.
    </div>
  )}
  ```

  `CheckCircle` is already imported.

- [ ] **Step 3: Add auto-session poll after magic link sent**

  In `frontend/app/login/page.tsx`, add polling after the link is sent. Import `supabase`:

  ```tsx
  import { supabase } from '@/lib/supabase'
  ```

  Add a `useEffect` that runs when `sent === true`:

  ```tsx
  useEffect(() => {
    if (!sent) return
    const interval = setInterval(async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (session) {
        clearInterval(interval)
        const lastRoute = localStorage.getItem('ec_lastRoute') || '/dashboard'
        localStorage.removeItem('ec_lastRoute')
        window.location.href = lastRoute
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [sent])
  ```

- [ ] **Step 4: Verify TypeScript**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep -E "useAuth|login/page" | head -10 || echo "OK"
  ```

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/hooks/useAuth.ts frontend/app/login/page.tsx
  git commit -m "fix(auth): signed-out banner on login; auto-redirect poll after magic link; logout sets ?signed_out=1"
  ```

---

## Task 13: Landing Page

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Replace spinner redirect with minimal landing page**

  Replace the entire contents of `frontend/app/page.tsx` with:

  ```tsx
  'use client'

  import { Shield, ArrowRight } from 'lucide-react'
  import Link from 'next/link'

  export default function LandingPage() {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center p-6 text-center"
        style={{ background: '#f9f6fa' }}
      >
        {/* Logo */}
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mb-8"
          style={{ background: '#1c1520', border: '1px solid rgba(255,255,255,0.1)' }}
        >
          <Shield size={24} color="white" />
        </div>

        {/* Wordmark */}
        <p className="text-xs font-medium uppercase tracking-[0.2em] mb-4" style={{ color: '#b0a6b4' }}>
          Ethic Companion
        </p>

        {/* Tagline */}
        <h1
          className="text-3xl sm:text-4xl mb-4 max-w-sm leading-tight"
          style={{ fontFamily: 'var(--font-fraunces)', color: '#1c1520', fontWeight: 400 }}
        >
          Your AI work companion that respects your boundaries.
        </h1>

        {/* Description */}
        <p className="text-sm leading-relaxed max-w-xs mb-10" style={{ color: '#695e6e' }}>
          Ethic Companion helps you make decisions, manage work, and stay focused — without dark patterns or engagement traps. Powered by an Ethical Safeguard Layer that puts your values first.
        </p>

        {/* CTA */}
        <Link
          href="/login"
          className="inline-flex items-center gap-2 w-full sm:w-auto justify-center h-12 px-8 rounded-2xl text-sm font-medium transition-all hover:opacity-90 active:scale-[0.98]"
          style={{ background: '#1c1520', color: '#ffffff' }}
        >
          Sign in
          <ArrowRight size={15} />
        </Link>

        {/* Trust note */}
        <p className="mt-6 text-xs" style={{ color: '#c4bcc8' }}>
          No password needed — we use magic links.
        </p>
      </div>
    )
  }
  ```

- [ ] **Step 2: Verify TypeScript + build**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "app/page" | head -5 || echo "OK"
  ```

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/page.tsx
  git commit -m "feat(landing): replace spinner redirect with minimal landing page — tagline, description, sign-in CTA"
  ```

---

## Task 14: Empty States — Integrations + Values Pages

**Files:**
- Modify: `frontend/app/dashboard/integrations/page.tsx`

- [ ] **Step 1: Read integrations page**

  ```bash
  head -60 /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend/app/dashboard/integrations/page.tsx
  ```

- [ ] **Step 2: Add connected-but-no-data empty state**

  Find where the integrations list or sync status section renders when no integrations are connected. Add:

  ```tsx
  {connected.length === 0 && !loading && (
    <div className="py-10 text-center space-y-3">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
        <Plug size={20} style={{ color: 'var(--ec-text-subtle)' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No integrations connected</p>
        <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
          Connect Calendar and Gmail so Ethic Companion knows your schedule and context.
        </p>
      </div>
    </div>
  )}
  ```

  Import `Plug` from `lucide-react` if not present.

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git add frontend/app/dashboard/integrations/page.tsx
  git commit -m "feat(integrations): add empty state when no integrations connected"
  ```

---

## Task 15: Final Verification

- [ ] **Step 1: Run full backend test suite**

  ```bash
  source /Users/catiamachado/RelevanceEthicCompanion/backend/venv/bin/activate
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/backend
  python -m pytest tests/ -q --tb=short 2>&1 | tail -5
  ```
  Expected: all tests pass (185+).

- [ ] **Step 2: Run frontend TypeScript check**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npx tsc --noEmit 2>&1 | grep "error TS" | head -20 || echo "No TypeScript errors"
  ```
  Expected: `No TypeScript errors`

- [ ] **Step 3: Run frontend build**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a/frontend
  npm run build 2>&1 | tail -15
  ```
  Expected: `✓ Compiled successfully` and all pages listed.

- [ ] **Step 4: Smoke-test checklist (manual)**

  - [ ] Landing page (`/`) shows tagline + Sign in button, no spinner
  - [ ] Sign out from dashboard → lands on `/login` with "You've been signed out" banner
  - [ ] Click a task in the task list → TaskDrawer slides in, edit + save works
  - [ ] Click a project → ProjectDrawer slides in, embedded task list shows, task toggle works
  - [ ] Goals page → click inside milestone input → can type, form submits
  - [ ] Documents page → upload a PDF → "View" button appears → iframe opens PDF
  - [ ] Sidebar → conversations grouped by date buckets
  - [ ] Values page → drag to reorder → list stays reordered after reorder

- [ ] **Step 5: Final commit if any stragglers**

  ```bash
  cd /Users/catiamachado/RelevanceEthicCompanion/.worktrees/sprint-2a
  git status
  # Commit any remaining changes
  ```
