'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { dataSourcesApi } from '@/lib/api'
import { RefreshCw, CheckCircle2, AlertCircle, Zap, Plug } from 'lucide-react'

type SourceType = 'google_calendar' | 'gmail' | 'slack'

interface ConnectedSource {
  source_type: string
  last_sync?: string | null
  enabled: boolean
  status?: string
  item_count?: number
  sync_error?: string | null
  sync_error_count?: number
}

// Brand-specific configs for each integration
const INTEGRATIONS = [
  {
    type: 'google_calendar' as SourceType,
    label: 'Google Calendar',
    description: 'Sync upcoming events and meeting context so ESL can factor your schedule into decisions.',
    icon: GoogleCalendarIcon,
    accentColor: '#1a73e8',
    bgGradient: 'linear-gradient(135deg, #e8f0fe 0%, #f8f9ff 100%)',
    borderColor: '#c5d8fc',
    benefits: ['Meeting context awareness', 'Schedule-aware decisions', 'Event summarisation'],
  },
  {
    type: 'gmail' as SourceType,
    label: 'Gmail',
    description: 'Read recent emails to surface relevant threads and help ESL make informed recommendations.',
    icon: GmailIcon,
    accentColor: '#ea4335',
    bgGradient: 'linear-gradient(135deg, #fce8e6 0%, #fff8f7 100%)',
    borderColor: '#f5c6c2',
    benefits: ['Thread context', 'Sender recognition', 'Priority detection'],
  },
  {
    type: 'slack' as SourceType,
    label: 'Slack',
    description: 'Surface channel conversations so ESL understands your team context and collaboration patterns.',
    icon: SlackIcon,
    accentColor: '#611f69',
    bgGradient: 'linear-gradient(135deg, #f5edf7 0%, #fdf9ff 100%)',
    borderColor: '#dfc6e5',
    benefits: ['Channel context', 'Team sentiment', 'Collaboration insights'],
  },
]

// SVG icons for each service
function GoogleCalendarIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="4" width="18" height="17" rx="2" fill="white" stroke="#dadce0" strokeWidth="1.5"/>
      <rect x="3" y="4" width="18" height="5" rx="1" fill="#1a73e8"/>
      <rect x="7" y="2" width="2" height="4" rx="1" fill="#1a73e8"/>
      <rect x="15" y="2" width="2" height="4" rx="1" fill="#1a73e8"/>
      <text x="12" y="17" textAnchor="middle" fontSize="7" fontWeight="700" fill="#1a73e8">12</text>
    </svg>
  )
}

function GmailIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="5" width="20" height="14" rx="2" fill="white" stroke="#dadce0" strokeWidth="1.5"/>
      <path d="M2 7l10 7 10-7" stroke="#ea4335" strokeWidth="1.5" fill="none"/>
      <path d="M2 7l4 4M22 7l-4 4" stroke="#fbbc04" strokeWidth="1.5"/>
    </svg>
  )
}

function SlackIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M6.5 14.5a2 2 0 01-2-2v-1a2 2 0 114 0v1a2 2 0 01-2 2z" fill="#e01e5a"/>
      <path d="M10 10.5H9a2 2 0 010-4h1a2 2 0 010 4z" fill="#36c5f0"/>
      <path d="M17.5 9.5a2 2 0 012 2v1a2 2 0 11-4 0v-1a2 2 0 012-2z" fill="#2eb67d"/>
      <path d="M14 13.5h1a2 2 0 010 4h-1a2 2 0 010-4z" fill="#ecb22e"/>
    </svg>
  )
}

