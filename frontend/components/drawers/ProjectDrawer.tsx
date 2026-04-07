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

  const projectId = project?.id

  const loadTasks = useCallback(async () => {
    if (!projectId) return
    try {
      const data = await api.tasks.list({ project_id: projectId })
      setTasks(data)
    } catch (e) {
      setTaskError(e instanceof Error ? e.message : 'Failed to load tasks')
    }
  }, [projectId])

  useEffect(() => {
    if (open && projectId) loadTasks()
  }, [open, projectId, loadTasks])

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
      await loadTasks()
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
      await loadTasks()
    } catch {
      await loadTasks() // restore correct state
    }
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
        <label htmlFor="project-name" className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Name</label>
        <input
          id="project-name"
          className={field}
          style={fieldStyle}
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="Project name"
        />
      </div>

      {/* Description */}
      <div className="space-y-1.5">
        <label htmlFor="project-desc" className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Description</label>
        <textarea
          id="project-desc"
          className={`${field} resize-none`}
          style={{ ...fieldStyle, minHeight: 72 }}
          value={desc}
          onChange={e => setDesc(e.target.value)}
          placeholder="Optional description"
        />
      </div>

      {/* Status */}
      <div className="space-y-1.5">
        <label htmlFor="project-status" className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--ec-text-subtle)' }}>Status</label>
        <select
          id="project-status"
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
        {taskError && <p role="alert" className="text-xs" style={{ color: '#B04A3A' }}>{taskError}</p>}
      </div>
    </DrawerShell>
  )
}
