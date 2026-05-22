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

// Sprint K Task 9: shape of the episodic memory hits recorded into
// `tool_call_events.output.memory_used` (or `output.plan_steps[0].memory_used`
// for planner-step events) when EPISODIC_MEMORY_ENABLED is true and recall
// returns matches.
type MemoryUsedEntry = {
  planner_run_id?: string | null
  message_text?: string
  plan_summary?: string
  similarity?: number
}

function extractMemoryUsed(event: ToolCallEvent | null): MemoryUsedEntry[] | null {
  if (!event) return null
  const out = event.output as unknown
  if (!out || typeof out !== 'object') return null
  const o = out as Record<string, unknown>
  // Check direct output.memory_used first
  if (Array.isArray(o.memory_used) && o.memory_used.length > 0) {
    return o.memory_used as MemoryUsedEntry[]
  }
  // Fall back to output.plan_steps[0].memory_used (planner-level event)
  if (Array.isArray(o.plan_steps) && o.plan_steps.length > 0) {
    const firstStep = o.plan_steps[0] as Record<string, unknown>
    if (firstStep && Array.isArray(firstStep.memory_used) && firstStep.memory_used.length > 0) {
      return firstStep.memory_used as MemoryUsedEntry[]
    }
  }
  return null
}

// Sprint G Task 4: shape of the retrieval breadcrumb trace recorded into
// `tool_call_events.output.trace` for `search_documents` calls.
type RetrievalTrace = {
  query?: string
  candidates?: Array<{
    chunk_uuid?: string | null
    hybrid_score?: number
    snippet_preview?: string
  }>
  rerank_applied?: boolean
  rerank_top?: Array<{
    chunk_uuid?: string | null
    rerank_score?: number
  }> | null
  final?: Array<string | null>
}

function extractTrace(event: ToolCallEvent | null): RetrievalTrace | null {
  if (!event || event.tool_name !== 'search_documents') return null
  const out = event.output as unknown
  if (!out || typeof out !== 'object') return null
  const maybe = (out as { trace?: unknown }).trace
  if (!maybe || typeof maybe !== 'object') return null
  return maybe as RetrievalTrace
}

function groupByStep(events: ToolCallEvent[]) {
  const groups = new Map<string, { runId: string | null; stepIndex: number | null; events: ToolCallEvent[] }>()
  for (const ev of events) {
    if (!ev.planner_run_id || ev.step_index == null) {
      const key = `legacy:${ev.id}`
      groups.set(key, { runId: null, stepIndex: null, events: [ev] })
      continue
    }
    const key = `${ev.planner_run_id}:${ev.step_index}`
    const g = groups.get(key)
    if (g) {
      g.events.push(ev)
    } else {
      groups.set(key, { runId: ev.planner_run_id, stepIndex: ev.step_index, events: [ev] })
    }
  }
  return Array.from(groups.entries()).map(([key, g]) => ({ key, ...g }))
}

function shortUuid(uuid: string | null | undefined): string {
  if (!uuid) return '—'
  if (uuid.length <= 12) return uuid
  return `${uuid.slice(0, 8)}…${uuid.slice(-4)}`
}

