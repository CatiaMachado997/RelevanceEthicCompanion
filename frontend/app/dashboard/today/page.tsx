'use client'

/**
 * Sprint F Task 6 — Today view.
 *
 * Replaces the old single "no tasks due" empty state with four cross-source
 * widgets pulled from `/api/today/feed`:
 *   - Tasks (due today + overdue stacked)
 *   - Recent emails (Gmail, last 24h indexed)
 *   - Recent Slack mentions (last 24h indexed)
 *   - Calendar today (events whose start falls today)
 *
 * Each widget has its own empty state. For Gmail/Slack/Calendar the empty
 * state asks the user to connect the integration when no items have ever
 * been synced for that source; once at least one row exists we show
 * "No new ... in the last 24h" instead.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  Calendar,
  CheckSquare,
  Mail,
  MessageSquare,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  todayApi,
  connectorsApi,
  type TodayFeed,
  type TodaySourceItem,
  type TodayTaskItem,
  type ConnectorIndexStatus,
} from '@/lib/api'

const HEADER_LABEL =
  'text-xs font-medium uppercase tracking-wider text-[var(--ec-text-subtle)]'

function formatRelativeTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diffMs = Date.now() - d.getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

function isConnected(status: ConnectorIndexStatus | null): boolean {
  if (!status) return false
  return status.total_items > 0 || status.last_sync_at !== null
}

interface WidgetProps {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}

function Widget({ title, icon, children }: WidgetProps) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[var(--ec-text-subtle)]">{icon}</span>
        <span className={HEADER_LABEL}>{title}</span>
      </div>
      {children}
    </Card>
  )
}

function EmptyState({
  message,
  ctaLabel,
  ctaHref,
}: {
  message: string
  ctaLabel?: string
  ctaHref?: string
}) {
  return (
    <p className="text-sm text-[var(--ec-text-subtle)]">
      {message}
      {ctaLabel && ctaHref && (
        <>
          {' '}
          <Link
            href={ctaHref}
            className="text-[#4A7C59] underline hover:opacity-80"
          >
            {ctaLabel}
          </Link>
        </>
      )}
    </p>
  )
}

function TaskRow({ task, overdue = false }: { task: TodayTaskItem; overdue?: boolean }) {
  return (
    <li className="flex items-start gap-2">
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0 mt-[6px]"
        style={{
          background: overdue
            ? '#B04A3A'
            : task.status === 'in_progress'
            ? '#4A7C59'
            : 'var(--ec-text-subtle)',
        }}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm truncate text-[var(--ec-text)]">{task.title}</p>
        {task.due_date && (
          <p className="text-[11px] text-[var(--ec-text-subtle)]">
            {overdue ? 'Was due ' : 'Due '}
            {new Date(task.due_date).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
            })}
          </p>
        )}
      </div>
    </li>
  )
}

function SourceRow({ item, showTime = false }: { item: TodaySourceItem; showTime?: boolean }) {
  const content = (
    <>
      <p className="text-sm truncate text-[var(--ec-text)] font-medium">
        {item.title || '(no subject)'}
      </p>
      {item.snippet && (
        <p className="text-[12px] text-[var(--ec-text-subtle)] truncate">
          {item.snippet}
        </p>
      )}
      <p className="text-[11px] text-[var(--ec-text-subtle)] mt-0.5">
        {showTime ? formatTime(item.timestamp) : formatRelativeTime(item.timestamp)}
      </p>
    </>
  )
  return (
    <li className="min-w-0">
      {item.url ? (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block hover:opacity-80"
        >
          {content}
        </a>
      ) : (
        <div>{content}</div>
      )}
    </li>
  )
}

export default function TodayPage() {
  const [feed, setFeed] = useState<TodayFeed | null>(null)
  const [gmailStatus, setGmailStatus] = useState<ConnectorIndexStatus | null>(null)
  const [slackStatus, setSlackStatus] = useState<ConnectorIndexStatus | null>(null)
  const [calStatus, setCalStatus] = useState<ConnectorIndexStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [feedRes, gmail, slack, cal] = await Promise.allSettled([
          todayApi.getFeed(),
          connectorsApi.getStatus('gmail'),
          connectorsApi.getStatus('slack'),
          connectorsApi.getStatus('google_calendar'),
        ])
        if (cancelled) return
        if (feedRes.status === 'fulfilled') setFeed(feedRes.value)
        if (gmail.status === 'fulfilled') setGmailStatus(gmail.value)
        if (slack.status === 'fulfilled') setSlackStatus(slack.value)
        if (cal.status === 'fulfilled') setCalStatus(cal.value)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const tasksDue = feed?.tasks_due_today ?? []
  const tasksOverdue = feed?.tasks_overdue ?? []
  const emails = feed?.recent_emails ?? []
  const slack = feed?.recent_slack ?? []
  const calendar = feed?.calendar_today ?? []

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--ec-text)]">Today</h1>
        <p className="text-sm text-[var(--ec-text-subtle)] mt-1">
          Tasks, recent activity, and what&apos;s on your calendar.
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Tasks (due today + overdue) */}
          <Widget title="Tasks" icon={<CheckSquare size={14} />}>
            {tasksDue.length === 0 && tasksOverdue.length === 0 ? (
              <EmptyState
                message="Nothing due today."
                ctaLabel="Add a task →"
                ctaHref="/dashboard/tasks"
              />
            ) : (
              <div className="space-y-3">
                {tasksOverdue.length > 0 && (
                  <div>
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <AlertTriangle size={11} className="text-[#B04A3A]" />
                      <span className="text-[11px] font-medium uppercase tracking-wider text-[#B04A3A]">
                        Overdue ({tasksOverdue.length})
                      </span>
                    </div>
                    <ul className="space-y-1.5">
                      {tasksOverdue.map((t) => (
                        <TaskRow key={t.id} task={t} overdue />
                      ))}
                    </ul>
                  </div>
                )}
                {tasksDue.length > 0 && (
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-wider text-[var(--ec-text-subtle)] mb-1.5">
                      Due today ({tasksDue.length})
                    </div>
                    <ul className="space-y-1.5">
                      {tasksDue.map((t) => (
                        <TaskRow key={t.id} task={t} />
                      ))}
                    </ul>
                  </div>
                )}
                <Link
                  href="/dashboard/tasks"
                  className="flex items-center gap-1 text-xs text-[#4A7C59] hover:opacity-70 mt-2"
                >
                  All tasks <ArrowRight size={11} />
                </Link>
              </div>
            )}
          </Widget>

          {/* Recent emails */}
          <Widget title="Recent emails" icon={<Mail size={14} />}>
            {emails.length === 0 ? (
              isConnected(gmailStatus) ? (
                <EmptyState message="No new emails in the last 24h." />
              ) : (
                <EmptyState
                  message="Connect Gmail to see recent messages here."
                  ctaLabel="Connect →"
                  ctaHref="/dashboard/integrations"
                />
              )
            ) : (
              <ul className="space-y-3">
                {emails.map((e) => (
                  <SourceRow key={e.id} item={e} />
                ))}
              </ul>
            )}
          </Widget>

          {/* Recent Slack */}
          <Widget title="Recent Slack" icon={<MessageSquare size={14} />}>
            {slack.length === 0 ? (
              isConnected(slackStatus) ? (
                <EmptyState message="No new Slack activity in the last 24h." />
              ) : (
                <EmptyState
                  message="Connect Slack to see recent messages here."
                  ctaLabel="Connect →"
                  ctaHref="/dashboard/integrations"
                />
              )
            ) : (
              <ul className="space-y-3">
                {slack.map((s) => (
                  <SourceRow key={s.id} item={s} />
                ))}
              </ul>
            )}
          </Widget>

          {/* Calendar today */}
          <Widget title="Calendar today" icon={<Calendar size={14} />}>
            {calendar.length === 0 ? (
              isConnected(calStatus) ? (
                <EmptyState message="No events scheduled for today." />
              ) : (
                <EmptyState
                  message="Connect Google Calendar to see today's events here."
                  ctaLabel="Connect →"
                  ctaHref="/dashboard/integrations"
                />
              )
            ) : (
              <ul className="space-y-3">
                {calendar.map((c) => (
                  <SourceRow key={c.id} item={c} showTime />
                ))}
              </ul>
            )}
          </Widget>
        </div>
      )}
    </div>
  )
}
