'use client'

import { Card, CardContent } from '@/components/ui/card'
import type { ProjectRollup } from '@/lib/api'

interface ProjectRollupCardProps {
  rollup: ProjectRollup
}

export function ProjectRollupCard({ rollup }: ProjectRollupCardProps) {
  const pct = Math.max(0, Math.min(100, rollup.completion_pct ?? 0))
  const atRisk = rollup.at_risk_count ?? 0
  const atRiskColor = atRisk > 0 ? '#B04A3A' : 'var(--ec-text-subtle)'

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-baseline justify-between">
          <span
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: 'var(--ec-text-subtle)' }}
          >
            Completion
          </span>
          <span
            className="text-2xl font-semibold tabular-nums"
            style={{ color: 'var(--ec-text)' }}
          >
            {pct}%
          </span>
        </div>

        <div
          className="h-2 rounded-full overflow-hidden"
          style={{ background: 'var(--ec-surface-2, #f5f2ef)' }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${pct}%`, background: '#1a1a1a' }}
          />
        </div>

        <div
          className="flex items-center gap-1.5 text-xs flex-wrap"
          style={{ color: 'var(--ec-text-muted)' }}
        >
          <span>
            {rollup.tasks_done} of {rollup.tasks_total} tasks done
          </span>
          <span style={{ color: 'var(--ec-text-subtle)' }}>·</span>
          <span>{rollup.tasks_open} open</span>
          <span style={{ color: 'var(--ec-text-subtle)' }}>·</span>
          <span style={{ color: atRiskColor, fontWeight: atRisk > 0 ? 600 : 400 }}>
            {atRisk} at-risk
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
