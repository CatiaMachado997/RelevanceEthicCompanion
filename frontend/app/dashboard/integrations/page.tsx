'use client'

import { useState, useEffect, useRef, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { dataSourcesApi, toolMarketplaceApi, ToolDefinition, ConnectedTool, connectorsApi, ConnectorIndexStatus } from '@/lib/api'
import { CatalogueCard } from '@/components/CatalogueCard'
import { RefreshCw, CheckCircle2, AlertCircle, Zap, Plug } from 'lucide-react'
import { toast } from '@/lib/toast'

type SourceType = 'google_calendar' | 'gmail' | 'slack'

interface ConnectedSource {
  source_type: string
  last_sync?: string | null
  enabled: boolean
  status: 'synced' | 'sync_needed' | 'token_expired' | 'disconnected'
  item_count?: number
  sync_error?: string | null
  sync_error_count?: number
  recent_items?: Array<{ title: string; item_at: string | null }>
  token_expires_at?: string | null
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

function formatRelativeTime(isoStr: string | null | undefined): string {
  if (!isoStr) return ''
  const date = new Date(isoStr)
  const diffMs = date.getTime() - Date.now()
  const absHours = Math.round(Math.abs(diffMs) / (1000 * 60 * 60))
  const isPast = diffMs < 0
  if (absHours < 1) return 'now'
  if (absHours < 24) return isPast ? `${absHours}h ago` : `in ${absHours}h`
  const days = Math.round(absHours / 24)
  return isPast ? `${days}d ago` : `in ${days}d`
}

function StatusBadge({ status }: { status: ConnectedSource['status'] }) {
  if (status === 'synced') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#e6f4ee', color: '#2d6a4f', border: '1px solid #c8e6d3' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#4A7C59' }} />
        Synced
      </span>
    )
  }
  if (status === 'sync_needed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: '#fff8e1', color: '#8a6600', border: '1px solid #ffe082' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#f59e0b' }} />
        Sync needed
      </span>
    )
  }
  if (status === 'token_expired') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
        style={{ background: 'rgba(176,74,58,0.08)', color: '#B04A3A', border: '1px solid rgba(176,74,58,0.25)' }}>
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#B04A3A' }} />
        Token expired
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
      style={{ background: '#f5f2ef', color: '#7a6e65', border: '1px solid #e4dcd7' }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#9e9e9e' }} />
      Disconnected
    </span>
  )
}

