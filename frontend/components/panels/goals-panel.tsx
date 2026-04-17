"use client"

/**
 * GoalsPanelContent — the contents of the Goals slide panel.
 *
 * Minimal read-oriented view that lives inside <SlidePanel>. Shows the
 * user's active goals and lets them open the full /dashboard/goals page
 * for deeper editing.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { Target, ArrowRight, CheckCircle, Circle } from "lucide-react"
import { api, type Goal } from "@/lib/api"


interface Props {
  onClose: () => void
}


export function GoalsPanelContent({ onClose }: Props) {
  const [goals, setGoals] = useState<Goal[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.goals.list('active')
      .then(r => setGoals(r.goals))
      .catch(e => setErr(e instanceof Error ? e.message : 'Could not load goals'))
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }

  if (goals === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  if (goals.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <Target size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No active goals</p>
        <p className="text-xs mb-4" style={{ color: "var(--ec-text-muted)" }}>
          Ask your companion to help you set one, or create it directly.
        </p>
        <Link
          href="/dashboard/goals"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          Open goals <ArrowRight size={13} />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {goals.map(g => (
        <Link
          key={g.id}
          href={`/dashboard/goals?goal=${g.id}`}
          onClick={onClose}
          className="group flex items-start gap-3 p-3 rounded-xl transition-colors hover:bg-[rgba(0,0,0,0.03)]"
          style={{ border: "1px solid var(--ec-card-border)" }}
        >
          <span className="shrink-0 mt-0.5">
            {g.status === 'completed'
              ? <CheckCircle size={15} style={{ color: "#4a7c59" }} />
              : <Circle size={15} style={{ color: "var(--ec-text-subtle)" }} />}
          </span>
          <span className="flex-1 min-w-0">
            <span className="block text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
              {g.title}
            </span>
            {g.description && (
              <span className="block text-xs mt-0.5 line-clamp-2" style={{ color: "var(--ec-text-muted)" }}>
                {g.description}
              </span>
            )}
            {typeof g.progress === "number" && (
              <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: "var(--ec-surface-2)" }}>
                <div
                  className="h-full transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, g.progress))}%`, background: "#4a7c59" }}
                />
              </div>
            )}
          </span>
          <ArrowRight
            size={13}
            className="shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ color: "var(--ec-text-subtle)" }}
          />
        </Link>
      ))}

      <div className="pt-3 mt-3 border-t text-center" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/goals"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Manage all goals <ArrowRight size={11} />
        </Link>
      </div>
    </div>
  )
}
