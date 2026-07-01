'use client'

import { useState } from 'react'
import { goalsApi } from '@/lib/api'

interface StepGoalProps {
  onContinue: () => void
  onSkip: () => void
}

/**
 * Step 3 — seed a single goal. Title is required to submit; target_date is
 * optional. Matches `goalsApi.create`'s signature: { title, priority,
 * target_date? }. Failure is non-fatal — we log and still advance, so the
 * user never gets stuck on the last step.
 */
export function StepGoal({ onContinue, onSkip }: StepGoalProps) {
  const [title, setTitle] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleContinue = async () => {
    const trimmed = title.trim()
    if (!trimmed) {
      onContinue()
      return
    }
    setSubmitting(true)
    try {
      await goalsApi.create({
        title: trimmed,
        priority: 5,
        ...(targetDate ? { target_date: targetDate } : {}),
      })
    } catch (e) {
      console.warn('[onboarding] failed to create goal', e)
    } finally {
      setSubmitting(false)
      onContinue()
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2
          className="text-2xl mb-1.5"
          style={{ fontFamily: 'var(--font-fraunces)', color: 'var(--ec-text)', fontWeight: 400 }}
        >
          What are you working toward?
        </h2>
        <p className="text-sm" style={{ color: 'var(--ec-text-muted)' }}>
          Pick one goal you&apos;d like help with. We&apos;ll use it to keep
          suggestions aligned with what you actually care about.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium" style={{ color: 'var(--ec-text-muted)' }}>
            Goal
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ship the Q2 product launch"
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-card-bg)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium" style={{ color: 'var(--ec-text-muted)' }}>
            By when (optional)
          </label>
          <input
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm outline-none"
            style={{
              background: 'var(--ec-card-bg)',
              border: '1px solid var(--ec-card-border)',
              color: 'var(--ec-text)',
            }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between mt-2">
        <button
          onClick={onSkip}
          disabled={submitting}
          className="text-sm transition-opacity hover:opacity-70 disabled:opacity-50"
          style={{ color: 'var(--ec-text-muted)' }}
        >
          Skip for now
        </button>
        <button
          onClick={handleContinue}
          disabled={submitting}
          className="px-5 py-2 rounded-xl text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
          style={{ background: '#111111', color: '#ffffff' }}
        >
          {submitting ? 'Saving…' : 'Continue'}
        </button>
      </div>
    </div>
  )
}
