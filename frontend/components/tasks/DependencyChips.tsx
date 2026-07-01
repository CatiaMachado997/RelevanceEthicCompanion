'use client'

import { useEffect, useState, useCallback } from 'react'
import { X } from 'lucide-react'
import { tasksApi, TaskDependency } from '@/lib/api'
import { toast } from '@/lib/toast'

interface DependencyChipsProps {
  taskId: string
  onChange?: () => void
  refreshKey?: number
}

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  todo:        { bg: 'rgba(0,0,0,0.06)',       fg: '#525252' },
  in_progress: { bg: 'rgba(74,124,89,0.12)',   fg: '#4A7C59' },
  done:        { bg: 'rgba(0,0,0,0.04)',       fg: '#9e9e9e' },
  cancelled:   { bg: 'rgba(176,74,58,0.10)',   fg: '#B04A3A' },
}

function StatusPill({ status }: { status: string }) {
  const c = STATUS_COLORS[status] ?? STATUS_COLORS.todo
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded"
      style={{ background: c.bg, color: c.fg }}
    >
      {status.replace('_', ' ')}
    </span>
  )
}

function Chip({
  dep,
  onRemove,
}: {
  dep: TaskDependency
  onRemove: () => void
}) {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs"
      style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}
    >
      {dep.depth > 1 && (
        <span style={{ color: 'var(--ec-text-subtle)' }}>↳</span>
      )}
      <span style={{ color: 'var(--ec-text)' }}>{dep.title}</span>
      <StatusPill status={dep.status} />
      <button
        type="button"
        onClick={onRemove}
        className="w-4 h-4 flex items-center justify-center rounded hover:bg-black/5"
        aria-label={`Remove dependency ${dep.title}`}
      >
        <X size={10} style={{ color: 'var(--ec-text-subtle)' }} />
      </button>
    </div>
  )
}

export function DependencyChips({ taskId, onChange, refreshKey }: DependencyChipsProps) {
  const [blockers, setBlockers] = useState<TaskDependency[]>([])
  const [blockedBy, setBlockedBy] = useState<TaskDependency[]>([])
  const [loading, setLoading] = useState(false)

  const fetchDeps = useCallback(async () => {
    setLoading(true)
    try {
      const r = await tasksApi.listDependencies(taskId)
      setBlockers(r.blockers)
      setBlockedBy(r.blocked_by)
    } catch (e) {
      // Silent — section just shows empty state
      console.error('Failed to load dependencies', e)
    } finally {
      setLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    if (!taskId) return
    fetchDeps()
  }, [taskId, fetchDeps, refreshKey])

  const handleRemove = async (depId: string) => {
    try {
      await tasksApi.removeDependency(taskId, depId)
      await fetchDeps()
      onChange?.()
    } catch (e) {
      toast.error(
        'Could not remove dependency',
        e instanceof Error ? e.message : undefined,
      )
    }
  }

  const Section = ({
    label,
    items,
  }: {
    label: string
    items: TaskDependency[]
  }) => (
    <div className="space-y-1.5">
      <div
        className="text-xs font-medium uppercase tracking-widest"
        style={{ color: 'var(--ec-text-subtle)' }}
      >
        {label}
      </div>
      {items.length === 0 ? (
        <div className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>
          (none)
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map(d => (
            <Chip key={d.task_id} dep={d} onRemove={() => handleRemove(d.task_id)} />
          ))}
        </div>
      )}
    </div>
  )

  return (
    <div className="space-y-3">
      <Section label="Blocked by" items={blockers} />
      <Section label="Blocks" items={blockedBy} />
      {loading && (
        <div className="text-[10px]" style={{ color: 'var(--ec-text-subtle)' }}>
          Loading…
        </div>
      )}
    </div>
  )
}
