"use client"

/**
 * ProjectsPanelContent — contents of the Projects slide panel.
 *
 * Read-oriented. For each active project we show its task progress
 * (done / total). Clicking a project deep-links to its filtered task list.
 */

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, FolderOpen, Archive } from "lucide-react"
import { api, type Project, type Task } from "@/lib/api"


interface Props {
  onClose: () => void
}


interface ProjectWithTaskStats extends Project {
  open: number
  done: number
}


export function ProjectsPanelContent({ onClose }: Props) {
  const [projects, setProjects] = useState<ProjectWithTaskStats[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        // Fetch active projects and all tasks in parallel, then join locally.
        const [projRes, taskRes] = await Promise.all([
          api.projects.list('active'),
          api.tasks.list(),
        ])
        const projs = Array.isArray(projRes) ? projRes : []
        const tasks = Array.isArray(taskRes) ? taskRes : []

        // Index task counts by project_id in one pass.
        const stats = new Map<string, { open: number; done: number }>()
        for (const t of tasks as Task[]) {
          if (!t.project_id) continue
          const s = stats.get(t.project_id) ?? { open: 0, done: 0 }
          if (t.status === 'done') s.done += 1
          else if (t.status !== 'cancelled') s.open += 1
          stats.set(t.project_id, s)
        }

        const joined: ProjectWithTaskStats[] = projs.map(p => ({
          ...p,
          open: stats.get(p.id)?.open ?? 0,
          done: stats.get(p.id)?.done ?? 0,
        }))

        // Show active projects with open work first, then active-but-empty.
        joined.sort((a, b) => b.open - a.open)
        setProjects(joined)
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Could not load projects')
      }
    })()
  }, [])

  if (err) {
    return <p className="text-sm" style={{ color: "#B04A3A" }}>{err}</p>
  }

  if (projects === null) {
    return <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>Loading…</p>
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-10">
        <div
          className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
          style={{ background: "var(--ec-surface-2)" }}
        >
          <FolderOpen size={18} style={{ color: "var(--ec-text-muted)" }} />
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--ec-text)" }}>No active projects</p>
        <p className="text-xs mb-4" style={{ color: "var(--ec-text-muted)" }}>
          Group related tasks into a project to track progress as one unit.
        </p>
        <Link
          href="/dashboard/projects"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg text-xs font-medium"
          style={{ background: "#4a7c59", color: "#ffffff" }}
        >
          Open projects <ArrowRight size={13} />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {projects.map(p => {
        const total = p.open + p.done
        const pct = total > 0 ? Math.round((p.done / total) * 100) : 0
        return (
          <Link
            key={p.id}
            href={`/dashboard/tasks?project=${p.id}`}
            onClick={onClose}
            className="group flex flex-col gap-2 p-3 rounded-xl transition-colors hover:bg-[rgba(0,0,0,0.03)]"
            style={{ border: "1px solid var(--ec-card-border)" }}
          >
            <div className="flex items-start gap-2">
              <FolderOpen size={14} className="mt-0.5 shrink-0" style={{ color: "var(--ec-text-muted)" }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: "var(--ec-text)" }}>
                  {p.title}
                </p>
                {p.description && (
                  <p className="text-xs mt-0.5 line-clamp-1" style={{ color: "var(--ec-text-muted)" }}>
                    {p.description}
                  </p>
                )}
              </div>
              <span className="text-[11px] shrink-0 tabular-nums" style={{ color: "var(--ec-text-subtle)" }}>
                {p.open} open
              </span>
              <ArrowRight
                size={12}
                className="mt-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: "var(--ec-text-subtle)" }}
              />
            </div>

            {total > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--ec-surface-2)" }}>
                  <div
                    className="h-full transition-all"
                    style={{ width: `${pct}%`, background: "#4a7c59" }}
                  />
                </div>
                <span className="text-[10px] tabular-nums shrink-0" style={{ color: "var(--ec-text-subtle)" }}>
                  {p.done}/{total}
                </span>
              </div>
            )}
          </Link>
        )
      })}

      <div className="pt-3 mt-3 border-t text-center space-x-3" style={{ borderColor: "var(--ec-card-border)" }}>
        <Link
          href="/dashboard/projects"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-muted)" }}
        >
          Manage all <ArrowRight size={11} />
        </Link>
        <Link
          href="/dashboard/projects?status=archived"
          onClick={onClose}
          className="inline-flex items-center gap-1.5 text-xs"
          style={{ color: "var(--ec-text-subtle)" }}
        >
          <Archive size={10} /> Archived
        </Link>
      </div>
    </div>
  )
}
