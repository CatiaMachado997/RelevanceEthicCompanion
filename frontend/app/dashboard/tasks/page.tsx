"use client"

import { useState, useEffect, useCallback } from 'react'
import { api, Task, ExtractedTask } from '@/lib/api'
import { CheckSquare, Trash2, AlertCircle, RefreshCw, Plus, Sparkles } from 'lucide-react'

function PriorityBadge({ priority }: { priority: number }) {
  if (priority >= 8) {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: 'rgba(176,74,58,0.08)', color: '#B04A3A', border: '1px solid rgba(176,74,58,0.25)' }}
      >
        High
      </span>
    )
  }
  if (priority >= 4) {
    return (
      <span
        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#fff8e1', color: '#8a6600', border: '1px solid #ffe082' }}
      >
        Medium
      </span>
    )
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: 'var(--ec-surface-2, #f5f2ef)', color: 'var(--ec-text-muted)', border: '1px solid var(--ec-card-border)' }}
    >
      Low
    </span>
  )
}

const STATUS_CYCLE: Record<Task['status'], Task['status']> = {
  todo: 'in_progress',
  in_progress: 'done',
  done: 'todo',
  cancelled: 'todo',
}

const STATUS_LABEL: Record<Task['status'], string> = {
  todo: 'Todo',
  in_progress: 'In Progress',
  done: 'Done',
  cancelled: 'Cancelled',
}

