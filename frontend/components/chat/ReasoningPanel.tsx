'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

export interface ActionEntry {
  step: number
  action_index: number
  tool: string
  status?: 'running' | 'ok' | 'error' | 'skipped' | 'cancelled'
  latency_ms?: number
}

export function ReasoningPanel({
  thought,
  actions,
  isStreaming,
}: {
  thought: string
  actions: ActionEntry[]
  isStreaming: boolean
}) {
  const [open, setOpen] = useState(isStreaming)
  return (
    <div className="rounded-xl mb-2"
      style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs"
        style={{ color: 'var(--ec-text-muted)' }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Reasoning {isStreaming ? '· thinking…' : `· ${actions.length} actions`}
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          {thought && (
            <div className="text-xs leading-relaxed whitespace-pre-wrap"
              style={{ color: 'var(--ec-text)' }}>
              {thought}
              {isStreaming && <span className="inline-block w-[2px] h-3 ml-0.5 align-[-0.05em] animate-pulse rounded-sm" style={{ background: 'var(--ec-text)' }} />}
            </div>
          )}
          {actions.length > 0 && (
            <ul className="space-y-1">
              {actions.map(a => (
                <li key={`${a.step}-${a.action_index}`}
                  className="flex items-center gap-2 text-xs">
                  <span style={{ color: a.status === 'ok' ? '#4A7C59'
                                  : a.status === 'error' ? '#B04A3A'
                                  : a.status === 'skipped' ? '#9B7A3D'
                                  : 'var(--ec-text-subtle)' }}>
                    {a.status === 'ok' ? '✓'
                     : a.status === 'error' ? '✗'
                     : a.status === 'skipped' ? '↷'
                     : a.status === 'cancelled' ? '⊘'
                     : '…'}
                  </span>
                  <span style={{ color: 'var(--ec-text)' }}>{a.tool}</span>
                  {a.latency_ms != null && (
                    <span style={{ color: 'var(--ec-text-subtle)' }}>· {a.latency_ms}ms</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
