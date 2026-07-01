'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, CalendarRange } from 'lucide-react'
import { weeklyReviewApi, type WeeklyReview } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export function WeeklyReviewCard() {
  const [data, setData] = useState<WeeklyReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    weeklyReviewApi
      .get()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (failed) return null

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <CalendarRange size={14} className="text-[#6b6b6b]" />
          <span
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: 'var(--ec-text-subtle)' }}
          >
            Weekly review
          </span>
        </div>

        {loading || !data ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-3/4 rounded" />
            <Skeleton className="h-4 w-1/2 rounded" />
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm" style={{ color: 'var(--ec-text)' }}>
              <span className="font-medium">Last week:</span>{' '}
              {data.completed_tasks.length} done,{' '}
              {data.completed_milestones.length} milestone
              {data.completed_milestones.length === 1 ? '' : 's'} ·{' '}
              <span
                className={
                  data.carry_over_tasks.length > 0
                    ? 'text-[#B04A3A]'
                    : ''
                }
              >
                {data.carry_over_tasks.length} carry-over
              </span>
            </p>
            <p className="text-sm" style={{ color: 'var(--ec-text)' }}>
              <span className="font-medium">This week:</span>{' '}
              {data.upcoming_tasks.length} due,{' '}
              {data.upcoming_milestones.length} milestone
              {data.upcoming_milestones.length === 1 ? '' : 's'}
            </p>
          </div>
        )}

        <Link
          href="/dashboard/weekly-review"
          className="mt-3 inline-flex items-center gap-1 text-xs hover:opacity-70 transition-opacity"
          style={{ color: '#4A7C59' }}
        >
          Open weekly review <ArrowRight size={11} />
        </Link>
      </CardContent>
    </Card>
  )
}

export default WeeklyReviewCard
