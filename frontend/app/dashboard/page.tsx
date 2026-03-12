'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, goalsApi, valuesApi } from '@/lib/api'
import Link from 'next/link'
import { MessageSquare, Heart, Shield, ArrowRight, Target } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface Goal {
  id: string
  title: string
  status: string
  priority: number
}

interface ESLLog {
  id: string
  decision: { status: 'APPROVED' | 'VETOED' | 'MODIFIED'; reason: string }
  timestamp: string
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

const CARD_STYLE = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.04)',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
}

export default function DashboardPage() {
  const [goalCount, setGoalCount] = useState<number | null>(null)
  const [valueCount, setValueCount] = useState<number | null>(null)
  const [eslCount, setEslCount] = useState<number | null>(null)
  const [recentGoals, setRecentGoals] = useState<Goal[]>([])
  const [eslActivity, setEslActivity] = useState<ESLLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [goals, values, report, logs] = await Promise.allSettled([
          goalsApi.list(),
          valuesApi.list(),
          transparencyApi.report(),
          transparencyApi.logs(),
        ])
        if (goals.status === 'fulfilled') {
          const g = goals.value?.goals ?? []
          setGoalCount(g.length)
          setRecentGoals(g.slice(0, 3) as Goal[])
        }
        if (values.status === 'fulfilled') setValueCount((values.value?.values ?? []).length)
        if (report.status === 'fulfilled') setEslCount(report.value?.total_decisions ?? 0)
        if (logs.status === 'fulfilled') setEslActivity((logs.value?.logs ?? []).slice(0, 5) as ESLLog[])
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

  const stats = [
    { label: 'Active Goals', value: goalCount, icon: Target, href: '/dashboard/goals' },
    { label: 'Values Set', value: valueCount, icon: Heart, href: '/dashboard/values' },
    { label: 'ESL Decisions Today', value: eslCount, icon: Shield, href: '/dashboard/transparency' },
  ]

  return (
    <div className="space-y-5">

      {/* Greeting card */}
      <div className="rounded-2xl p-6" style={CARD_STYLE}>
        <p className="text-sm mb-1" style={{ color: '#78716C' }}>{dateStr}</p>
        <h2 className="text-2xl font-semibold" style={{ color: '#1C1917' }}>{greeting}</h2>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        {stats.map(({ label, value, icon: Icon, href }) => (
          <Link
            key={label}
            href={href}
            className="rounded-2xl p-5 flex items-center gap-4 transition-shadow duration-150 hover:shadow-md"
            style={CARD_STYLE}
          >
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'rgba(194,113,79,0.10)' }}
            >
              <Icon size={18} style={{ color: '#C2714F' }} />
            </div>
            <div>
              {loading ? (
                <Skeleton className="h-7 w-10 mb-1" />
              ) : (
                <p className="text-2xl font-semibold" style={{ color: '#1C1917' }}>
                  {value ?? '—'}
                </p>
              )}
              <p className="text-xs" style={{ color: '#78716C' }}>{label}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Two-column: chat shortcut + active goals */}
      <div className="grid grid-cols-2 gap-4">

        {/* Chat shortcut */}
        <div className="rounded-2xl p-5 flex flex-col justify-between" style={CARD_STYLE}>
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare size={16} style={{ color: '#C2714F' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Chat</h3>
          </div>
          <p className="text-sm mb-4" style={{ color: '#78716C' }}>
            Ask your companion anything. Every response goes through ESL.
          </p>
          <Link
            href="/dashboard/chat"
            className="inline-flex items-center gap-1.5 text-sm font-medium"
            style={{ color: '#C2714F' }}
          >
            Open chat <ArrowRight size={14} />
          </Link>
        </div>

        {/* Active goals */}
        <div className="rounded-2xl p-5" style={CARD_STYLE}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target size={16} style={{ color: '#C2714F' }} />
              <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Active Goals</h3>
            </div>
            <Link href="/dashboard/goals" className="text-xs" style={{ color: '#C2714F' }}>
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-5 w-full" />)}
            </div>
          ) : recentGoals.length === 0 ? (
            <p className="text-sm" style={{ color: '#A8A29E' }}>No active goals yet.</p>
          ) : (
            <ul className="space-y-2">
              {recentGoals.map(g => (
                <li key={g.id} className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#4A7C59' }} />
                  <span className="text-sm truncate" style={{ color: '#1C1917' }}>{g.title}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ESL activity strip */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Shield size={16} style={{ color: '#C2714F' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Recent ESL Decisions</h3>
          </div>
          <Link href="/dashboard/transparency" className="text-xs" style={{ color: '#C2714F' }}>
            View report
          </Link>
        </div>
        {loading ? (
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-6 w-20 rounded-full" />)}
          </div>
        ) : eslActivity.length === 0 ? (
          <p className="text-sm" style={{ color: '#A8A29E' }}>No decisions recorded yet.</p>
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
      </div>
    </div>
  )
}
