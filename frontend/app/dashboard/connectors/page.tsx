'use client'

/**
 * Sprint F Task 3 — Connector status panel.
 *
 * Surfaces what's actually flowing through the sync→index pipeline so the
 * user can tell if the agent has anything to retrieve. Per-connector card
 * shows total/indexed/failed/pending counts, last sync time, last error,
 * and a Reindex button that retries non-completed items.
 */

import { useState, useEffect, useCallback } from 'react'
import { connectorsApi, ConnectorIndexStatus } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/toast'

const SOURCES: Array<{ key: string; label: string }> = [
  { key: 'gmail', label: 'Gmail' },
  { key: 'slack', label: 'Slack' },
  { key: 'google_calendar', label: 'Google Calendar' },
]

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return 'never'
  const date = new Date(isoStr)
  const diffMs = Date.now() - date.getTime()
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}

function ConnectorCard({ source, label }: { source: string; label: string }) {
  const [status, setStatus] = useState<ConnectorIndexStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [reindexing, setReindexing] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const s = await connectorsApi.getStatus(source)
      setStatus(s)
    } catch (e) {
      console.error(`[connectors] failed to load status for ${source}`, e)
    } finally {
      setLoading(false)
    }
  }, [source])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{label}</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={handleReindex}
            disabled={reindexing || loading}
          >
            {reindexing ? 'Reindexing…' : 'Reindex'}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-sm text-[#9e9e9e]">Loading…</div>
        ) : !status || status.total_items === 0 ? (
          <div className="text-sm text-[#6b6b6b]">
            Nothing synced yet. Trigger a sync or wait for the next scheduler run.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-4 gap-3">
              <Stat label="Total" value={status.total_items} />
              <Stat label="Indexed" value={status.indexed} color="#2d6a4f" />
              <Stat label="Failed" value={status.failed} color={status.failed > 0 ? '#B04A3A' : undefined} />
              <Stat label="Pending" value={status.pending} />
            </div>
            <div className="text-xs text-[#6b6b6b]">
              Last sync: <span className="font-medium">{formatRelativeTime(status.last_sync_at)}</span>
            </div>
            {status.last_error && (
              <div className="rounded-md bg-[#fdf2f0] border border-[#f5d0c8] p-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-[#B04A3A] mb-1">
                  Last error
                </div>
                <code className="text-[11px] text-[#7a3024] font-mono break-all">
                  {status.last_error}
                </code>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-[#9e9e9e]">{label}</div>
      <div className="text-xl font-semibold" style={color ? { color } : undefined}>
        {value}
      </div>
    </div>
  )
}

export default function ConnectorsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-lg font-semibold text-[#1a1a1a]">Connectors</h2>
        <p className="text-sm mt-0.5 text-[#6b6b6b]">
          Sync→index health for each connected source. If &ldquo;failed&rdquo; is non-zero,
          click Reindex to retry.
        </p>
      </div>

      <div className="space-y-3">
        {SOURCES.map(({ key, label }) => (
          <ConnectorCard key={key} source={key} label={label} />
        ))}
      </div>
    </div>
  )
}