function IntegrationsContent() {
  const [connected, setConnected] = useState<ConnectedSource[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<SourceType | null>(null)
  const [flash, setFlash] = useState<SourceType | null>(null)
  const [errorFlash, setErrorFlash] = useState<string | null>(null)
  const [stats, setStats] = useState<Record<string, number>>({})
  const searchParams = useSearchParams()

  const loadConnected = async () => {
    try {
      const r = await dataSourcesApi.list()
      setConnected((r.sources ?? []) as ConnectedSource[])
      try {
        const s = await dataSourcesApi.stats()
        setStats(s)
      } catch {
        // stats are non-critical
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadConnected() }, [])

  useEffect(() => {
    const connectedParam = searchParams.get('connected') as SourceType | null
    if (connectedParam) {
      loadConnected()
      setFlash(connectedParam)
      setTimeout(() => setFlash(null), 3000)
    }
    const errorParam = searchParams.get('error')
    if (errorParam) {
      loadConnected()
      const integration = INTEGRATIONS.find(i => errorParam.startsWith(i.type))
      const label = integration?.label ?? 'Service'
      let msg: string
      if (errorParam.includes('access_denied') || errorParam.includes('denied')) {
        msg = `${label} connection cancelled. You can connect it any time.`
      } else if (errorParam.includes('auth_failed')) {
        msg = 'Session expired. Refresh the page and try connecting again.'
      } else if (errorParam.includes('server_error')) {
        msg = `${label} connection failed due to a server error. Please try again.`
      } else if (errorParam.includes('failed')) {
        msg = `${label} connected but the initial sync failed. Try syncing manually.`
      } else {
        msg = `Could not connect ${label}. Please try again.`
      }
      setErrorFlash(msg)
      setTimeout(() => setErrorFlash(null), 6000)
    }
  }, [searchParams])

  const isConnected = (type: SourceType) => connected.some(s => s.source_type === type)
  const lastSync = (type: SourceType) => connected.find(s => s.source_type === type)?.last_sync

  const handleConnect = async (type: SourceType) => {
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(type)
      window.location.href = authorization_url
    } catch (e) {
      console.error(e)
      const label = INTEGRATIONS.find(i => i.type === type)?.label ?? type
      setErrorFlash(`Could not start ${label} connection. Make sure you're signed in and try again.`)
      setTimeout(() => setErrorFlash(null), 6000)
    }
  }

  const handleDisconnect = async (type: SourceType) => {
    try {
      await dataSourcesApi.disconnect(type)
      setConnected(prev => prev.filter(s => s.source_type !== type))
    } catch (e) {
      console.error(e)
    }
  }

  const handleSync = async (type: SourceType) => {
    setSyncing(type)
    try {
      await dataSourcesApi.sync(type)
      await loadConnected()
    } catch (e) {
      console.error(e)
    } finally {
      setSyncing(null)
    }
  }

  const connectedCount = INTEGRATIONS.filter(i => isConnected(i.type)).length

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#1c1520' }}>Integrations</h2>
          <p className="text-sm mt-0.5" style={{ color: '#695e6e' }}>
            Connect your apps to give ESL real context about your work and life.
          </p>
        </div>
        {!loading && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium" style={{
            background: connectedCount > 0 ? '#f0f7f2' : '#f5f2ef',
            color: connectedCount > 0 ? '#4A7C59' : '#7a6e65',
            border: `1px solid ${connectedCount > 0 ? '#c8e6d3' : '#e4dcd7'}`,
          }}>
            <Zap size={11} />
            {connectedCount} of {INTEGRATIONS.length} connected
          </div>
        )}
      </div>

      {/* Flash success banner */}
      {flash && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm animate-fade-in" style={{
          background: '#f0f7f2',
          border: '1px solid #c8e6d3',
          color: '#2d6a4f',
        }}>
          <CheckCircle2 size={15} />
          <span><strong>{INTEGRATIONS.find(i => i.type === flash)?.label}</strong> connected successfully.</span>
        </div>
      )}

      {/* Flash error/warning banner */}
      {errorFlash && (() => {
        const isSoft = errorFlash.includes('cancelled') || errorFlash.includes('any time')
        return (
          <div className="flex items-center justify-between gap-2 px-4 py-3 rounded-xl text-sm" style={{
            background: isSoft ? '#fff8f0' : 'rgba(176,74,58,0.07)',
            border: `1px solid ${isSoft ? '#f5d9b0' : 'rgba(176,74,58,0.25)'}`,
            color: isSoft ? '#8a5c1a' : '#B04A3A',
          }}>
            <div className="flex items-center gap-2">
              <AlertCircle size={15} />
              <span>{errorFlash}</span>
            </div>
            <button onClick={() => setErrorFlash(null)} className="shrink-0 opacity-50 hover:opacity-100 transition-opacity text-base leading-none">×</button>
          </div>
        )
      })()}

      {/* Empty state — shown when nothing is connected yet */}
      {connectedCount === 0 && !loading && (
        <div className="py-10 text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
            <Plug size={20} style={{ color: 'var(--ec-text-subtle)' }} />
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No integrations connected</p>
            <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
              Connect Calendar and Gmail so Ethic Companion knows your schedule and context.
            </p>
          </div>
        </div>
      )}

      {/* Integration cards */}
      <div className="space-y-3">
        {INTEGRATIONS.map(({ type, label, description, icon: Icon, accentColor, bgGradient, borderColor, benefits }) => {
          const isConn = isConnected(type)
          const sync = lastSync(type)
          const isSyncing = syncing === type

          return (
            <div
              key={type}
              className="rounded-2xl overflow-hidden transition-all"
              style={{
                border: isConn ? `1px solid ${borderColor}` : '1px solid #e4dee7',
                opacity: loading ? 0.5 : 1,
              }}
            >
              {/* Card inner */}
              <div
                className="p-5"
                style={{ background: isConn ? bgGradient : '#ffffff' }}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* Left: icon + info */}
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{
                      background: '#ffffff',
                      border: '1px solid rgba(0,0,0,0.08)',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                    }}>
                      <Icon size={20} />
                    </div>

                    {/* Info */}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="text-sm font-semibold" style={{ color: '#1c1520' }}>{label}</span>
                        {isConn && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium" style={{
                            background: '#e6f4ee',
                            color: '#2d6a4f',
                          }}>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#4A7C59]" />
                            Connected
                          </span>
                        )}
                      </div>
                      <p className="text-xs leading-relaxed" style={{ color: '#695e6e' }}>
                        {isConn && sync
                          ? `Last synced ${new Date(sync).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
                          : description}
                      </p>
                      {/* Item count — only when connected and count > 0 */}
                      {isConn && (stats[type] ?? 0) > 0 && (
                        <span className="inline-flex items-center gap-1 mt-1 text-[10px]" style={{ color: '#6b6b6b' }}>
                          <span className="font-medium">{(stats[type] ?? 0).toLocaleString()}</span> items synced
                        </span>
                      )}
                      {/* Sync error indicator */}
                      {isConn && connected.find(src => src.source_type === type)?.sync_error && (
                        <p className="mt-1 text-[10px]" style={{ color: '#B04A3A' }}>
                          ⚠ Last sync failed — try syncing again
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Right: actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {isConn ? (
                      <>
                        <button
                          onClick={() => handleSync(type)}
                          disabled={isSyncing}
                          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-40"
                          style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.08)' }}
                          title={`Sync ${label}`}
                          aria-label={`Sync ${label}`}
                        >
                          <RefreshCw size={13} style={{ color: '#695e6e' }} className={isSyncing ? 'animate-spin' : ''} />
                        </button>
                        <button
                          onClick={() => handleDisconnect(type)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                          style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.1)', color: '#695e6e' }}
                        >
                          Disconnect
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleConnect(type)}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all hover:opacity-90 active:scale-[0.98]"
                        style={{ background: accentColor, color: '#ffffff' }}
                      >
                        Connect
                      </button>
                    )}
                  </div>
                </div>

                {/* Benefits row — only shown when not connected */}
                {!isConn && (
                  <div className="flex flex-wrap gap-1.5 mt-4">
                    {benefits.map(b => (
                      <span key={b} className="px-2.5 py-1 rounded-full text-[11px]" style={{
                        background: '#f5f2ef',
                        color: '#7a6e65',
                        border: '1px solid #ede8e3',
                      }}>
                        {b}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Info footer */}
      <div className="flex items-start gap-2 px-4 py-3 rounded-xl" style={{
        background: '#f9f6fa',
        border: '1px solid #e4dee7',
      }}>
        <AlertCircle size={13} className="mt-0.5 shrink-0" style={{ color: '#b0a6b4' }} />
        <p className="text-xs leading-relaxed" style={{ color: '#9e9e9e' }}>
          Ethic Companion only reads data — it never sends messages or modifies your accounts.
          All data is processed locally to inform ESL decisions and never stored externally.
        </p>
      </div>
    </div>
  )
}

export default function IntegrationsPage() {
  return (
    <Suspense fallback={<div className="h-40 flex items-center justify-center text-sm" style={{ color: '#b0a6b4' }}>Loading...</div>}>
      <IntegrationsContent />
    </Suspense>
  )
}
