'use client'

import { useState } from 'react'
import {
  Mail,
  MessageSquare,
  Calendar,
  RefreshCw,
  Trash2,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { connectorsApi, dataSourcesApi } from '@/lib/api'
import { toast } from '@/lib/toast'

const ICONS: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  gmail: Mail,
  slack: MessageSquare,
  google_calendar: Calendar,
}

const LABELS: Record<string, string> = {
  gmail: 'Gmail',
  slack: 'Slack',
  google_calendar: 'Google Calendar',
}

function formatRelative(iso: string | null): string {
  if (!iso) return 'never'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 'never'
  const diffMs = Date.now() - t
  const min = Math.round(diffMs / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr}h ago`
  const d = Math.round(hr / 24)
  return `${d}d ago`
}

interface IntegrationCardProps {
  source_type: string
  connected: boolean
  last_sync_at: string | null
  items_count: number
  error?: string | null
  onChange?: () => void
}

export function IntegrationCard({
  source_type,
  connected,
  last_sync_at,
  items_count,
  error,
  onChange,
}: IntegrationCardProps) {
  const [busy, setBusy] = useState<null | 'connect' | 'backfill' | 'disconnect'>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const Icon = ICONS[source_type] ?? Mail
  const label = LABELS[source_type] ?? source_type

  const handleConnect = async () => {
    setBusy('connect')
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(source_type)
      window.location.href = authorization_url
    } catch (e) {
      toast.error('Connect failed', e instanceof Error ? e.message : undefined)
      setBusy(null)
    }
  }

  const handleBackfill = async () => {
    setBusy('backfill')
    try {
      const r = await connectorsApi.backfill(source_type)
      if (r.status === 'failed') {
        toast.error('Backfill failed')
      } else {
        toast.success('Backfill complete', `job ${r.job_id.slice(0, 8)}`)
      }
      onChange?.()
    } catch (e) {
      toast.error('Backfill failed', e instanceof Error ? e.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  const handleDisconnect = async () => {
    setConfirmOpen(false)
    setBusy('disconnect')
    try {
      const r = await connectorsApi.disconnect(source_type)
      toast.success('Disconnected', `${r.items_deleted} items removed`)
      onChange?.()
    } catch (e) {
      toast.error('Disconnect failed', e instanceof Error ? e.message : undefined)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: 'var(--ec-card-bg)',
        border: '1px solid var(--ec-card-border)',
        borderRadius: '16px',
        boxShadow: 'var(--ec-card-shadow)',
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: '#f5f5f5' }}
        >
          <Icon size={16} className="text-black" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-medium" style={{ color: '#0a0a0a' }}>
              {label}
            </p>
            {connected ? (
              <Badge
                variant="outline"
                className="gap-1 text-[10px]"
                style={{ color: '#4A7C59', borderColor: 'rgba(74,124,89,0.35)' }}
              >
                <CheckCircle2 size={10} />
                Connected
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="gap-1 text-[10px]"
                style={{ color: '#9e9e9e', borderColor: 'rgba(0,0,0,0.12)' }}
              >
                <XCircle size={10} />
                Not connected
              </Badge>
            )}
          </div>
          <p className="text-xs mt-1" style={{ color: '#9e9e9e' }}>
            {connected
              ? `${items_count} items synced · last sync ${formatRelative(last_sync_at)}`
              : 'Connect to let chat cite content from this source'}
          </p>
          {error && (
            <p className="text-xs mt-1" style={{ color: '#B04A3A' }}>
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {connected ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBackfill}
                disabled={busy !== null}
                className="gap-1.5"
              >
                <RefreshCw
                  size={12}
                  className={busy === 'backfill' ? 'animate-spin' : ''}
                />
                {busy === 'backfill' ? 'Working…' : 'Backfill now'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmOpen(true)}
                disabled={busy !== null}
                className="gap-1.5"
                style={{ color: '#B04A3A' }}
              >
                <Trash2 size={12} />
                Disconnect
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={handleConnect}
              disabled={busy !== null}
              style={{ background: '#000000', color: '#ffffff' }}
            >
              {busy === 'connect' ? 'Redirecting…' : 'Connect'}
            </Button>
          )}
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect {label}?</DialogTitle>
            <DialogDescription>
              This removes the OAuth token and deletes all indexed content for this
              source. You can reconnect later, but the history will be re-fetched
              from scratch.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleDisconnect}
              style={{ background: '#B04A3A', color: '#ffffff' }}
            >
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
