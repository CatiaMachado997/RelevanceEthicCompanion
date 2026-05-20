'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { tasksApi, Task } from '@/lib/api'
import { toast } from '@/lib/toast'

interface AddDependencyDialogProps {
  taskId: string
  open: boolean
  onOpenChange: (o: boolean) => void
  onAdded?: () => void
}

export function AddDependencyDialog({
  taskId,
  open,
  onOpenChange,
  onAdded,
}: AddDependencyDialogProps) {
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [existingBlockerIds, setExistingBlockerIds] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [adding, setAdding] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setError(null)
    setLoading(true)
    Promise.all([tasksApi.list(), tasksApi.listDependencies(taskId)])
      .then(([tasks, deps]) => {
        setAllTasks(tasks)
        setExistingBlockerIds(new Set(deps.blockers.map(b => b.task_id)))
      })
      .catch(e => {
        setError(e instanceof Error ? e.message : 'Failed to load tasks')
      })
      .finally(() => setLoading(false))
  }, [open, taskId])

  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allTasks
      .filter(t => t.id !== taskId && !existingBlockerIds.has(t.id))
      .filter(t => (q ? t.title.toLowerCase().includes(q) : true))
      .slice(0, 50)
  }, [allTasks, taskId, existingBlockerIds, query])

  const handleAdd = async (candidateId: string) => {
    setAdding(candidateId)
    setError(null)
    try {
      await tasksApi.addDependency(taskId, candidateId)
      toast.success('Dependency added')
      onAdded?.()
      onOpenChange(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add dependency'
      setError(msg)
    } finally {
      setAdding(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add dependency</DialogTitle>
          <DialogDescription>
            Pick a task that blocks this one. Cycles are rejected.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <input
            autoFocus
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search tasks…"
            className="w-full rounded-xl px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--ec-surface-2)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />

          {error && (
            <div className="text-xs" style={{ color: '#B04A3A' }}>
              {error}
            </div>
          )}

          <div
            className="max-h-72 overflow-y-auto rounded-xl"
            style={{ border: '1px solid var(--ec-card-border)' }}
          >
            {loading ? (
              <div
                className="p-3 text-xs"
                style={{ color: 'var(--ec-text-subtle)' }}
              >
                Loading…
              </div>
            ) : candidates.length === 0 ? (
              <div
                className="p-3 text-xs"
                style={{ color: 'var(--ec-text-subtle)' }}
              >
                No matching tasks.
              </div>
            ) : (
              <ul className="divide-y" style={{ borderColor: 'var(--ec-card-border)' }}>
                {candidates.map(t => (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => handleAdd(t.id)}
                      disabled={adding !== null}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-black/5 disabled:opacity-40 transition-colors"
                      style={{ color: 'var(--ec-text)' }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate">{t.title}</span>
                        <span
                          className="text-[10px] uppercase tracking-wider shrink-0"
                          style={{ color: 'var(--ec-text-subtle)' }}
                        >
                          {t.status.replace('_', ' ')}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
