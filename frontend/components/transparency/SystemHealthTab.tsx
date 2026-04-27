'use client'

import { useCallback, useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { transparencyApi, type SystemHealth } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

const ESL_STATUSES: Array<'APPROVED' | 'MODIFIED' | 'VETOED'> = [
  'APPROVED',
  'MODIFIED',
  'VETOED',
]

function latencyClass(ms: number): string {
  if (ms < 100) return 'text-[#166534]'
  if (ms < 500) return 'text-[#854d0e]'
  return 'text-[#991b1b]'
}

function formatLocalTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return iso
  }
}

export default function SystemHealthTab() {
  const [data, setData] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await transparencyApi.getSystemHealth()
      setData(resp)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load system health'
      setError(msg)
      console.error('[system-health] load failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[180px] rounded-2xl" />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <CardContent className="py-12 text-center space-y-4">
          <Activity className="h-10 w-10 mx-auto text-[#9e9e9e]" />
          <p className="text-sm text-[#991b1b]">{error || 'No system health data available.'}</p>
          <Button type="button" variant="outline" onClick={load}>
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Tool latency */}
      <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <CardHeader>
          <CardTitle className="text-[#0a0a0a]">Tool latency</CardTitle>
          <CardDescription className="text-[#6b6b6b]">
            Per-tool success rate and latency over the last 24 hours
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.tool_health.length === 0 ? (
            <div className="text-center py-8 text-sm text-[#6b6b6b]">
              No tool calls in the last 24h.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[rgba(0,0,0,0.06)]">
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Tool</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Source</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Calls (24h)</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Success</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">p50</th>
                    <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">p95</th>
                  </tr>
                </thead>
                <tbody>
                  {data.tool_health.map((row) => (
                    <tr
                      key={`${row.tool_name}-${row.source}`}
                      className="border-b border-[rgba(0,0,0,0.04)] last:border-0"
                    >
                      <td className="py-3 px-4 text-sm font-medium text-[#0a0a0a]">{row.tool_name}</td>
                      <td className="py-3 px-4 text-sm text-[#6b6b6b]">{row.source}</td>
                      <td className="py-3 px-4 text-sm text-right text-[#0a0a0a]">{row.calls_24h}</td>
                      <td className="py-3 px-4 text-sm text-right text-[#0a0a0a]">
                        {(row.success_rate * 100).toFixed(0)}%
                      </td>
                      <td className={`py-3 px-4 text-sm text-right font-medium ${latencyClass(row.p50_latency_ms)}`}>
                        {row.p50_latency_ms} ms
                      </td>
                      <td className={`py-3 px-4 text-sm text-right font-medium ${latencyClass(row.p95_latency_ms)}`}>
                        {row.p95_latency_ms} ms
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ESL decisions summary */}
      <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <CardHeader>
          <CardTitle className="text-[#0a0a0a]">ESL decisions</CardTitle>
          <CardDescription className="text-[#6b6b6b]">
            Counts over the last 24 hours and 7 days
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[rgba(0,0,0,0.06)]">
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Decision</th>
                  <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">24h</th>
                  <th className="text-right py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">7d</th>
                </tr>
              </thead>
              <tbody>
                {ESL_STATUSES.map((status) => {
                  const row = data.esl_summary[status] || { count_24h: 0, count_7d: 0 }
                  const tint =
                    status === 'VETOED' && row.count_24h > 0 ? 'bg-[#fef2f2]' : ''
                  return (
                    <tr
                      key={status}
                      className={`border-b border-[rgba(0,0,0,0.04)] last:border-0 ${tint}`}
                    >
                      <td className="py-3 px-4 text-sm font-medium text-[#0a0a0a]">{status}</td>
                      <td className="py-3 px-4 text-sm text-right text-[#0a0a0a]">{row.count_24h}</td>
                      <td className="py-3 px-4 text-sm text-right text-[#0a0a0a]">{row.count_7d}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Scheduler jobs */}
      <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <CardHeader>
          <CardTitle className="text-[#0a0a0a]">Scheduler jobs</CardTitle>
          <CardDescription className="text-[#6b6b6b]">
            Background APScheduler state
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.scheduler.length === 0 ? (
            <div className="text-center py-8 text-sm text-[#6b6b6b]">
              Scheduler not running.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[rgba(0,0,0,0.06)]">
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Job</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Next run</th>
                    <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Trigger</th>
                  </tr>
                </thead>
                <tbody>
                  {data.scheduler.map((job) => (
                    <tr
                      key={job.job_id}
                      className="border-b border-[rgba(0,0,0,0.04)] last:border-0"
                    >
                      <td className="py-3 px-4 text-sm font-medium text-[#0a0a0a]">{job.job_id}</td>
                      <td className="py-3 px-4 text-sm text-[#6b6b6b]">{formatLocalTime(job.next_run_time)}</td>
                      <td className="py-3 px-4 text-sm text-[#6b6b6b]">{job.trigger}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
