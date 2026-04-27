'use client'

import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { transparencyApi, type ToolCallEvent } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const STATUS_PILL: Record<string, string> = {
  success: 'bg-[#f0fdf4] text-[#166534] border-[#bbf7d0]',
  error: 'bg-[#fef2f2] text-[#991b1b] border-[#fecaca]',
  vetoed: 'bg-[#fff7ed] text-[#9a3412] border-[#fed7aa]',
  pending_confirmation: 'bg-[#eff6ff] text-[#1e40af] border-[#bfdbfe]',
}

const ESL_PILL: Record<string, string> = {
  APPROVED: 'bg-[#f0fdf4] text-[#166534] border-[#bbf7d0]',
  MODIFIED: 'bg-[#eff6ff] text-[#1e40af] border-[#bfdbfe]',
  VETOED: 'bg-[#fef2f2] text-[#991b1b] border-[#fecaca]',
}

function formatTime(iso: string): string {
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

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export default function ToolCallsTab() {
  const [events, setEvents] = useState<ToolCallEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ToolCallEvent | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await transparencyApi.listToolCalls()
        if (!cancelled) setEvents(data.events || [])
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load tool calls')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Card className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
      <CardHeader>
        <CardTitle className="text-[#0a0a0a]">Tool Calls</CardTitle>
        <CardDescription className="text-[#6b6b6b]">
          Every tool invocation across chat and scheduled flows
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10 rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-sm text-[#991b1b]">{error}</p>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-12">
            <Activity className="h-10 w-10 mx-auto text-[#9e9e9e]" />
            <h3 className="font-semibold mt-4 text-lg text-[#0a0a0a]">No tool calls yet.</h3>
            <p className="text-[#6b6b6b] mt-2">
              Tool invocations will appear here as you chat or scheduled flows run.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[rgba(0,0,0,0.06)]">
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Time</th>
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Tool</th>
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Source</th>
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Status</th>
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">Latency</th>
                  <th className="text-left py-3 px-4 text-xs font-medium uppercase tracking-wide text-[#9e9e9e]">ESL</th>
                </tr>
              </thead>
              <tbody>
                {events.map((evt) => {
                  const statusClass = STATUS_PILL[evt.status] || 'bg-[#f5f5f5] text-[#6b6b6b] border-[#e5e5e5]'
                  const eslClass = evt.esl_decision
                    ? ESL_PILL[evt.esl_decision] || 'bg-[#f5f5f5] text-[#6b6b6b] border-[#e5e5e5]'
                    : 'bg-[#f5f5f5] text-[#9e9e9e] border-[#e5e5e5]'
                  return (
                    <tr
                      key={evt.id}
                      className="border-b border-[rgba(0,0,0,0.04)] last:border-0 hover:bg-[#fafafa] cursor-pointer"
                      onClick={() => setSelected(evt)}
                    >
                      <td className="py-3 px-4 text-sm text-[#6b6b6b] whitespace-nowrap">
                        {formatTime(evt.created_at)}
                      </td>
                      <td className="py-3 px-4 text-sm font-medium text-[#0a0a0a]">{evt.tool_name}</td>
                      <td className="py-3 px-4 text-sm text-[#6b6b6b]">{evt.source}</td>
                      <td className="py-3 px-4">
                        <Badge variant="outline" className={`${statusClass} rounded-full px-2.5 py-0.5 text-xs`}>
                          {evt.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-sm text-[#6b6b6b]">
                        {evt.latency_ms !== null ? `${evt.latency_ms} ms` : '—'}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="outline" className={`${eslClass} rounded-full px-2.5 py-0.5 text-xs`}>
                          {evt.esl_decision || 'n/a'}
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selected?.tool_name}</DialogTitle>
            <DialogDescription>
              {selected ? `${selected.source} · ${formatTime(selected.created_at)}` : ''}
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="outline" className={`${STATUS_PILL[selected.status] || ''} rounded-full px-2.5 py-0.5`}>
                  {selected.status}
                </Badge>
                {selected.esl_decision && (
                  <Badge variant="outline" className={`${ESL_PILL[selected.esl_decision] || ''} rounded-full px-2.5 py-0.5`}>
                    ESL: {selected.esl_decision}
                  </Badge>
                )}
                {selected.latency_ms !== null && (
                  <Badge variant="outline" className="rounded-full px-2.5 py-0.5">
                    {selected.latency_ms} ms
                  </Badge>
                )}
                {selected.source_ref && (
                  <Badge variant="outline" className="rounded-full px-2.5 py-0.5">
                    ref: {selected.source_ref}
                  </Badge>
                )}
              </div>
              {selected.error_message && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e] mb-1">Error</p>
                  <pre className="text-xs bg-[#fef2f2] text-[#991b1b] rounded-lg p-3 overflow-x-auto">
                    {selected.error_message}
                  </pre>
                </div>
              )}
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e] mb-1">Input</p>
                <pre className="text-xs bg-[#fafafa] text-[#0a0a0a] rounded-lg p-3 overflow-x-auto">
                  {prettyJson(selected.input)}
                </pre>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e] mb-1">Output</p>
                <pre className="text-xs bg-[#fafafa] text-[#0a0a0a] rounded-lg p-3 overflow-x-auto">
                  {prettyJson(selected.output)}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  )
}
