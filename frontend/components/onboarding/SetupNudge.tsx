'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { useOnboardingState } from '@/hooks/useOnboardingState'

const DISMISSED_KEY = 'ec_onboarding_nudge_dismissed'

/**
 * Tiny "Finish setting up · N of 3 done" tile that lives at the top of the
 * sidebar until the user has completed the wizard or fully set up their
 * account by hand.
 *
 * Visible when:
 *   - state has loaded, AND
 *   - any of the three setup pieces is missing (data source / value / goal),
 *     AND
 *   - the user hasn't dismissed the nudge in this browser
 *
 * Dismissal is per-browser (localStorage) — the nudge will reappear on
 * another device or after clearing storage if setup is still incomplete.
 * That's intentional: we want the cue back when the user might have
 * forgotten about it, not stuck off forever.
 */
export function SetupNudge() {
  const { data } = useOnboardingState()
  const [dismissed, setDismissed] = useState(true) // default true so we don't flash before reading localStorage

  useEffect(() => {
    if (typeof window === 'undefined') return
    setDismissed(localStorage.getItem(DISMISSED_KEY) === '1')
  }, [])

  if (!data) return null

  const done =
    (data.has_data_source ? 1 : 0) +
    (data.has_value ? 1 : 0) +
    (data.has_goal ? 1 : 0)
  const complete = done === 3

  // Already dismissed, or there's nothing left to nudge about.
  if (dismissed || complete) return null

  const handleDismiss = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (typeof window !== 'undefined') {
      localStorage.setItem(DISMISSED_KEY, '1')
    }
    setDismissed(true)
  }

  return (
    <Link
      href="/onboarding"
      className="mx-2 mt-2 mb-1 flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-colors hover:bg-black/5"
      style={{
        background: 'rgba(74,124,89,0.08)',
        border: '1px solid rgba(74,124,89,0.20)',
      }}
    >
      <div
        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: '#4A7C59' }}
      >
        <Sparkles size={13} color="#fff" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium leading-tight" style={{ color: 'var(--ec-text)' }}>
          Finish setting up
        </p>
        <p className="text-[10px] mt-0.5" style={{ color: 'var(--ec-text-muted)' }}>
          {done} of 3 done · Continue →
        </p>
      </div>
      <button
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="shrink-0 w-5 h-5 flex items-center justify-center rounded transition-opacity opacity-50 hover:opacity-100"
      >
        <X size={11} style={{ color: 'var(--ec-text-muted)' }} />
      </button>
    </Link>
  )
}
