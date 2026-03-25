'use client'

import { useState, useEffect } from 'react'
import { Bell, Lock, Calendar, CheckCircle2, XCircle, RefreshCw } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { dataSourcesApi, DataSource, settingsApi, UserSettings } from '@/lib/api'
import { PageHeader } from '@/components/ui/page-header'

const CARD_STYLE = {
  background: 'var(--ec-card-bg)',
  border: '1px solid var(--ec-card-border)',
  borderRadius: '16px',
  boxShadow: 'var(--ec-card-shadow)',
}

const DEFAULT_SETTINGS: UserSettings = {
  email_notifications: false,
  push_notifications: false,
  esl_alerts: true,
  share_analytics: false,
  pii_protection: true,
}

function ToggleRow({
  label,
  description,
  checked,
  onCheckedChange,
}: {
  label: string
  description: string
  checked: boolean
  onCheckedChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <Label className="text-sm font-medium" style={{ color: '#0a0a0a' }}>{label}</Label>
        <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  )
}

export default function SettingsPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [syncing, setSyncing] = useState<string | null>(null)

  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    dataSourcesApi.list().then(({ sources }) => setDataSources(sources)).catch(console.error)
    settingsApi.get().then(setSettings).catch(console.error)
  }, [])

  const handleToggle = (key: keyof UserSettings) => (checked: boolean) => {
    setSettings(prev => ({ ...prev, [key]: checked }))
    setDirty(true)
    setSaveSuccess(false)
    setSaveError(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const { email_notifications, push_notifications, esl_alerts, share_analytics, pii_protection } = settings
      await settingsApi.update({ email_notifications, push_notifications, esl_alerts, share_analytics, pii_protection })
      setDirty(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleConnect = async (sourceType: string) => {
    try {
      const { authorization_url } = await dataSourcesApi.getAuthUrl(sourceType)
      window.location.href = authorization_url
    } catch (e) {
      console.error(e)
    }
  }

  const handleDisconnect = async (sourceType: string) => {
    try {
      await dataSourcesApi.disconnect(sourceType)
      const { sources } = await dataSourcesApi.list()
      setDataSources(sources)
    } catch (e) {
      console.error(e)
    }
  }

  const handleSync = async (sourceType: string) => {
    setSyncing(sourceType)
    try {
      await dataSourcesApi.sync(sourceType)
      const { sources } = await dataSourcesApi.list()
      setDataSources(sources)
    } catch (e) {
      console.error(e)
    } finally {
      setSyncing(null)
    }
  }

  const calendarSource = dataSources.find(s => s.source_type === 'google_calendar')

  return (
    <div className="max-w-4xl space-y-4 md:space-y-6">
      <PageHeader title="Settings" subtitle="Preferences and privacy" />

      {/* Connected Data Sources */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <Calendar size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Connected Data Sources</h3>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: '#f5f5f5' }}>
              <Calendar size={16} style={{ color: '#000000' }} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium" style={{ color: '#0a0a0a' }}>Google Calendar</p>
                {calendarSource && (
                  <span
                    className="inline-flex items-center gap-1 text-[10px] font-medium"
                    style={{ color: calendarSource.status === 'connected' ? '#4A7C59' : '#B04A3A' }}
                  >
                    {calendarSource.status === 'connected'
                      ? <><CheckCircle2 size={10} />Connected</>
                      : <><XCircle size={10} />Disconnected</>
                    }
                  </span>
                )}
              </div>
              <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>
                {calendarSource?.last_sync
                  ? `Last synced ${new Date(calendarSource.last_sync).toLocaleString()}`
                  : 'Sync events for better context'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {calendarSource?.status === 'connected' ? (
              <>
                <button
                  onClick={() => handleSync(calendarSource.source_type)}
                  disabled={syncing === calendarSource.source_type}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 hover:bg-[#f0f0f0]"
                  style={{ border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                >
                  <RefreshCw size={12} className={syncing === calendarSource.source_type ? 'animate-spin' : ''} />
                  Sync
                </button>
                <button
                  onClick={() => handleDisconnect(calendarSource.source_type)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#f0f0f0]"
                  style={{ border: '1px solid rgba(0,0,0,0.10)', color: '#6b6b6b' }}
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                onClick={() => handleConnect('google_calendar')}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
                style={{ background: '#000000', color: '#ffffff' }}
              >
                Connect
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <Bell size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Notifications</h3>
        </div>
        <div className="space-y-4">
          <ToggleRow
            label="Email Notifications"
            description="Receive updates via email"
            checked={settings.email_notifications}
            onCheckedChange={handleToggle('email_notifications')}
          />
          <ToggleRow
            label="Push Notifications"
            description="Receive browser notifications"
            checked={settings.push_notifications}
            onCheckedChange={handleToggle('push_notifications')}
          />
          <ToggleRow
            label="ESL Alerts"
            description="Get notified when ESL blocks an action"
            checked={settings.esl_alerts}
            onCheckedChange={handleToggle('esl_alerts')}
          />
        </div>
      </div>

      {/* Privacy & Security */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <Lock size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Privacy & Security</h3>
        </div>
        <div className="space-y-4">
          <ToggleRow
            label="Share Usage Analytics"
            description="Help improve the app with anonymous usage data"
            checked={settings.share_analytics}
            onCheckedChange={handleToggle('share_analytics')}
          />
          <ToggleRow
            label="PII Protection"
            description="Auto-redact sensitive personal information from AI context"
            checked={settings.pii_protection}
            onCheckedChange={handleToggle('pii_protection')}
          />
        </div>
      </div>

      {/* Save bar */}
      {dirty && (
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-opacity disabled:opacity-50"
            style={{ background: '#000000', color: '#ffffff' }}
          >
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
          {saveError && <p className="text-xs" style={{ color: '#B04A3A' }}>{saveError}</p>}
        </div>
      )}
      {saveSuccess && (
        <p className="text-xs" style={{ color: '#4A7C59' }}>Settings saved</p>
      )}

    </div>
  )
}
