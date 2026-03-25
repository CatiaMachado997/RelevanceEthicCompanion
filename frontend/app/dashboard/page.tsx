'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, goalsApi, valuesApi, eventsApi, type Goal, type CalendarEvent } from '@/lib/api'
import Link from 'next/link'
import { MessageSquare, Heart, Shield, ArrowRight, Target, Calendar, Clock } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Card } from '@/components/ui/card'
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts'

interface ESLLog {
  id?: string
  decision?: { status: 'APPROVED' | 'VETOED' | 'MODIFIED'; reason: string }
  timestamp?: string
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

export default function DashboardPage() {
  const [goalCount, setGoalCount] = useState<number | null>(null)
  const [valueCount, setValueCount] = useState<number | null>(null)
  const [eslCount, setEslCount] = useState<number | null>(null)
  const [approvalRate, setApprovalRate] = useState<number | null>(null)
  const [recentGoals, setRecentGoals] = useState<Goal[]>([])
  const [eslActivity, setEslActivity] = useState<ESLLog[]>([])
  const [upcomingEvents, setUpcomingEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [goals, values, report, logs, events] = await Promise.allSettled([
          goalsApi.list(),
          valuesApi.list(),
          transparencyApi.report(),
          transparencyApi.logs(),
          eventsApi.upcoming(24),
        ])
        if (goals.status === 'fulfilled') {
          const g = goals.value?.goals ?? []
          setGoalCount(g.length)
          setRecentGoals(g.slice(0, 3) as Goal[])
        }
        if (values.status === 'fulfilled') setValueCount((values.value?.values ?? []).length)
        if (report.status === 'fulfilled') {
          setEslCount(report.value?.total_decisions ?? 0)
          const rate = report.value?.approval_rate ?? 0
          setApprovalRate(rate > 1 ? rate : rate * 100)
        }
        if (logs.status === 'fulfilled') setEslActivity((logs.value?.logs ?? []).slice(0, 5) as unknown as ESLLog[])
        if (events.status === 'fulfilled') setUpcomingEvents((events.value?.events ?? []).slice(0, 3))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const now = new Date()
  const hour = now.getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  function formatEventTime(iso: string | null): string {
    if (!iso) return ''
    const d = new Date(iso)
    const diffMs = d.getTime() - Date.now()
    const diffMin = Math.round(diffMs / 60000)
    if (diffMin < 0) return 'Started'
    if (diffMin < 60) return `in ${diffMin}m`
    const diffH = Math.round(diffMin / 60)
    if (diffH < 24) return `in ${diffH}h`
    return d.toLocaleDateString('en-US', { weekday: 'short', hour: '2-digit', minute: '2-digit' })
  }

  const stats = [
    { label: 'Active Goals', value: goalCount, icon: Target, href: '/dashboard/goals' },
    { label: 'Values Set', value: valueCount, icon: Heart, href: '/dashboard/values' },
    { label: 'ESL Decisions Today', value: eslCount, icon: Shield, href: '/dashboard/transparency' },
  ]

  return (
    <div className="space-y-5">

      {/* Greeting card */}
      <Card className="rounded-2xl p-6 border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <p className="text-sm mb-1" style={{ color: '#6b6b6b' }}>{dateStr}</p>
        <h2 className="text-2xl font-semibold" style={{ color: '#0a0a0a' }}>{greeting}</h2>
      </Card>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {stats.map(({ label, value, icon: Icon, href }) => (
          <Link
            key={label}
            href={href}
            className="rounded-2xl p-5 flex items-center gap-4 transition-shadow duration-150 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] bg-white border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
          >
            <div className="w-10 h-10 rounded-xl bg-[#f5f5f5] flex items-center justify-center shrink-0">
              <Icon size={18} style={{ color: '#000000' }} />
            </div>
            <div>
              {loading ? (
                <Skeleton className="h-7 w-10 mb-1" />
              ) : (
                <p className="text-2xl font-semibold" style={{ color: '#0a0a0a' }}>
                  {value ?? '—'}
                </p>
              )}
              <p className="text-xs" style={{ color: '#6b6b6b' }}>{label}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Two-column: chat shortcut + active goals */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

        {/* Chat shortcut */}
        <Card className="rounded-2xl p-5 flex flex-col justify-between border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare size={16} style={{ color: '#000000' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Chat</h3>
          </div>
          <p className="text-sm mb-4" style={{ color: '#6b6b6b' }}>
            Ask your companion anything. Every response goes through ESL.
          </p>
          <Link
            href="/dashboard/chat"
            className="inline-flex items-center gap-1.5 text-sm font-medium"
            style={{ color: '#000000' }}
          >
            Open chat <ArrowRight size={14} />
          </Link>
        </Card>

        {/* Active goals */}
        <Card className="rounded-2xl p-5 border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target size={16} style={{ color: '#000000' }} />
              <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Active Goals</h3>
            </div>
            <Link href="/dashboard/goals" className="text-xs" style={{ color: '#000000' }}>
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-5 w-full" />)}
            </div>
          ) : recentGoals.length === 0 ? (
            <p className="text-sm" style={{ color: '#9e9e9e' }}>No active goals yet.</p>
          ) : (
            <ul className="space-y-2">
              {recentGoals.map(g => (
                <li key={g.id} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#4A7C59' }} />
                  <span className="text-sm truncate" style={{ color: '#0a0a0a' }}>{g.title}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Upcoming Events */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Calendar size={16} style={{ color: '#000000' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Upcoming</h3>
          </div>
          <Link href="/dashboard/integrations" className="text-xs" style={{ color: '#9e9e9e' }}>
            Manage
          </Link>
        </div>
        {loading ? (
          <div className="space-y-2">
            {[1, 2].map(i => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : upcomingEvents.length === 0 ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm" style={{ color: '#9e9e9e' }}>No upcoming events.</p>
            <Link
              href="/dashboard/integrations"
              className="inline-flex items-center gap-1 text-xs font-medium"
              style={{ color: '#000000' }}
            >
              Connect Google Calendar <ArrowRight size={12} />
            </Link>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {upcomingEvents.map(event => (
              <li key={event.id} className="flex items-start gap-3">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  style={{ background: '#f5f5f5' }}
                >
                  <Clock size={13} style={{ color: '#695e6e' }} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm truncate font-medium" style={{ color: '#0a0a0a' }}>{event.title}</p>
                  <p className="text-xs" style={{ color: '#9e9e9e' }}>
                    {formatEventTime(event.start_time)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ESL Approval Rate sparkline */}
      {!loading && approvalRate !== null && (
        <div className="rounded-2xl p-4" style={{ background: '#ffffff', border: '1px solid #e4dee7' }}>
          <p className="text-xs font-medium mb-2" style={{ color: '#695e6e' }}>ESL Approval Rate</p>
          <div className="flex items-center gap-3">
            <ResponsiveContainer width={60} height={60}>
              <PieChart>
                <Pie
                  data={[{ value: approvalRate }, { value: 100 - approvalRate }]}
                  cx="50%"
                  cy="50%"
                  innerRadius={20}
                  outerRadius={28}
                  dataKey="value"
                  startAngle={90}
                  endAngle={-270}
                >
                  <Cell fill="#4A7C59" />
                  <Cell fill="#f5f5f5" />
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <span className="text-2xl font-bold" style={{ color: '#332b36' }}>{approvalRate.toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* ESL activity strip */}
      <Card className="rounded-2xl p-5 border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Shield size={16} style={{ color: '#000000' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Recent ESL Decisions</h3>
          </div>
          <Link href="/dashboard/transparency" className="text-xs" style={{ color: '#000000' }}>
            View report
          </Link>
        </div>
        {loading ? (
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-6 w-20 rounded-full" />)}
          </div>
        ) : eslActivity.length === 0 ? (
          <p className="text-sm" style={{ color: '#9e9e9e' }}>No decisions recorded yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {eslActivity.map((log, idx) => {
              const status = log.decision?.status ?? 'APPROVED'
              const c = ESL_COLORS[status] ?? ESL_COLORS.APPROVED
              return (
                <span
                  key={log.id ?? idx}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
                  title={log.decision?.reason}
                >
                  {status}
                </span>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
