"use client"

/**
 * TasksPanelContent — the contents of the Tasks slide panel.
 *
 * Read-oriented view with a one-click "mark done" affordance for open tasks.
 * Deeper editing (rename, reschedule, reassign) lives on /dashboard/tasks.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowRight, CheckSquare, Square, Check, AlertTriangle, Flag,
} from "lucide-react"
import { api, type Task } from "@/lib/api"


interface Props {
  onClose: () => void
}


function isOverdue(t: Task): boolean {
  if (!t.due_date) return false
  return new Date(t.due_date) < new Date() && t.status !== 'done' && t.status !== 'cancelled'
}


function prettyDue(t: Task): string | null {
  if (!t.due_date) return null
  const d = new Date(t.due_date)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const dayDiff = Math.round((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  if (dayDiff === 0) return "Today"
  if (dayDiff === 1) return "Tomorrow"
  if (dayDiff === -1) return "Yesterday"
  if (dayDiff < 0) return `${-dayDiff}d overdue`
  if (dayDiff < 7) return `In ${dayDiff}d`
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}


export function TasksPanelContent({ onClose }: Props) {
  const [tasks, setTasks] = useState<Task[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  // Tracks in-flight mark-done requests so clicks feel responsive and can't double-fire.
  const [updating, setUpdating] = useState<Set<string>>(new Set())

  useEffect(() => {
    load()
  }, [])

  const load = () => {
    api.tasks.list()
      .then(res => {
        const arr = Array.isArray(res) ? res : []
        // Show open + in-progress first, then done, capped at a reasonable panel size
        const ordered = arr.slice().sort((a, b) => {
          const openA = a.status === 'done' || a.status === 'cancelled' ? 1 : 0
          const openB = b.status === 'done' || b.status === 'cancelled' ? 1 : 0
          if (openA !== openB) return openA - openB
          // Within open, overdue first
          const oA = isOverdue(a) ? 0 : 1
          const oB = isOverdue(b) ? 0 : 1
          if (oA !== oB) return oA - oB
          return (b.priority ?? 0) - (a.priority ?? 0)
        })
        setTasks(ordered.slice(0, 20))
      })
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load tasks'))
  }

  const toggleDone = async (t: Task) => {
    if (updating.has(t.id)) return
    setUpdating(prev => new Set(prev).add(t.id))
    const nextStatus: Task['status'] = t.status === 'done' ? 'todo' : 'done'
    // Optimistic
    setTasks(prev => prev?.map(x => x.id === t.id ? { ...x, status: nextStatus } : x) ?? null)
    try {
      await api.tasks.update(t.id, { status: nextStatus })
    } catch {
      // Revert on failure
      setTasks(prev => prev?.map(x => x.id === t.id ? t : x) ?? null)
    } finally {
      setUpdating(prev => {
        const n = new Set(prev); n.delete(t.id); return n
      })
    }
  }

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }

  if (tasks === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  const open = tasks.filter(t => t.status !== 'done' && t.status !== 'cancelled')
  const done = tasks.filter(t => t.status === 'done')
  const overdueCount = open.filter(isOverdue).length

  if (tasks.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <CheckSquare size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No tasks yet</p>
        <p className="text-xs mb-4" style={{ color: "var(--ec-text-muted)" }}>
          Ask your companion to extract tasks from what you&apos;re working on.
        </p>
        <Link
          href="/dashboard/tasks"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          Open tasks <ArrowRight size={13} />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Summary row */}
      <div className="flex items-center gap-3 text-xs">
        <span className="font-medium" style={{ color: "var(--ec-text)" }}>
          {open.length} open
        </span>
        {overdueCount > 0 && (
          <span
            className="flex items-center gap-1 px-2 py-0.5 rounded-full font-medium"
            style={{ background: "rgba(176,74,58,0.10)", color: "#B04A3A" }}
          >
            <AlertTriangle size={10} />
            {overdueCount} overdue
          </span>
        )}
        <span className="ml-auto" style={{ color: "var(--ec-text-subtle)" }}>
          {done.length} done
        </span>
      </div>

      {/* Open tasks */}
      {open.length > 0 && (
        <div className="space-y-1.5">
          {open.map(t => {
            const overdue = isOverdue(t)
            const due = prettyDue(t)
            const isUpdating = updating.has(t.id)
            return (
              <div
                key={t.id}
                className="group flex items-start gap-2.5 p-2.5 rounded-xl transition-colors hover:bg-[rgba(0,0,0,0.03)]"
                style={{ border: "1px solid var(--ec-card-border)" }}
              >
                <button
                  onClick={() => toggleDone(t)}
                  disabled={isUpdating}
                  className="mt-0.5 shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors hover:border-[#4a7c59] disabled:opacity-50"
                  style={{ borderColor: "var(--ec-border)" }}
                  aria-label="Mark as done"
                >
                  {t.status === 'in_progress' && (
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: "#4a7c59" }} />
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: "var(--ec-text)" }}>
                    {t.title}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px]">
                    {due && (
                      <span style={{ color: overdue ? "#B04A3A" : "var(--ec-text-subtle)" }}>
                        {due}
                      </span>
                    )}
                    {t.priority >= 2 && (
                      <span className="flex items-center gap-0.5" style={{ color: "#9B7A3D" }}>
                        <Flag size={9} />
                        High
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Done (collapsed look — simpler rows) */}
      {done.length > 0 && (
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider mb-1.5 px-1" style={{ color: "var(--ec-text-subtle)" }}>
            Completed
          </p>
          <div className="space-y-1">
            {done.slice(0, 5).map(t => (
              <div
                key={t.id}
                className="flex items-center gap-2.5 p-1.5 rounded-lg text-xs"
                style={{ color: "var(--ec-text-subtle)" }}
              >
                <button
                  onClick={() => toggleDone(t)}
                  disabled={updating.has(t.id)}
                  className="shrink-0 w-4 h-4 rounded flex items-center justify-center disabled:opacity-50"
                  style={{ background: "#4a7c59" }}
                  aria-label="Unmark"
                >
                  <Check size={10} color="#fff" strokeWidth={3} />
                </button>
                <span className="flex-1 truncate line-through">{t.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="pt-3 mt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/tasks"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Manage all tasks <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
