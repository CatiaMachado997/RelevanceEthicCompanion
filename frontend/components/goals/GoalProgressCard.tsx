'use client'

import { Check } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { GoalRollup } from '@/lib/api'

interface MilestoneItem {
  id: string
  title: string
  completed: boolean
  target_date?: string | null
}

interface GoalProgressCardProps {
  rollup: GoalRollup
  milestones?: MilestoneItem[]
}

function isOverdue(target_date?: string | null): boolean {
  if (!target_date) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(target_date)
  if (Number.isNaN(target.getTime())) return false
  return target < today
}

export function GoalProgressCard({ rollup, milestones }: GoalProgressCardProps) {
  const pct = Math.max(0, Math.min(100, rollup.progress_pct ?? 0))

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-baseline justify-between">
          <span
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: 'var(--ec-text-subtle)' }}
          >
            Progress
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

        <div className="text-xs space-y-0.5" style={{ color: 'var(--ec-text-muted)' }}>
          <div>
            Milestones {rollup.milestones_hit} of {rollup.milestones_total}
          </div>
          {rollup.tasks_total > 0 && (
            <div>
              Tasks {rollup.tasks_done} of {rollup.tasks_total} done
            </div>
          )}
        </div>

        {milestones && milestones.length > 0 && (
          <ul className="space-y-1.5 pt-2 border-t border-[rgba(0,0,0,0.06)]">
            {milestones.map(m => {
              const overdue = !m.completed && isOverdue(m.target_date)
              return (
                <li key={m.id} className="flex items-center gap-2">
                  <span
                    className="w-4 h-4 rounded border flex items-center justify-center shrink-0"
                    style={{
                      background: m.completed ? '#4A7C59' : 'transparent',
                      borderColor: m.completed ? '#4A7C59' : '#d4d0d6',
                    }}
                  >
                    {m.completed && <Check size={10} color="#fff" />}
                  </span>
                  <span
                    className="text-xs flex-1 truncate"
                    style={{
                      color: m.completed ? '#9e9e9e' : 'var(--ec-text)',
                      textDecoration: m.completed ? 'line-through' : 'none',
                    }}
                  >
                    {m.title}
                  </span>
                  {overdue && (
                    <span
                      className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium shrink-0"
                      style={{
                        background: 'rgba(176,74,58,0.10)',
                        color: '#B04A3A',
                        border: '1px solid rgba(176,74,58,0.25)',
                      }}
                    >
                      Overdue
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