function ConnectorStatusFooter({ source, label }: { source: SourceType; label: string }) {
  const [status, setStatus] = useState<ConnectorIndexStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [reindexing, setReindexing] = useState(false)

  const fetchStatus = async () => {
    try {
      const s = await connectorsApi.getStatus(source)
      setStatus(s)
    } catch (e) {
      console.error(`[connectors] failed to load status for ${source}`, e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source])

  const handleReindex = async () => {
    setReindexing(true)
    try {
      const result = await connectorsApi.reindex(source)
      toast.success(
        `Reindex complete for ${label}`,
        `${result.processed} processed · ${result.succeeded} succeeded · ${result.failed} failed`,
      )
      await fetchStatus()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      toast.error(`Reindex failed for ${label}`, msg)
    } finally {
      setReindexing(false)
    }
  }

  if (loading) return null
  if (!status || status.total_items === 0) return null

  const reindexNeeded = status.failed > 0 || status.pending > 0

  return (
    <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 text-[11px]" style={{ color: '#6b6b6b' }}>
          <span>
            <span className="font-semibold" style={{ color: '#1a1a1a' }}>{status.total_items}</span> synced
          </span>
          <span style={{ color: '#cfcfcf' }}>•</span>
          <span>
            <span className="font-semibold" style={{ color: '#2d6a4f' }}>{status.indexed}</span> indexed
          </span>
          {status.failed > 0 && (
            <>
              <span style={{ color: '#cfcfcf' }}>•</span>
              <span>
                <span className="font-semibold" style={{ color: '#B04A3A' }}>{status.failed}</span> failed
              </span>
            </>
          )}
          {status.pending > 0 && (
            <>
              <span style={{ color: '#cfcfcf' }}>•</span>
              <span>
                <span className="font-semibold">{status.pending}</span> pending
              </span>
            </>
          )}
        </div>
        <button
          onClick={handleReindex}
          disabled={reindexing || !reindexNeeded}
          title={!reindexNeeded ? 'Nothing to reindex.' : undefined}
          className="px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.1)', color: '#6b6b6b' }}
        >
          {reindexing ? 'Reindexing…' : 'Reindex'}
        </button>
      </div>
      {status.last_error && (
        <div className="mt-2 rounded-md p-2" style={{ background: '#fdf2f0', border: '1px solid #f5d0c8' }}>
          <div className="text-[9px] font-semibold uppercase tracking-wide mb-0.5" style={{ color: '#B04A3A' }}>
            Last error
          </div>
          <code className="text-[10px] font-mono break-all" style={{ color: '#7a3024' }}>
            {status.last_error}
          </code>
        </div>
      )}
    </div>
  )
}

function IntegrationsContent() {
  const [connected, setConnected] = useState<ConnectedSource[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<SourceType | null>(null)
  const [flash, setFlash] = useState<SourceType | null>(null)
  const [errorFlash, setErrorFlash] = useState<string | null>(null)
  const [stats, setStats] = useState<Record<string, number>>({})
  const [catalogue, setCatalogue] = useState<ToolDefinition[]>([])
  const [connectedTools, setConnectedTools] = useState<ConnectedTool[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [mcpUrl, setMcpUrl] = useState('')
  const [mcpConnecting, setMcpConnecting] = useState(false)
  const searchParams = useSearchParams()
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const loadConnected = async () => {
    try {
      const r = await dataSourcesApi.list()
      if (!mountedRef.current) return
      setConnected((r.sources ?? []) as ConnectedSource[])
      try {
        const s = await dataSourcesApi.stats()
        if (mountedRef.current) setStats(s)
      } catch {
        // stats are non-critical
      }
    } catch (e) {
      console.error(e)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }

  async function loadMarketplace() {
    try {
      const [cat, conn] = await Promise.all([
        toolMarketplaceApi.getCatalogue(),
        toolMarketplaceApi.getConnected(),
      ])
      if (!mountedRef.current) return
      setCatalogue(cat)
      setConnectedTools(conn)
    } catch (err) {
      console.error('[Marketplace] loadMarketplace failed:', err)
    }
  }

  useEffect(() => { loadConnected(); loadMarketplace() }, [])

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

  const sourceData = (type: SourceType) => connected.find(s => s.source_type === type)
  const getStatus = (type: SourceType): ConnectedSource['status'] => sourceData(type)?.status ?? 'disconnected'
  const isConnected = (type: SourceType) => {
    const s = getStatus(type)
    return s === 'synced' || s === 'sync_needed' || s === 'token_expired'
  }
  const lastSync = (type: SourceType) => sourceData(type)?.last_sync

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
    } catch (e) {
      const label = INTEGRATIONS.find(i => i.type === type)?.label ?? type
      setErrorFlash(`Sync failed for ${label}. If the problem persists, try reconnecting.`)
      setTimeout(() => setErrorFlash(null), 6000)
    } finally {
      setSyncing(null)
      await loadConnected()
    }
  }

  const handleReconnect = async (type: SourceType) => {
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(type)
      window.location.href = authorization_url
    } catch (e) {
      const label = INTEGRATIONS.find(i => i.type === type)?.label ?? type
      setErrorFlash(`Could not start ${label} reconnection. Make sure you're signed in and try again.`)
      setTimeout(() => setErrorFlash(null), 6000)
    }
  }

  async function handleConnectTool(toolId: string) {
    try {
      const url = await toolMarketplaceApi.connectComposio(toolId)
      if (url) window.location.href = url
    } catch (e) {
      console.error('[Marketplace] Failed to start Composio connect', e)
      const label = catalogue.find((t) => t.id === toolId)?.name ?? toolId
      setErrorFlash(`Could not start ${label} connection. Check that the backend is running.`)
      setTimeout(() => setErrorFlash(null), 6000)
    }
  }

  async function handleDisconnectTool(toolId: string) {
    try {
      await toolMarketplaceApi.disconnect(toolId)
      await loadMarketplace()
    } catch (e) {
      console.error('Failed to disconnect tool', e)
    }
  }

  async function handleConnectMcp() {
    if (!mcpUrl.trim()) return
    setMcpConnecting(true)
    try {
      await toolMarketplaceApi.connectMcp(mcpUrl.trim())
      setMcpUrl('')
      await loadMarketplace()
    } catch (e) {
      console.error('Failed to connect MCP', e)
    } finally {
      setMcpConnecting(false)
    }
  }

  const connectedCount = INTEGRATIONS.filter(i => isConnected(i.type)).length

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: '#1a1a1a' }}>Integrations</h2>
          <p className="text-sm mt-0.5" style={{ color: '#6b6b6b' }}>
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
          const src = sourceData(type)
          const status = getStatus(type)

          return (
            <div
              key={type}
              className="rounded-2xl overflow-hidden transition-all"
              style={{
                border: isConn ? `1px solid ${borderColor}` : '1px solid #e5e5e5',
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
                        <span className="text-sm font-semibold" style={{ color: '#1a1a1a' }}>{label}</span>
                        {isConn && <StatusBadge status={status} />}
                      </div>
                      <p className="text-xs leading-relaxed" style={{ color: '#6b6b6b' }}>
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
                      {isConn && src?.sync_error && (
                        <p className="mt-1 text-[10px]" style={{ color: '#B04A3A' }}>
                          ⚠ Last sync failed — try syncing again
                        </p>
                      )}
                      {/* Recent items preview — shown when synced and items exist */}
                      {isConn && (src?.recent_items ?? []).length > 0 && (
                        <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                          <div className="space-y-1">
                            {(src?.recent_items ?? []).slice(0, 3).map((item, i) => (
                              <p key={i} className="text-[11px] truncate" style={{ color: '#6b6b6b' }}>
                                {type === 'google_calendar'
                                  ? `${item.title} · ${formatRelativeTime(item.item_at)}`
                                  : item.title
                                }
                              </p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {isConn ? (
                      <>
                        {status === 'token_expired' ? (
                          <button
                            onClick={() => handleReconnect(type)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:opacity-90"
                            style={{ background: 'rgba(176,74,58,0.1)', border: '1px solid rgba(176,74,58,0.3)', color: '#B04A3A' }}
                          >
                            Reconnect
                          </button>
                        ) : (
                          <button
                            onClick={() => handleSync(type)}
                            disabled={isSyncing}
                            className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors disabled:opacity-40"
                            style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.08)' }}
                            title={`Sync ${label}`}
                            aria-label={`Sync ${label}`}
                          >
                            <RefreshCw size={13} style={{ color: '#6b6b6b' }} className={isSyncing ? 'animate-spin' : ''} />
                          </button>
                        )}
                        <button
                          onClick={() => handleDisconnect(type)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                          style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.1)', color: '#6b6b6b' }}
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

                {/* Connector index status footer — only shown when connected */}
                {isConn && <ConnectorStatusFooter source={type} label={label} />}

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

      {/* Tool Marketplace Catalogue */}
      {catalogue.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
            Available Tools
          </h3>
          <div className="flex flex-col gap-2">
            {catalogue.map((tool) => (
              <CatalogueCard
                key={tool.id}
                tool={tool}
                isConnected={connectedTools.some((c) => c.tool_id === tool.id && c.enabled)}
                onConnect={handleConnectTool}
                onDisconnect={handleDisconnectTool}
              />
            ))}
          </div>
        </div>
      )}

      {/* Advanced / MCP */}
      <div className="mt-6 pt-4" style={{ borderTop: '1px solid #e5e5e5' }}>
        <button
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-xs transition-colors"
          style={{ color: '#9e9e9e' }}
        >
          {showAdvanced ? 'Hide advanced options' : 'Advanced — connect a custom MCP server'}
        </button>
        {showAdvanced && (
          <div
            className="mt-3 rounded-xl p-4"
            style={{ border: '1px dashed #d4cdd8', background: '#faf8fb' }}
          >
            <p className="text-sm font-medium mb-1" style={{ color: '#1a1a1a' }}>
              Custom MCP Server
            </p>
            <p className="text-xs mb-3" style={{ color: '#6b6b6b' }}>
              Connect any Model Context Protocol server via its SSE endpoint URL.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={mcpUrl}
                onChange={(e) => setMcpUrl(e.target.value)}
                placeholder="https://my-mcp-server.com/sse"
                className="flex-1 rounded-lg px-3 py-2 text-sm focus:outline-none"
                style={{
                  background: '#ffffff',
                  border: '1px solid #d4cdd8',
                  color: '#1a1a1a',
                }}
              />
              <button
                onClick={handleConnectMcp}
                disabled={mcpConnecting || !mcpUrl.trim()}
                className="rounded-xl px-4 py-2 text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40"
                style={{ background: '#4A7C59', color: '#ffffff' }}
              >
                {mcpConnecting ? '…' : 'Connect'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Info footer */}
      <div className="flex items-start gap-2 px-4 py-3 rounded-xl" style={{
        background: '#fafafa',
        border: '1px solid #e5e5e5',
      }}>
        <AlertCircle size={13} className="mt-0.5 shrink-0" style={{ color: '#9e9e9e' }} />
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
    <Suspense fallback={<div className="h-40 flex items-center justify-center text-sm" style={{ color: '#9e9e9e' }}>Loading...</div>}>
      <IntegrationsContent />
    </Suspense>
  )
}
