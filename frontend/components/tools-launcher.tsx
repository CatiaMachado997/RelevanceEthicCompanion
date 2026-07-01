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
import { useQuery } from "@tanstack/react-query"
import {
  Target, CheckSquare, FolderOpen, Heart, FileText, Eye, Bell,
  ArrowRight, PanelRight,
} from "lucide-react"
import { api, transparencyApi, type DashboardOverview } from "@/lib/api"


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
  const { data: overview } = useQuery<DashboardOverview>({
    queryKey: ["dashboard-overview"],
    queryFn: () => api.dashboard.overview(),
  })
  // Surface the ESL approval rate on the Transparency tile so the old
  // "ESL activity" card on the dashboard can go away. Cheap query, not
  // tied to the overview endpoint (kept separate to avoid bloating
  // /overview with stats that only this tile uses).
  const { data: eslReport } = useQuery({
    queryKey: ["esl-report-7d"],
    queryFn: () => transparencyApi.report(7),
    retry: false,
    staleTime: 5 * 60_000,
  })
  const approvalRate =
    eslReport && eslReport.total_decisions > 0
      ? Math.round(
          (eslReport.approval_rate > 1
            ? eslReport.approval_rate
            : eslReport.approval_rate * 100),
        )
      : null

  const tools: ToolCard[] = [
    {
      href: "/dashboard/goals",
      title: "Goals",
      subtitle: "Long-term direction",
      icon: <Target size={16} />,
      count: overview?.goals_active ?? null,
      unit: "active",
      accent: "rgba(74,124,89,0.10)",
      panelName: "goals",
    },
    {
      href: "/dashboard/tasks",
      title: "Tasks",
      subtitle: "This week's work",
      icon: <CheckSquare size={16} />,
      count: overview?.tasks_open ?? null,
      unit: "open",
      accent: "rgba(74,124,89,0.10)",
      panelName: "tasks",
    },
    {
      href: "/dashboard/projects",
      title: "Projects",
      subtitle: "Grouped initiatives",
      icon: <FolderOpen size={16} />,
      count: overview?.projects_active ?? null,
      unit: "active",
      accent: "rgba(155,122,61,0.10)",
      panelName: "projects",
    },
    {
      href: "/dashboard/values",
      title: "Values",
      subtitle: "Your boundaries",
      icon: <Heart size={16} />,
      count: overview?.values_count ?? null,
      unit: "defined",
      accent: "rgba(155,122,61,0.10)",
      panelName: "values",
    },
    {
      href: "/dashboard/documents",
      title: "Documents",
      subtitle: "Uploaded files",
      icon: <FileText size={16} />,
      count: overview?.documents_count ?? null,
      unit: "files",
      accent: "rgba(74,124,89,0.10)",
      panelName: "documents",
    },
    {
      href: "/dashboard/transparency",
      title: "Transparency",
      // Approval rate is the most informative single number for the ESL —
      // surfaces "is the agent over-vetoing me?" at a glance.
      subtitle: approvalRate !== null ? `${approvalRate}% approved · 7d` : "ESL audit log",
      icon: <Eye size={16} />,
      count: overview?.esl_decisions_7d ?? null,
      unit: "decisions",
      accent: "rgba(74,124,89,0.10)",
      panelName: "transparency",
    },
    {
      href: "/dashboard/notifications",
      title: "Notifications",
      subtitle: "Activity alerts",
      icon: <Bell size={16} />,
      count: overview?.notifications_unread ?? null,
      unit: "unread",
      accent: (overview?.notifications_unread ?? 0) > 0 ? "rgba(176,74,58,0.10)" : "rgba(74,124,89,0.10)",
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
