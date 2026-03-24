'use client'

import { useState, useEffect } from 'react'
import { Calendar, Mail, Slack as SlackIcon, CheckCircle2, RefreshCw, Unlink } from 'lucide-react'
import { useSearchParams } from 'next/navigation'
import { dataSourcesApi } from '@/lib/api'

type SourceType = 'google_calendar' | 'gmail' | 'slack'

interface ConnectedSource {
  source_type: SourceType
  last_sync?: string
  enabled: boolean
}

const INTEGRATIONS: { type: SourceType; label: string; description: string; icon: React.ElementType }[] = [
  {
    type: 'google_calendar',
    label: 'Google Calendar',
    description: 'Sync your calendar events for ESL context awareness.',
    icon: Calendar,
  },
  {
    type: 'gmail',
    label: 'Gmail',
    description: 'Read recent emails to surface relevant context.',
    icon: Mail,
  },
  {
    type: 'slack',
    label: 'Slack',
    description: 'Read channel messages for work context.',
    icon: SlackIcon,
  },
]

export default function IntegrationsPage() {
  const [connected, setConnected] = useState<ConnectedSource[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState<SourceType | null>(null)
  const searchParams = useSearchParams()

  const loadConnected = async () => {
    try {
      const r = await dataSourcesApi.list()
      setConnected(r.sources ?? [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConnected()
  }, [])

  useEffect(() => {
    const connectedParam = searchParams.get('connected')
    if (connectedParam) loadConnected()
  }, [searchParams])

  const isConnected = (type: SourceType) => connected.some(s => s.source_type === type)
  const lastSync = (type: SourceType) => connected.find(s => s.source_type === type)?.last_sync

  const handleConnect = async (type: SourceType) => {
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(type)
      window.location.href = authorization_url
    } catch (e) {
      console.error(e)
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

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold" style={{ color: '#332b36' }}>Integrations</h2>
        <p className="text-sm mt-0.5" style={{ color: '#695e6e' }}>
          Connect your apps so ESL can protect you in context.
        </p>
      </div>

      <div className="grid gap-4">
        {INTEGRATIONS.map(({ type, label, description, icon: Icon }) => {
          const isConn = isConnected(type)
          const sync = lastSync(type)
          return (
            <div
              key={type}
              className="rounded-2xl p-5 flex items-center justify-between gap-4"
              style={{
                background: '#ffffff',
                border: '1px solid #e4dee7',
                boxShadow: '0 1px 3px rgba(42,34,45,0.08)',
                opacity: loading ? 0.6 : 1,
              }}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: '#f9f6fa' }}>
                  <Icon size={18} style={{ color: '#332b36' }} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium" style={{ color: '#332b36' }}>{label}</p>
                    {isConn && <CheckCircle2 size={14} style={{ color: '#4A7C59' }} />}
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: '#b0a6b4' }}>
                    {isConn && sync
                      ? `Last synced ${new Date(sync).toLocaleString()}`
                      : description}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {isConn ? (
                  <>
                    <button
                      onClick={() => handleSync(type)}
                      disabled={syncing === type}
                      className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors disabled:opacity-40"
                      aria-label={`Sync ${label}`}
                    >
                      <RefreshCw size={14} style={{ color: '#695e6e' }} className={syncing === type ? 'animate-spin' : ''} />
                    </button>
                    <button
                      onClick={() => handleDisconnect(type)}
                      className="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors hover:bg-black/5"
                      style={{ borderColor: '#e4dee7', color: '#695e6e' }}
                    >
                      Disconnect
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => handleConnect(type)}
                    className="px-4 py-1.5 rounded-[14px] text-xs font-medium transition-opacity hover:opacity-80"
                    style={{ background: '#332b36', color: '#ffffff' }}
                  >
                    Connect
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
