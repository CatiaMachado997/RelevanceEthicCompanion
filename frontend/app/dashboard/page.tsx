'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, insightApi, contextApi, type ContextSnapshot } from '@/lib/api'
import Link from 'next/link'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import {
  MessageSquare, Shield, ArrowRight,
  Calendar, Clock, AlertTriangle, CheckSquare, FolderOpen,
} from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

interface ESLLog {
  id?: string
  decision?: { status: 'APPROVED' | 'VETOED' | 'MODIFIED'; reason: string }
  timestamp?: string
}

const CARD_STYLE = {
  background: 'var(--ec-card-bg)',
  border: '1px solid var(--ec-card-border)',
  borderRadius: '16px',
  boxShadow: 'var(--ec-card-shadow)',
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

const PRESSURE_LABEL: Record<string, string> = {
  light: 'Light day',
  moderate: 'Moderate load',
  heavy: 'Heavy schedule',
}
const PRESSURE_COLOR: Record<string, string> = {
  light: '#4A7C59',
  moderate: '#9B7A3D',
  heavy: '#B04A3A',
}

export default function DashboardPage() {
  const [snapshot, setSnapshot] = useState<ContextSnapshot | null>(null)
  const [eslActivity, setEslActivity] = useState<ESLLog[]>([])
  const [approvalRate, setApprovalRate] = useState<number | null>(null)
  const [eslCount, setEslCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [dailyInsight, setDailyInsight] = useState<string | null>(null)
  const [insightLoading, setInsightLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [snap, report, logs] = await Promise.allSettled([
          contextApi.snapshot(),
          transparencyApi.report(),
          transparencyApi.logs(),
        ])
        if (snap.status === 'fulfilled') setSnapshot(snap.value)
        if (report.status === 'fulfilled') {
          setEslCount(report.value?.total_decisions ?? 0)
          const rate = report.value?.approval_rate ?? 0
          setApprovalRate(rate > 1 ? rate : rate * 100)
        }
        if (logs.status === 'fulfilled')
          setEslActivity((logs.value?.logs ?? []).slice(0, 5) as unknown as ESLLog[])
      } finally {
        setLoading(false)
      }

      try {
        const insightData = await insightApi.daily()
        setDailyInsight(insightData?.insight ?? null)
      } catch {
        // no insight available
      } finally {
        setInsightLoading(false)
      }
    }
    load()
  }, [])

  const pieData = approvalRate !== null
    ? [
        { name: 'Approved', value: Math.round(approvalRate) },
        { name: 'Other', value: Math.max(0, 100 - Math.round(approvalRate)) },
      ]
    : []

  return (
    <ErrorBoundary>
    <div className="p-6 max-w-4xl mx-auto space-y-8">

      {/* ── Today section ──────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold" style={{ color: 'var(--ec-text)' }}>
            Today
          </h2>
          {snapshot && (
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={{
                background: `${PRESSURE_COLOR[snapshot.calendar_pressure]}18`,
                color: PRESSURE_COLOR[snapshot.calendar_pressure],
                border: `1px solid ${PRESSURE_COLOR[snapshot.calendar_pressure]}30`,
              }}
            >
              {PRESSURE_LABEL[snapshot.calendar_pressure]}
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[0, 1].map(i => <Skeleton key={i} className="h-32 rounded-2xl" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Tasks due soon */}
            <div style={CARD_STYLE} className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckSquare size={14} style={{ color: 'var(--ec-text-subtle)' }} />
                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
                  Due soon
                </span>
                {snapshot && snapshot.overdue_count > 0 && (
                  <span
                    className="ml-auto text-xs px-1.5 py-0.5 rounded-full font-medium flex items-center gap-1"
                    style={{ background: 'rgba(176,74,58,0.10)', color: '#B04A3A' }}
                  >
                    <AlertTriangle size={10} />
                    {snapshot.overdue_count} overdue
                  </span>
                )}
              </div>
              {!snapshot || snapshot.tasks_due_soon.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
                  No tasks due in the next 7 days.{' '}
                  <Link href="/dashboard/tasks" className="underline">Add one</Link>
                </p>
              ) : (
                <ul className="space-y-2">
                  {snapshot.tasks_due_soon.slice(0, 4).map(t => (
                    <li key={t.id} className="flex items-start gap-2">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{
                          background: t.status === 'in_progress' ? '#4A7C59' : 'var(--ec-text-subtle)',
                          marginTop: '6px',
                        }}
                      />
                      <div className="min-w-0">
                        <p className="text-sm truncate" style={{ color: 'var(--ec-text)' }}>{t.title}</p>
                        <p className="text-[11px]" style={{ color: 'var(--ec-text-subtle)' }}>
                          {t.project_title ? `${t.project_title} · ` : ''}
                          {t.due_date
                            ? new Date(t.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                            : 'No due date'}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <Link
                href="/dashboard/tasks"
                className="mt-3 flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
                style={{ color: '#4A7C59' }}
              >
                All tasks <ArrowRight size={11} />
              </Link>
            </div>

            {/* Active projects */}
            <div style={CARD_STYLE} className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <FolderOpen size={14} style={{ color: 'var(--ec-text-subtle)' }} />
                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
                  Active projects
                </span>
              </div>
              {!snapshot || snapshot.active_projects.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
                  No active projects.{' '}
                  <Link href="/dashboard/projects" className="underline">Create one</Link>
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {snapshot.active_projects.slice(0, 4).map(p => {
                    const total = p.open_tasks + p.done_tasks
                    const pct = total > 0 ? Math.round((p.done_tasks / total) * 100) : 0
                    return (
                      <li key={p.id}>
                        <div className="flex items-center justify-between mb-0.5">
                          <p className="text-sm truncate flex-1 mr-2" style={{ color: 'var(--ec-text)' }}>{p.title}</p>
                          <span className="text-[11px] shrink-0" style={{ color: 'var(--ec-text-subtle)' }}>
                            {p.open_tasks} open
                          </span>
                        </div>
                        <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--ec-card-border)' }}>
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${pct}%`, background: '#4A7C59' }}
                          />
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
              <Link
                href="/dashboard/projects"
                className="mt-3 flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
                style={{ color: '#4A7C59' }}
              >
                All projects <ArrowRight size={11} />
              </Link>
            </div>

            {/* Upcoming events — only rendered when events exist */}
            {snapshot && snapshot.upcoming_events.length > 0 && (
              <div style={CARD_STYLE} className="p-5 md:col-span-2">
                <div className="flex items-center gap-2 mb-3">
                  <Calendar size={14} style={{ color: 'var(--ec-text-subtle)' }} />
                  <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
                    Next 24 hours
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {snapshot.upcoming_events.map((ev, i) => (
                    <div
                      key={`${ev.title}-${ev.start_time ?? i}`}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm"
                      style={{ background: 'var(--ec-surface-2, rgba(0,0,0,0.04))', color: 'var(--ec-text)' }}
                    >
                      <Clock size={12} style={{ color: 'var(--ec-text-subtle)' }} />
                      <span>{ev.title}</span>
                      {ev.start_time && (
                        <span style={{ color: 'var(--ec-text-subtle)' }}>
                          {new Date(ev.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}
      </div>

      {/* ── Daily insight ─────────────────────────────────────── */}
      <div style={CARD_STYLE} className="p-6">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquare size={14} style={{ color: 'var(--ec-text-subtle)' }} />
          <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
            Daily insight
          </span>
        </div>
        {insightLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full rounded" />
            <Skeleton className="h-4 w-3/4 rounded" />
          </div>
        ) : dailyInsight ? (
          <p className="text-sm leading-relaxed" style={{ color: 'var(--ec-text)' }}>{dailyInsight}</p>
        ) : (
          <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
            No insight available today.{' '}
            <Link href="/dashboard/chat" className="underline">Start a chat</Link> to generate one.
          </p>
        )}
      </div>

      {/* ── ESL activity ─────────────────────────────────────── */}
      <div style={CARD_STYLE} className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Shield size={14} style={{ color: 'var(--ec-text-subtle)' }} />
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--ec-text-subtle)' }}>
              ESL activity
            </span>
          </div>
          {eslCount !== null && (
            <span className="text-xs" style={{ color: 'var(--ec-text-subtle)' }}>
              {eslCount} decisions
            </span>
          )}
        </div>

        <div className="flex gap-6 items-start">
          {/* Pie chart */}
          {pieData.length > 0 && (
            <div className="shrink-0">
              <ResponsiveContainer width={80} height={80}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={22} outerRadius={36} dataKey="value" strokeWidth={0}>
                    <Cell fill="#4A7C59" />
                    <Cell fill="rgba(0,0,0,0.06)" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <p className="text-center text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
                {Math.round(approvalRate ?? 0)}% approved
              </p>
            </div>
          )}

          {/* Recent logs */}
          <div className="flex-1 min-w-0">
            {loading ? (
              <div className="space-y-2">
                {[0,1,2].map(i => <Skeleton key={i} className="h-6 rounded" />)}
              </div>
            ) : eslActivity.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>No recent ESL decisions.</p>
            ) : (
              <ul className="space-y-1.5">
                {eslActivity.map((log, i) => {
                  const status = log.decision?.status ?? 'APPROVED'
                  const colors = ESL_COLORS[status] ?? ESL_COLORS.APPROVED
                  return (
                    <li key={log.id ?? i} className="flex items-center gap-2">
                      <span
                        className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
                        style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
                      >
                        {status}
                      </span>
                      <span className="text-xs truncate" style={{ color: 'var(--ec-text-subtle)' }}>
                        {log.decision?.reason?.slice(0, 60) ?? '—'}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
            <Link
              href="/dashboard/transparency"
              className="mt-3 flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
              style={{ color: '#4A7C59' }}
            >
              Full transparency log <ArrowRight size={11} />
            </Link>
          </div>
        </div>
      </div>

    </div>
    </ErrorBoundary>
  )
}