const GROUPS: Array<{ status: Task['status']; label: string }> = [
  { status: 'todo', label: 'Todo' },
  { status: 'in_progress', label: 'In Progress' },
  { status: 'done', label: 'Done' },
]

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)

  // Create form
  const [createTitle, setCreateTitle] = useState('')
  const [createDesc, setCreateDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // AI Extract section
  const [extractText, setExtractText] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<ExtractedTask[]>([])
  const [addingIdx, setAddingIdx] = useState<number | null>(null)

  const loadTasks = useCallback(async () => {
    try {
      const data = await api.tasks.list()
      setTasks(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadTasks() }, [loadTasks])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createTitle.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      const task = await api.tasks.create({
        title: createTitle.trim(),
        description: createDesc.trim() || undefined,
        source_origin: 'manual',
      })
      setTasks(prev => [task, ...prev])
      setCreateTitle('')
      setCreateDesc('')
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create task')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleStatus = async (task: Task) => {
    const nextStatus = STATUS_CYCLE[task.status]
    setTogglingId(task.id)
    try {
      const updated = await api.tasks.update(task.id, { status: nextStatus })
      setTasks(prev => prev.map(t => t.id === task.id ? updated : t))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update task')
    } finally {
      setTogglingId(null)
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await api.tasks.delete(id)
      setTasks(prev => prev.filter(t => t.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete task')
    } finally {
      setDeletingId(null)
    }
  }

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!extractText.trim()) return
    setExtracting(true)
    setExtractError(null)
    setSuggestions([])
    try {
      const result = await api.tasks.extract(extractText.trim())
      setSuggestions(result.suggestions || [])
    } catch (e) {
      setExtractError(e instanceof Error ? e.message : 'Extraction failed')
    } finally {
      setExtracting(false)
    }
  }

  const handleAddSuggestion = async (idx: number, suggestion: ExtractedTask) => {
    setAddingIdx(idx)
    try {
      const task = await api.tasks.create({
        title: suggestion.title,
        description: suggestion.description,
        priority: suggestion.priority,
        source_origin: 'ai_extract',
      })
      setTasks(prev => [task, ...prev])
      setSuggestions(prev => prev.filter((_, i) => i !== idx))
    } catch (e) {
      setExtractError(e instanceof Error ? e.message : 'Failed to add task')
    } finally {
      setAddingIdx(null)
    }
  }

  const tasksByStatus = (status: Task['status']) => tasks.filter(t => t.status === status)

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Page header */}
      <div>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--ec-text)' }}>Tasks</h2>
        <p className="text-sm mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
          Manage your tasks and extract new ones from text using AI.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(176,74,58,0.07)', border: '1px solid rgba(176,74,58,0.25)', color: '#B04A3A' }}
        >
          <div className="flex items-center gap-2">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="shrink-0 opacity-50 hover:opacity-100 transition-opacity text-base leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Create form */}
      <div
        className="px-4 py-4 rounded-xl"
        style={{
          background: 'var(--ec-card-bg)',
          border: '1px solid var(--ec-card-border)',
          boxShadow: 'var(--ec-card-shadow)',
        }}
      >
        <p className="text-xs font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--ec-text-subtle)' }}>
          New task
        </p>
        <form onSubmit={handleCreate} className="space-y-2">
          {createError && (
            <p className="text-xs" style={{ color: '#B04A3A' }}>{createError}</p>
          )}
          <input
            type="text"
            placeholder="Task title"
            value={createTitle}
            onChange={e => setCreateTitle(e.target.value)}
            required
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-surface-2, #f5f2ef)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={createDesc}
            onChange={e => setCreateDesc(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-surface-2, #f5f2ef)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
          <button
            type="submit"
            disabled={creating || !createTitle.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-opacity disabled:opacity-40"
            style={{ background: 'var(--ec-text)', color: 'var(--ec-sidebar-bg)' }}
          >
            {creating ? <RefreshCw size={13} className="animate-spin" /> : <Plus size={13} />}
            {creating ? 'Creating…' : 'Add task'}
          </button>
        </form>
      </div>

      {/* AI Extract section */}
      <div
        className="px-4 py-4 rounded-xl"
        style={{
          background: 'var(--ec-card-bg)',
          border: '1px solid var(--ec-card-border)',
          boxShadow: 'var(--ec-card-shadow)',
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={14} style={{ color: '#4A7C59' }} />
          <p className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
            AI Extract
          </p>
        </div>
        <p className="text-xs mb-3" style={{ color: 'var(--ec-text-muted)' }}>
          Paste any text (meeting notes, emails, etc.) and let AI extract actionable tasks.
        </p>
        <form onSubmit={handleExtract} className="space-y-2">
          {extractError && (
            <p className="text-xs" style={{ color: '#B04A3A' }}>{extractError}</p>
          )}
          <textarea
            placeholder="Paste text here to extract tasks…"
            value={extractText}
            onChange={e => setExtractText(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
            style={{
              background: 'var(--ec-surface-2, #f5f2ef)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
          <button
            type="submit"
            disabled={extracting || !extractText.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-opacity disabled:opacity-40"
            style={{ background: '#4A7C59', color: '#fff' }}
          >
            {extracting ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {extracting ? 'Extracting…' : 'Extract Tasks'}
          </button>
        </form>

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="mt-4 space-y-2">
            <p className="text-xs font-medium" style={{ color: 'var(--ec-text-subtle)' }}>
              {suggestions.length} suggestion{suggestions.length !== 1 ? 's' : ''} found
            </p>
            {suggestions.map((s, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between gap-3 px-3 py-2.5 rounded-lg"
                style={{
                  background: 'var(--ec-surface-2, #f5f2ef)',
                  border: '1px solid var(--ec-card-border)',
                }}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>{s.title}</p>
                  {s.description && (
                    <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>{s.description}</p>
                  )}
                </div>
                <button
                  onClick={() => handleAddSuggestion(idx, s)}
                  disabled={addingIdx === idx}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-opacity disabled:opacity-40 shrink-0"
                  style={{ background: '#4A7C59', color: '#fff' }}
                >
                  {addingIdx === idx ? <RefreshCw size={11} className="animate-spin" /> : <Plus size={11} />}
                  Add task
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Task list grouped by status */}
      <div>
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2" style={{ color: 'var(--ec-text-subtle)' }}>
            <RefreshCw size={16} className="animate-spin" />
            <span className="text-sm">Loading tasks…</span>
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
            >
              <CheckSquare size={20} style={{ color: 'var(--ec-text-subtle)' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No tasks yet</p>
              <p className="text-xs mt-0.5" style={{ color: 'var(--ec-text-subtle)' }}>
                Add a task above or extract them from text using AI.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {GROUPS.map(({ status, label }) => {
              const group = tasksByStatus(status)
              if (group.length === 0) return null
              return (
                <div key={status}>
                  <p className="text-xs font-medium uppercase tracking-wider mb-2" style={{ color: 'var(--ec-text-subtle)' }}>
                    {label} · {group.length}
                  </p>
                  <div className="space-y-2">
                    {group.map(task => (
                      <div
                        key={task.id}
                        className="flex items-start gap-3 px-4 py-3 rounded-xl"
                        style={{
                          background: 'var(--ec-card-bg)',
                          border: '1px solid var(--ec-card-border)',
                          boxShadow: 'var(--ec-card-shadow)',
                          opacity: task.status === 'done' ? 0.7 : 1,
                        }}
                      >
                        {/* Status toggle */}
                        <button
                          onClick={() => handleToggleStatus(task)}
                          disabled={togglingId === task.id}
                          className="mt-0.5 w-5 h-5 rounded flex items-center justify-center shrink-0 transition-opacity disabled:opacity-40 hover:opacity-70"
                          style={{
                            background: task.status === 'done' ? '#2d6a4f' : 'var(--ec-surface-2, #f5f2ef)',
                            border: `1px solid ${task.status === 'done' ? '#2d6a4f' : 'var(--ec-card-border)'}`,
                          }}
                          title={`Mark as ${STATUS_LABEL[STATUS_CYCLE[task.status]]}`}
                          aria-label={`Toggle status for ${task.title}`}
                        >
                          {togglingId === task.id ? (
                            <RefreshCw size={10} className="animate-spin" style={{ color: task.status === 'done' ? '#fff' : 'var(--ec-text-muted)' }} />
                          ) : task.status === 'done' ? (
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                              <path d="M2 5l2.5 2.5L8 3" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          ) : null}
                        </button>

                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className="text-sm font-medium"
                              style={{
                                color: 'var(--ec-text)',
                                textDecoration: task.status === 'done' ? 'line-through' : 'none',
                              }}
                            >
                              {task.title}
                            </span>
                            <PriorityBadge priority={task.priority} />
                            {task.source_origin === 'ai_extract' && (
                              <span
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium"
                                style={{ background: '#e8f4f0', color: '#4A7C59', border: '1px solid #c3dfd6' }}
                              >
                                <Sparkles size={8} />
                                AI
                              </span>
                            )}
                          </div>
                          {task.description && (
                            <p className="text-xs mt-0.5 line-clamp-2" style={{ color: 'var(--ec-text-muted)' }}>
                              {task.description}
                            </p>
                          )}
                        </div>

                        {/* Delete */}
                        <button
                          onClick={() => handleDelete(task.id)}
                          disabled={deletingId === task.id}
                          className="w-8 h-8 rounded-lg flex items-center justify-center transition-opacity disabled:opacity-40 hover:opacity-70 shrink-0"
                          style={{ background: 'var(--ec-surface-2, #f5f2ef)', border: '1px solid var(--ec-card-border)' }}
                          title="Delete task"
                          aria-label={`Delete ${task.title}`}
                        >
                          {deletingId === task.id
                            ? <RefreshCw size={13} className="animate-spin" style={{ color: 'var(--ec-text-muted)' }} />
                            : <Trash2 size={13} style={{ color: '#B04A3A' }} />
                          }
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
