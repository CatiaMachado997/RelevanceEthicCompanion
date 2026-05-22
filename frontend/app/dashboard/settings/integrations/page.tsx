'use client'

import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { IntegrationCard } from '@/components/settings/IntegrationCard'
import { connectorsApi, type ConnectorStatus } from '@/lib/api'

const SUPPORTED = ['gmail', 'slack', 'google_calendar'] as const

export default function IntegrationsPage() {
  const [rows, setRows] = useState<ConnectorStatus[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await connectorsApi.list()
      // Ensure all supported sources are represented even if backend omits them.
      const byType = new Map(r.connectors.map(c => [c.source_type, c]))
      const merged: ConnectorStatus[] = SUPPORTED.map(
        st =>
          byType.get(st) ?? {
            source_type: st,
            connected: false,
            last_sync: null,
            items_count: 0,
            error: null,
          },
      )
      setRows(merged)
    } catch (e) {
      console.error('[integrations] load failed:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="max-w-4xl space-y-4 md:space-y-6">
      <PageHeader
        title="Integrations"
        subtitle="Connect your accounts so chat can cite emails, Slack messages, and calendar events."
      />

      {loading ? (
        <div className="text-sm" style={{ color: '#9e9e9e' }}>
          Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map(row => (
            <IntegrationCard
              key={row.source_type}
              source_type={row.source_type}
              connected={row.connected}
              last_sync_at={row.last_sync}
              items_count={row.items_count}
              error={row.error}
              onChange={load}
            />
          ))}
        </div>
      )}
    </div>
  )
}
