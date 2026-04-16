'use client'

import { useState, useEffect } from 'react'
import { DrawerShell } from './DrawerShell'
import { api, Task, Project } from '@/lib/api'
import { Trash2, AlertCircle } from 'lucide-react'

interface TaskDrawerProps {
  task: Task | null
  open: boolean
  onClose: () => void
  onSaved: () => void
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
            style={{ background: '#1a1a1a', color: '#fff' }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </>
      }
    >
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
