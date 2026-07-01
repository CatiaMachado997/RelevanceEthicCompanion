'use client'

export interface PausedAction {
  thread_id: string
  step: number
  action_index: number
  tool: string
  category: string
  params: Record<string, unknown>
  reason: string
  trust_would_help: boolean
}

export function PausedActionPrompt({
  paused,
  onDecision,
}: {
  paused: PausedAction
  onDecision: (decision: 'approve' | 'skip' | 'cancel', trust?: boolean) => void
}) {
  return (
    <div className="rounded-xl p-3 my-2"
      style={{
        background: 'rgba(176,120,58,0.06)',
        border: '1px solid rgba(176,120,58,0.20)',
      }}>
      <div className="text-xs font-medium" style={{ color: '#9B6A2A' }}>
        Pause — confirm before running
      </div>
      <div className="text-sm mt-1" style={{ color: 'var(--ec-text)' }}>
        About to call <code className="text-xs px-1 rounded" style={{ background: 'var(--ec-surface-2)' }}>{paused.tool}</code>
      </div>
      <div className="text-xs mt-1" style={{ color: 'var(--ec-text-muted)' }}>
        {paused.reason}
      </div>
      <pre className="text-[10px] mt-2 p-2 rounded overflow-x-auto"
        style={{ background: 'var(--ec-card-bg)', border: '1px solid var(--ec-card-border)' }}>
        {JSON.stringify(paused.params, null, 2)}
      </pre>
      <div className="flex flex-wrap gap-2 mt-3">
        <button
          onClick={() => onDecision('approve', false)}
          className="px-3 py-1 rounded text-xs font-medium"
          style={{ background: '#4A7C59', color: '#fff' }}
        >Approve</button>
        <button
          onClick={() => onDecision('skip')}
          className="px-3 py-1 rounded text-xs"
          style={{ background: 'var(--ec-surface-2)', color: 'var(--ec-text)', border: '1px solid var(--ec-card-border)' }}
        >Skip</button>
        <button
          onClick={() => onDecision('cancel')}
          className="px-3 py-1 rounded text-xs"
          style={{ background: 'var(--ec-surface-2)', color: '#B04A3A', border: '1px solid var(--ec-card-border)' }}
        >Cancel turn</button>
        <button
          onClick={() => onDecision('approve', true)}
          disabled={!paused.trust_would_help}
          title={paused.trust_would_help ? '' : 'Master or category would still pause this'}
          className="px-3 py-1 rounded text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: 'var(--ec-surface-2)', color: 'var(--ec-text-muted)', border: '1px solid var(--ec-card-border)' }}
        >Trust this tool from now on</button>
      </div>
    </div>
  )
}
