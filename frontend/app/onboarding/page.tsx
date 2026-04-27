'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Shield, Sparkles } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { onboardingApi } from '@/lib/api'
import { StepConnect } from '@/components/onboarding/StepConnect'
import { StepValues } from '@/components/onboarding/StepValues'
import { StepGoal } from '@/components/onboarding/StepGoal'

const TOTAL_STEPS = 3

function StepDots({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6" aria-label={`Step ${current} of ${TOTAL_STEPS}`}>
      {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map((n) => {
        const active = n === current
        const done = n < current
        return (
          <div
            key={n}
            className="flex items-center gap-2"
          >
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-semibold transition-all"
              style={{
                background: active ? '#111111' : done ? '#4A7C59' : 'var(--ec-surface-2)',
                color: active || done ? '#ffffff' : 'var(--ec-text-subtle)',
                border: active || done ? 'none' : '1px solid var(--ec-card-border)',
              }}
            >
              {n}
            </div>
            {n < TOTAL_STEPS && (
              <div
                className="w-6 h-px"
                style={{ background: done ? '#4A7C59' : 'var(--ec-card-border)' }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

function CompanionLogo() {
  return (
    <div className="relative">
      <div
        className="w-12 h-12 rounded-2xl flex items-center justify-center"
        style={{ background: '#111111' }}
      >
        <Shield size={20} color="white" />
      </div>
      <div
        className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 flex items-center justify-center"
        style={{ background: '#4A7C59', borderColor: 'var(--ec-page-bg)' }}
      >
        <Sparkles size={10} color="#fff" />
      </div>
    </div>
  )
}

function OnboardingWizard() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()

  // Parse step from URL — never trust it blind, clamp to [1, TOTAL_STEPS].
  const rawStep = parseInt(searchParams.get('step') ?? '1', 10)
  const step = Number.isFinite(rawStep) && rawStep >= 1 && rawStep <= TOTAL_STEPS
    ? rawStep
    : 1

  const [completing, setCompleting] = useState(false)
  const [showFinal, setShowFinal] = useState(false)

  // Once the wizard has loaded, the in-progress marker is no longer needed.
  // Clear it so a future hard-refresh of /dashboard/integrations doesn't keep
  // showing the "continue setup" banner forever.
  useEffect(() => {
    try {
      localStorage.removeItem('ec_onboarding_in_progress')
    } catch {
      // localStorage may be disabled — non-fatal.
    }
  }, [])

  const goToStep = (n: number) => {
    const clamped = Math.max(1, Math.min(TOTAL_STEPS, n))
    router.replace(`/onboarding?step=${clamped}`)
  }

  const finishOnboarding = async () => {
    setCompleting(true)
    try {
      await onboardingApi.complete()
    } catch (e) {
      // The complete endpoint is idempotent — even if it fails we still want
      // the user to land on the dashboard. Just log it.
      console.warn('[onboarding] failed to mark complete', e)
    }
    // Invalidate any caches that consumers might have set up. The standard
    // keys we publish from this Sprint are ["onboarding-state"] and
    // ["auth", "me"]; both are no-ops if nothing has subscribed yet.
    try {
      queryClient.invalidateQueries({ queryKey: ['onboarding-state'] })
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    } catch {
      // ignore
    }
    router.replace('/dashboard/today')
  }

  // Step 3's Continue / Skip both move us to the "You're set" final screen,
  // which then has its own CTA to finishOnboarding. This split keeps the
  // success moment distinct from any saving spinner.
  const handleStep3Done = () => setShowFinal(true)

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-10"
      style={{ background: 'var(--ec-page-bg)' }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-7"
        style={{
          background: 'var(--ec-card-bg)',
          border: '1px solid var(--ec-card-border)',
          boxShadow: 'var(--ec-card-shadow, 0 8px 32px rgba(0,0,0,0.06))',
        }}
      >
        {showFinal ? (
          <div className="flex flex-col items-center text-center gap-5 py-4">
            <CompanionLogo />
            <div>
              <p
                className="text-[11px] font-medium uppercase tracking-[0.2em] mb-2"
                style={{ color: 'var(--ec-text-subtle)' }}
              >
                Ethic Companion
              </p>
              <h2
                className="text-2xl mb-2"
                style={{ fontFamily: 'var(--font-fraunces)', color: 'var(--ec-text)', fontWeight: 400 }}
              >
                You&apos;re set
              </h2>
              <p className="text-sm" style={{ color: 'var(--ec-text-muted)' }}>
                Your companion is ready, guided by your values and protected by ESL.
              </p>
            </div>
            <button
              onClick={finishOnboarding}
              disabled={completing}
              className="px-5 py-2 rounded-xl text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: '#111111', color: '#ffffff' }}
            >
              {completing ? 'Just a moment…' : 'Take me to Today'}
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-center mb-5">
              <CompanionLogo />
            </div>
            <StepDots current={step} />
            {step === 1 && (
              <StepConnect
                onContinue={() => goToStep(2)}
                onSkip={() => goToStep(2)}
              />
            )}
            {step === 2 && (
              <StepValues
                onContinue={() => goToStep(3)}
                onSkip={() => goToStep(3)}
              />
            )}
            {step === 3 && (
              <StepGoal
                onContinue={handleStep3Done}
                onSkip={handleStep3Done}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function OnboardingPage() {
  return (
    <Suspense
      fallback={
        <div
          className="min-h-screen flex items-center justify-center text-sm"
          style={{ background: 'var(--ec-page-bg)', color: 'var(--ec-text-subtle)' }}
        >
          Loading…
        </div>
      }
    >
      <OnboardingWizard />
    </Suspense>
  )
}
