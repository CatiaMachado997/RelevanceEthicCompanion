"use client"

/**
 * ToolsLauncher
 *
 * A grid of tool cards for pages that are no longer in the main sidebar
 * (goals, tasks, projects, documents, values, transparency, notifications).
 * Each card shows a live count and links to the full page.
 *
 * Rendered on the dashboard home page as a launcher / overview.
 */

import Link from "next/link"
import { useEffect, useState } from "react"
import {
  Target, CheckSquare, FolderOpen, Heart, FileText, Eye, Bell,
  ArrowRight, PanelRight,
} from "lucide-react"
import { api } from "@/lib/api"


interface ToolCard {
  href: string
  title: string
  subtitle: string
  icon: React.ReactNode
  count: number | null        // null = loading or unavailable
  unit?: string               // e.g. "active", "open", "unread"
  accent?: string             // subtle icon background tint
  panelName?: "goals" | "tasks" | "projects" | "values" | "transparency" | "notifications" | "documents"  // if set, card shows a quick-peek button that opens a slide panel
}


export function ToolsLauncher() {
  const [goalsCount, setGoalsCount] = useState<number | null>(null)
  const [tasksCount, setTasksCount] = useState<number | null>(null)
  const [projectsCount, setProjectsCount] = useState<number | null>(null)
  const [valuesCount, setValuesCount] = useState<number | null>(null)
  const [documentsCount, setDocumentsCount] = useState<number | null>(null)
  const [transparencyCount, setTransparencyCount] = useState<number | null>(null)
  const [unreadNotifs, setUnreadNotifs] = useState<number | null>(null)

  useEffect(() => {
    // Fire all in parallel; each one handles its own failure quietly
    // (dashboard is resilient — missing counts just show as "—").
    api.goals.list('active')
      .then(r => setGoalsCount(r.total_count ?? r.goals?.length ?? 0))
      .catch(() => setGoalsCount(0))

    api.tasks.list({ status: 'open' }).then((tasks) => {
      // tasksApi.list returns Task[] directly
      const arr = Array.isArray(tasks) ? tasks : []
      setTasksCount(arr.length)
    }).catch(() => setTasksCount(0))

    api.projects.list('active').then((projects) => {
      const arr = Array.isArray(projects) ? projects : []
      setProjectsCount(arr.length)
    }).catch(() => setProjectsCount(0))

    api.values.list()
      .then(r => setValuesCount(r.total_count ?? (Array.isArray(r.values) ? r.values.length : 0)))
      .catch(() => setValuesCount(0))

    api.documents.list().then((docs) => {
      const arr = Array.isArray(docs) ? docs : []
      setDocumentsCount(arr.length)
    }).catch(() => setDocumentsCount(0))

    api.transparency.report()
      .then((r: { total_decisions?: number }) => setTransparencyCount(r?.total_decisions ?? 0))
      .catch(() => setTransparencyCount(0))

    api.notifications.count()
      .then(r => setUnreadNotifs(r?.unread_count ?? 0))
      .catch(() => setUnreadNotifs(0))
  }, [])

  const tools: ToolCard[] = [
    {
      href: "/dashboard/goals",
      title: "Goals",
      subtitle: "Long-term direction",
      icon: <Target size={16} />,
      count: goalsCount,
      unit: "active",
      accent: "rgba(74,124,89,0.10)",
      panelName: "goals",
    },
    {
      href: "/dashboard/tasks",
      title: "Tasks",
      subtitle: "This week's work",
      icon: <CheckSquare size={16} />,
      count: tasksCount,
      unit: "open",
      accent: "rgba(74,124,89,0.10)",
      panelName: "tasks",
    },
    {
      href: "/dashboard/projects",
      title: "Projects",
      subtitle: "Grouped initiatives",
      icon: <FolderOpen size={16} />,
      count: projectsCount,
      unit: "active",
      accent: "rgba(155,122,61,0.10)",
      panelName: "projects",
    },
    {
      href: "/dashboard/values",
      title: "Values",
      subtitle: "Your boundaries",
      icon: <Heart size={16} />,
      count: valuesCount,
      unit: "defined",
      accent: "rgba(155,122,61,0.10)",
      panelName: "values",
    },
    {
      href: "/dashboard/documents",
      title: "Documents",
      subtitle: "Uploaded files",
      icon: <FileText size={16} />,
      count: documentsCount,
      unit: "files",
      accent: "rgba(74,124,89,0.10)",
      panelName: "documents",
    },
    {
      href: "/dashboard/transparency",
      title: "Transparency",
      subtitle: "ESL audit log",
      icon: <Eye size={16} />,
      count: transparencyCount,
      unit: "decisions",
      accent: "rgba(74,124,89,0.10)",
      panelName: "transparency",
    },
    {
      href: "/dashboard/notifications",
      title: "Notifications",
      subtitle: "Activity alerts",
      icon: <Bell size={16} />,
      count: unreadNotifs,
      unit: unreadNotifs === 1 ? "unread" : "unread",
      accent: unreadNotifs && unreadNotifs > 0 ? "rgba(176,74,58,0.10)" : "rgba(74,124,89,0.10)",
      panelName: "notifications",
    },
  ]

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold" style={{ color: "var(--ec-text)" }}>
          Tools
        </h2>
        <p className="text-xs" style={{ color: "var(--ec-text-subtle)" }}>
          Not in the sidebar — click to open
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {tools.map(t => (
          <div
            key={t.href}
            className="group relative flex items-start gap-3 p-4 rounded-2xl transition-all hover:-translate-y-0.5"
            style={{
              background: "var(--ec-card-bg)",
              border: "1px solid var(--ec-card-border)",
              boxShadow: "var(--ec-card-shadow)",
            }}
          >
            {/* Peek-in-panel button — appears on hover for tools that support a slide panel */}
            {t.panelName && (
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  window.dispatchEvent(new CustomEvent("ec:open-panel", {
                    detail: { name: t.panelName, title: `Your ${t.title.toLowerCase()}` },
                  }))
                }}
                className="absolute top-2 right-2 w-6 h-6 rounded-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[rgba(0,0,0,0.06)]"
                title={`Peek at ${t.title.toLowerCase()} without leaving`}
                aria-label={`Peek at ${t.title}`}
              >
                <PanelRight size={12} style={{ color: "var(--ec-text-subtle)" }} />
              </button>
            )}

            <Link href={t.href} className="flex items-start gap-3 flex-1 min-w-0" aria-label={`Open ${t.title}`}>
              <span
                className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: t.accent, color: "var(--ec-text)" }}
              >
                {t.icon}
              </span>
              <span className="flex-1 min-w-0">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold truncate" style={{ color: "var(--ec-text)" }}>
                    {t.title}
                  </span>
                  <ArrowRight
                    size={12}
                    className={`${t.panelName ? '' : 'opacity-0 group-hover:opacity-100'} transition-opacity shrink-0`}
                    style={{ color: "var(--ec-text-subtle)" }}
                  />
                </span>
                <span className="block text-[11px] mt-0.5" style={{ color: "var(--ec-text-subtle)" }}>
                  {t.subtitle}
                </span>
                <span className="flex items-baseline gap-1 mt-2">
                  <span className="text-xl font-semibold tabular-nums" style={{ color: "var(--ec-text)" }}>
                    {t.count === null ? "—" : t.count}
                  </span>
                  {t.unit && (
                    <span className="text-[11px]" style={{ color: "var(--ec-text-subtle)" }}>
                      {t.unit}
                    </span>
                  )}
                </span>
              </span>
            </Link>
          </div>
        ))}
      </div>
    </section>
  )
}
