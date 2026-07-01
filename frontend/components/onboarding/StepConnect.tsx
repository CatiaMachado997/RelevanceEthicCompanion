'use client'

import { useEffect, useState } from 'react'
import { Check, Mail, Calendar, MessageSquare } from 'lucide-react'
import { dataSourcesApi, onboardingApi } from '@/lib/api'

type SourceType = 'gmail' | 'google_calendar' | 'slack'

interface SourceConfig {
  type: SourceType
  label: string
  description: string
  icon: typeof Mail
  accent: string
}

const SOURCES: SourceConfig[] = [
  {
    type: 'gmail',
    label: 'Gmail',
    description: 'Read recent emails to surface relevant threads.',
    icon: Mail,
    accent: '#ea4335',
  },
  {
    type: 'google_calendar',
    label: 'Google Calendar',
    description: 'Sync upcoming events and meetings.',
    icon: Calendar,
    accent: '#1a73e8',
  },
  {
    type: 'slack',
    label: 'Slack',
    description: 'Surface channel conversations for team context.',
    icon: MessageSquare,
    accent: '#611f69',
  },
]

interface StepConnectProps {
  onContinue: () => void
  onSkip: () => void
}

/**
 * Step 1 — connect a data source.
 *
 * The OAuth start URL we use here is the existing
 * `/api/data-sources/oauth/{type}/authorize` endpoint, which doesn't accept a
 * `return_to` parameter. So instead of intercepting the redirect, we set
 * `localStorage.ec_onboarding_in_progress = '1'` before kicking OAuth off; the
 * /onboarding page picks that up to show the right step when the user gets
 * bounced back via /dashboard/integrations. We also append `?from=onboarding=1`
 * to the integrations page (handled there) for a "continue setup" banner.
 */
export function StepConnect({ onContinue, onSkip }: StepConnectProps) {
  const [connectedTypes, setConnectedTypes] = useState<Set<SourceType>>(new Set())
  const [loading, setLoading] = useState(true)
  const [connectingType, setConnectingType] = useState<SourceType | null>(null)

  const refresh = async () => {
    try {
      const state = await onboardingApi.state()
      // We get the per-source status from the data-sources endpoint to know
      // which row to flip — onboardingApi.state only gives us a coarse boolean.
      const sources = await dataSourcesApi.list()
      const connected = new Set<SourceType>()
      for (const s of sources.sources) {
        if (s.status === 'synced' || s.status === 'sync_needed' || s.status === 'token_expired') {
          connected.add(s.source_type as SourceType)
        }
      }
      setConnectedTypes(connected)
      // Also note whether onboarding considers this step "done" — we use it
      // to gate the Continue button, which is more permissive than the
      // per-source flags below (e.g. counts a "disabled" source as data).
      void state
    } catch (e) {
      console.warn('[onboarding] failed to load source status', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // Refresh on focus — e.g. user comes back from OAuth tab.
    const onFocus = () => refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleConnect = async (type: SourceType) => {
    setConnectingType(type)
    try {
      // Set a marker so /onboarding can route the user back to step 1 after
      // OAuth lands them on /dashboard/integrations.
      try {
        localStorage.setItem('ec_onboarding_in_progress', '1')
      } catch {
        // localStorage may be disabled — non-fatal, banner just won't show.
      }
      const { authorization_url } = await dataSourcesApi.getAuthUrl(type)
      window.location.href = authorization_url
    } catch (e) {
      console.error('[onboarding] connect failed', e)
      setConnectingType(null)
    }
  }

  const anyConnected = connectedTypes.size > 0

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2
          className="text-2xl mb-1.5"
          style={{ fontFamily: 'var(--font-fraunces)', color: 'var(--ec-text)', fontWeight: 400 }}
        >
          Bring in your context
        </h2>
        <p className="text-sm" style={{ color: 'var(--ec-text-muted)' }}>
          Connect at least one source so your companion has real context to work with.
          You can always add more later.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {SOURCES.map(({ type, label, description, icon: Icon, accent }) => {
          const isConnected = connectedTypes.has(type)
          const isLoadingThis = connectingType === type
          return (
            <div
              key={type}
              className="flex items-center gap-3 p-3 rounded-xl"
              style={{
                background: 'var(--ec-card-bg)',
                border: '1px solid var(--ec-card-border)',
              }}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: `${accent}15`, color: accent }}
              >
                <Icon size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>
                  {label}
                </p>
                <p className="text-xs truncate" style={{ color: 'var(--ec-text-muted)' }}>
                  {description}
                </p>
              </div>
              {isConnected ? (
                <span
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{
                    background: 'rgba(74,124,89,0.10)',
                    color: '#4A7C59',
                    border: '1px solid rgba(74,124,89,0.25)',
                  }}
                >
                  <Check size={11} />
                  Connected
                </span>
              ) : (
                <button
                  onClick={() => handleConnect(type)}
                  disabled={isLoadingThis || loading}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-opacity hover:opacity-90 disabled:opacity-50"
                  style={{ background: accent, color: '#ffffff' }}
                >
                  {isLoadingThis ? 'Opening…' : 'Connect'}
                </button>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between mt-2">
        <button
          onClick={onSkip}
          className="text-sm transition-opacity hover:opacity-70"
          style={{ color: 'var(--ec-text-muted)' }}
        >
          Skip for now
        </button>
        <button
          onClick={onContinue}
          disabled={!anyConnected}
          className="px-5 py-2 rounded-xl text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: '#111111', color: '#ffffff' }}
        >
          Continue
        </button>
      </div>
    </div>
  )
}
