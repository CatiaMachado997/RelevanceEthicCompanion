'use client'

import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, CalendarRange } from 'lucide-react'
import { weeklyReviewApi, type WeeklyReview } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/lib/toast'

/** Format YYYY-MM-DD from a Date in UTC-stable way (matches backend ISO date). */
function toIsoDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseIsoDate(s: string): Date {
  // Treat as local date (avoid TZ surprises in display labels).
  const [y, m, d] = s.split('-').map((n) => parseInt(n, 10))
  return new Date(y, (m ?? 1) - 1, d ?? 1)
}

function formatShort(s: string | null | undefined): string {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatPeriod(start: string, end: string): string {
  const s = parseIsoDate(start)
  const e = parseIsoDate(end)
  const left = s.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const right = e.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `${left} – ${right}`
}

function startOfThisWeekIso(): string {
  // Monday as start of week (matches typical backend behaviour).
  const now = new Date()
  const day = now.getDay() // 0 = Sun, 1 = Mon, …
  const diff = (day + 6) % 7 // days since Monday
  const monday = new Date(now)
  monday.setDate(now.getDate() - diff)
  monday.setHours(0, 0, 0, 0)
  return toIsoDate(monday)
}

function shiftIsoDate(iso: string, days: number): string {
  const d = parseIsoDate(iso)
  d.setDate(d.getDate() + days)
  return toIsoDate(d)
}

interface ListRowProps {
  title: string
  meta?: string | null
}

function ListRow({ title, meta }: ListRowProps) {
  return (
    <li className="flex items-start justify-between gap-3 py-1.5 border-b border-[#f0f0f0] last:border-b-0">
      <span className="text-sm truncate" style={{ color: 'var(--ec-text)' }}>
        {title}
      </span>
      {meta ? (
        <span
          className="text-[11px] shrink-0"
          style={{ color: 'var(--ec-text-subtle)' }}
        >
          {meta}
        </span>
      ) : null}
    </li>
  )
}

interface SectionProps {
  title: string
  count: number
  emptyText?: string
  tone?: 'default' | 'warn'
  children: React.ReactNode
  isEmpty: boolean
}

function Section({
  title,
  count,
  emptyText = 'Nothing here.',
  tone = 'default',
  children,
  isEmpty,
}: SectionProps) {
  return (
    <div className="mb-5">
      <h3
        className="text-xs font-medium uppercase tracking-wider mb-2 flex items-center gap-2"
        style={{
          color:
            tone === 'warn' ? '#B04A3A' : 'var(--ec-text-subtle)',
        }}
      >
        <span>{title}</span>
        <span className="text-[11px] font-normal opacity-70">({count})</span>
      </h3>
      {isEmpty ? (
        <p className="text-sm" style={{ color: 'var(--ec-text-subtle)' }}>
          {emptyText}
        </p>
      ) : (
        <ul className="space-y-0">{children}</ul>
      )}
    </div>
  )
}

export default function WeeklyReviewPage() {
  const [weekStart, setWeekStart] = useState<string>(() => startOfThisWeekIso())
  const [data, setData] = useState<WeeklyReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (ws: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await weeklyReviewApi.get(ws)
      setData(res)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load weekly review'
      setError(msg)
      toast.error('Could not load weekly review', msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(weekStart)
  }, [weekStart, load])

  const goPrev = () => setWeekStart((ws) => shiftIsoDate(ws, -7))
  const goNext = () => setWeekStart((ws) => shiftIsoDate(ws, 7))
  const goThis = () => setWeekStart(startOfThisWeekIso())

  const periodLabel = data
    ? formatPeriod(data.period.start, data.period.end)
    : formatPeriod(weekStart, shiftIsoDate(weekStart, 6))

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: 'var(--ec-text)' }}>
            Weekly Review
          </h1>
          <p
            className="text-sm flex items-center gap-2 mt-1"
            style={{ color: 'var(--ec-text-subtle)' }}
          >
            <CalendarRange size={14} />
            {periodLabel}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={goPrev}>
            <ChevronLeft size={14} />
            Previous
          </Button>
          <Button variant="outline" size="sm" onClick={goThis}>
            This week
          </Button>
          <Button variant="outline" size="sm" onClick={goNext}>
            Next
            <ChevronRight size={14} />
          </Button>
        </div>
      </div>

      {error && !loading ? (
        <Card>
          <CardContent className="p-5 flex items-center justify-between gap-3">
            <p className="text-sm text-[#B04A3A]">{error}</p>
            <Button variant="outline" size="sm" onClick={() => load(weekStart)}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Last week column */}
          <Card>
            <CardContent className="p-5">
              <h2
                className="text-base font-semibold mb-4"
                style={{ color: 'var(--ec-text)' }}
              >
                Last week
              </h2>

              <Section
                title="Completed tasks"
                count={data.completed_tasks.length}
                isEmpty={data.completed_tasks.length === 0}
              >
                {data.completed_tasks.map((t) => (
                  <ListRow
                    key={t.id}
                    title={t.title}
                    meta={t.completed_at ? formatShort(t.completed_at) : null}
                  />
                ))}
              </Section>

              <Section
                title="Completed milestones"
                count={data.completed_milestones.length}
                isEmpty={data.completed_milestones.length === 0}
              >
                {data.completed_milestones.map((m) => (
                  <ListRow
                    key={m.id}
                    title={m.title}
                    meta={m.completed_at ? formatShort(m.completed_at) : null}
                  />
                ))}
              </Section>

              <Section
                title="Carry-over tasks"
                count={data.carry_over_tasks.length}
                tone="warn"
                isEmpty={data.carry_over_tasks.length === 0}
              >
                {data.carry_over_tasks.map((t) => (
                  <ListRow
                    key={t.id}
                    title={t.title}
                    meta={
                      t.due_date
                        ? `due ${formatShort(t.due_date)}`
                        : t.status
                    }
                  />
                ))}
              </Section>
            </CardContent>
          </Card>

          {/* This week column */}
          <Card>
            <CardContent className="p-5">
              <h2
                className="text-base font-semibold mb-4"
                style={{ color: 'var(--ec-text)' }}
              >
                This week
              </h2>

              <Section
                title="Upcoming tasks"
                count={data.upcoming_tasks.length}
                isEmpty={data.upcoming_tasks.length === 0}
              >
                {data.upcoming_tasks.map((t) => (
                  <ListRow
                    key={t.id}
                    title={t.title}
                    meta={
                      t.due_date
                        ? `due ${formatShort(t.due_date)}`
                        : t.status
                    }
                  />
                ))}
              </Section>

              <Section
                title="Upcoming milestones"
                count={data.upcoming_milestones.length}
                isEmpty={data.upcoming_milestones.length === 0}
              >
                {data.upcoming_milestones.map((m) => (
                  <ListRow
                    key={m.id}
                    title={m.title}
                    meta={m.target_date ? formatShort(m.target_date) : null}
                  />
                ))}
              </Section>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