function MemoryUsedSection({ entries }: { entries: MemoryUsedEntry[] }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e] mb-1">
        Drew on past plans
      </p>
      <div className="rounded-lg p-3 bg-[#fafafa]" style={{ border: '1px solid rgba(0,0,0,0.06)' }}>
        <ul className="space-y-1.5">
          {entries.map((m, i) => (
            <li key={m.planner_run_id ?? i} className="text-xs">
              <div className="text-[#0a0a0a]">
                &ldquo;{m.message_text}&rdquo;
              </div>
              <div className="text-[#6b6b6b]">
                {m.plan_summary}
                {typeof m.similarity === 'number' && (
                  <span className="ml-2 text-[#9e9e9e]">
                    · similarity {m.similarity.toFixed(2)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function RetrievalTraceSection({ trace }: { trace: RetrievalTrace }) {
  const finalSet = new Set((trace.final || []).filter(Boolean) as string[])
  const candidates = trace.candidates || []
  const rerankTop = trace.rerank_top || []

  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-[#9e9e9e] mb-1">
        Retrieval trace
      </p>
      <div className="space-y-3 bg-[#fafafa] rounded-lg p-3">
        {trace.query !== undefined && (
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#9e9e9e] mb-1">Query</p>
            <p className="text-xs text-[#0a0a0a] break-words">{trace.query}</p>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between mb-1">
            <p className="text-[11px] uppercase tracking-wide text-[#9e9e9e]">
              Hybrid candidates ({candidates.length})
            </p>
            <span className="text-[11px] text-[#6b6b6b]">
              rerank: {trace.rerank_applied ? 'applied' : 'not applied'}
            </span>
          </div>
          {candidates.length === 0 ? (
            <p className="text-xs text-[#6b6b6b]">No candidates.</p>
          ) : (
            <ul className="space-y-1.5">
              {candidates.map((c, i) => {
                const isFinal = c.chunk_uuid ? finalSet.has(c.chunk_uuid) : false
                return (
                  <li
                    key={`${c.chunk_uuid || 'na'}-${i}`}
                    className={`text-xs rounded-md px-2 py-1.5 border ${
                      isFinal
                        ? 'bg-[#f0fdf4] border-[#bbf7d0] text-[#166534]'
                        : 'bg-white border-[rgba(0,0,0,0.06)] text-[#0a0a0a]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <code className="font-mono text-[11px]">{shortUuid(c.chunk_uuid)}</code>
                      <span className="text-[11px] text-[#6b6b6b] whitespace-nowrap">
                        hybrid: {(c.hybrid_score ?? 0).toFixed(3)}
                        {isFinal && <span className="ml-2 font-medium">cited</span>}
                      </span>
                    </div>
                    {c.snippet_preview && (
                      <p className="mt-1 text-[11px] text-[#6b6b6b] break-words">
                        {c.snippet_preview}
                      </p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {trace.rerank_applied && rerankTop.length > 0 && (
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#9e9e9e] mb-1">
              Rerank scores
            </p>
            <ul className="space-y-1">
              {rerankTop.map((r, i) => {
                const isFinal = r.chunk_uuid ? finalSet.has(r.chunk_uuid) : false
                return (
                  <li
                    key={`${r.chunk_uuid || 'na'}-${i}`}
                    className="flex items-center justify-between text-xs px-2 py-1 rounded bg-white border border-[rgba(0,0,0,0.06)]"
                  >
                    <code className="font-mono text-[11px] text-[#0a0a0a]">
                      {shortUuid(r.chunk_uuid)}
                    </code>
                    <span className="text-[11px] text-[#6b6b6b]">
                      rerank: {(r.rerank_score ?? 0).toFixed(3)}
                      {isFinal && <span className="ml-2 font-medium text-[#166534]">cited</span>}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        <div>
          <p className="text-[11px] uppercase tracking-wide text-[#9e9e9e] mb-1">
            Final cited ({(trace.final || []).length})
          </p>
          {(trace.final || []).length === 0 ? (
            <p className="text-xs text-[#6b6b6b]">None.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {(trace.final || []).map((uuid, i) => (
                <code
                  key={`${uuid || 'na'}-${i}`}
                  className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-[#f0fdf4] text-[#166534] border border-[#bbf7d0]"
                >
                  {shortUuid(uuid)}
                </code>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ToolCallsTab() {
  const [events, setEvents] = useState<ToolCallEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ToolCallEvent | null>(null)
  const [planView, setPlanView] = useState(true)

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
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-[#0a0a0a]">Tool Calls</CardTitle>
            <CardDescription className="text-[#6b6b6b]">
              Every tool invocation across chat and scheduled flows
            </CardDescription>
          </div>
          <button
            onClick={() => setPlanView(v => !v)}
            className="text-xs px-2.5 py-1 rounded-full transition-colors whitespace-nowrap"
            style={{
              background: planView ? 'rgba(74,124,89,0.10)' : 'var(--ec-surface-2, #f5f5f5)',
              color: planView ? '#4A7C59' : 'var(--ec-text-muted, #9e9e9e)',
              border: `1px solid ${planView ? 'rgba(74,124,89,0.20)' : 'var(--ec-card-border, rgba(0,0,0,0.08))'}`,
            }}
          >
            {planView ? 'Plan view ✓' : 'Plan view'}
          </button>
        </div>
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
                {planView
                  ? groupByStep(events).map(group => (
                      <>
                        {group.runId != null && group.stepIndex != null && (
                          <tr key={`header:${group.key}`}>
                            <td colSpan={6} className="pt-4 pb-1 px-4">
                              <span className="text-xs font-medium text-[#9e9e9e]">
                                Step {group.stepIndex} · {group.events.length} action{group.events.length === 1 ? '' : 's'}
                              </span>
                            </td>
                          </tr>
                        )}
                        {group.events.map((evt) => {
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
                      </>
                    ))
                  : events.map((evt) => {
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
                    })
                }
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
              {(() => {
                const trace = extractTrace(selected)
                return trace ? <RetrievalTraceSection trace={trace} /> : null
              })()}
              {(() => {
                const memoryUsed = extractMemoryUsed(selected)
                return memoryUsed ? <MemoryUsedSection entries={memoryUsed} /> : null
              })()}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  )
}
