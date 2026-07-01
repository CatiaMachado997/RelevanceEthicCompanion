'use client'

import { useState } from 'react'
import { valuesApi } from '@/lib/api'

const PLACEHOLDERS = [
  "Don't ping me after 7pm",
  'Avoid manipulative phrasing',
  'Prefer concise answers',
]

interface StepValuesProps {
  onContinue: () => void
  onSkip: () => void
}

/**
 * Step 2 — three optional "boundaries" the user wants the assistant to honor.
 * On Continue we POST every non-empty trimmed input as a `boundary`-typed
 * value with priority 5. Failures are logged but never block progress —
 * onboarding shouldn't get stuck on a flaky network.
 */
export function StepValues({ onContinue, onSkip }: StepValuesProps) {
  const [values, setValues] = useState<string[]>(['', '', ''])
  const [submitting, setSubmitting] = useState(false)

  const handleContinue = async () => {
    setSubmitting(true)
    const trimmed = values.map((v) => v.trim()).filter((v) => v.length > 0)
    if (trimmed.length === 0) {
      onContinue()
      return
    }
    await Promise.all(
      trimmed.map((value) =>
        valuesApi
          .create({ type: 'boundary', value, priority: 5 })
          .catch((e) => {
            console.warn('[onboarding] failed to create value', value, e)
          }),
      ),
    )
    setSubmitting(false)
    onContinue()
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2
          className="text-2xl mb-1.5"
          style={{ fontFamily: 'var(--font-fraunces)', color: 'var(--ec-text)', fontWeight: 400 }}
        >
          What matters to you?
        </h2>
        <p className="text-sm" style={{ color: 'var(--ec-text-muted)' }}>
          Tell your companion what to honor. These boundaries are sacred —
          they&apos;ll never be ignored, even &ldquo;just this once.&rdquo;
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {values.map((v, i) => (
          <div key={i} className="flex flex-col gap-1">
            <label
              className="text-xs font-medium"
              style={{ color: 'var(--ec-text-muted)' }}
            >
              Something you want the assistant to honor
            </label>
            <input
              type="text"
              value={v}
              onChange={(e) =>
                setValues((prev) => {
                  const next = [...prev]
                  next[i] = e.target.value
                  return next
                })
              }
              placeholder={PLACEHOLDERS[i]}
              className="px-3 py-2 rounded-lg text-sm outline-none transition-colors"
              style={{
                background: 'var(--ec-card-bg)',
                border: '1px solid var(--ec-card-border)',
                color: 'var(--ec-text)',
              }}
            />
          </div>
        ))}
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
