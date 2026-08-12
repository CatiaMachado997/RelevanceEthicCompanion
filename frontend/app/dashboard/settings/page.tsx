'use client'

import { useState, useEffect } from 'react'
import { Bell, Lock, Calendar, CheckCircle2, XCircle, RefreshCw, SlidersHorizontal, Globe, LogOut, Brain, Pencil, Trash2 } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { dataSourcesApi, DataSource, settingsApi, UserSettings, memoriesApi, ControlledMemory } from '@/lib/api'
import { PageHeader } from '@/components/ui/page-header'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

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
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        aria-label={label}
      />
    </div>
  )
}

const TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Sao_Paulo', 'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Singapore', 'Asia/Tokyo', 'Australia/Sydney',
]

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'pt', label: 'Português' },
  { value: 'ja', label: '日本語' },
  { value: 'zh', label: '中文' },
]

export default function SettingsPage() {
  const router = useRouter()
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [memories, setMemories] = useState<ControlledMemory[]>([])
  const [newMemory, setNewMemory] = useState('')
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null)
  const [editingMemoryContent, setEditingMemoryContent] = useState('')
  const [syncing, setSyncing] = useState<string | null>(null)

  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Appearance — localStorage only (useEffect for SSR safety)
  const [appearance, setAppearance] = useState<Record<string, unknown>>({})

  useEffect(() => {
    try {
      const saved = localStorage.getItem('ec_appearance')
      if (saved) setAppearance(JSON.parse(saved))
    } catch {}
  }, [])

  const saveAppearance = (update: Record<string, unknown>) => {
    const next = { ...appearance, ...update }
    setAppearance(next)
    localStorage.setItem('ec_appearance', JSON.stringify(next))
  }

  const [signingOut, setSigningOut] = useState(false)

  useEffect(() => {
    dataSourcesApi.list().then(({ sources }) => setDataSources(sources)).catch(console.error)
    settingsApi.get().then(setSettings).catch(console.error)
    memoriesApi.list().then(({ memories: rows }) => setMemories(rows)).catch(console.error)
  }, [])

  const addMemory = async () => {
    const content = newMemory.trim()
    if (!content) return
    const created = await memoriesApi.create(content)
    setMemories(prev => [created, ...prev])
    setNewMemory('')
  }

  const toggleMemory = async (memory: ControlledMemory) => {
    const updated = await memoriesApi.update(memory.id, { active: !memory.active })
    setMemories(prev => prev.map(item => item.id === updated.id ? updated : item))
  }

  const startEditingMemory = (memory: ControlledMemory) => {
    setEditingMemoryId(memory.id)
    setEditingMemoryContent(memory.content)
  }

  const cancelEditingMemory = () => {
    setEditingMemoryId(null)
    setEditingMemoryContent('')
  }

  const saveMemoryCorrection = async (memory: ControlledMemory) => {
    const content = editingMemoryContent.trim()
    if (!content) return
    if (content === memory.content) {
      cancelEditingMemory()
      return
    }
    const updated = await memoriesApi.update(memory.id, { content })
    setMemories(prev => prev.map(item => item.id === updated.id ? updated : item))
    cancelEditingMemory()
  }

  const forgetMemory = async (id: string) => {
    await memoriesApi.forget(id)
    setMemories(prev => prev.filter(item => item.id !== id))
  }

  const handleToggle = (key: keyof UserSettings) => (checked: boolean) => {
    setSettings(prev => ({ ...prev, [key]: checked }))
    setDirty(true)
    setSaveSuccess(false)
    setSaveError(null)
  }

  const handleWeightChange = (key: keyof UserSettings, value: number) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setDirty(true)
    setSaveSuccess(false)
    setSaveError(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const {
        email_notifications, push_notifications, esl_alerts, share_analytics, pii_protection,
        weight_goal_alignment, weight_time_sensitivity, weight_personal_values, weight_context_relevance,
        timezone, language,
      } = settings
      await settingsApi.update({
        email_notifications, push_notifications, esl_alerts, share_analytics, pii_protection,
        weight_goal_alignment: weight_goal_alignment ?? 1.0,
        weight_time_sensitivity: weight_time_sensitivity ?? 1.0,
        weight_personal_values: weight_personal_values ?? 1.0,
        weight_context_relevance: weight_context_relevance ?? 1.0,
        timezone,
        language,
      })
      setDirty(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleSignOutAll = async () => {
    setSigningOut(true)
    try {
      await supabase.auth.signOut({ scope: 'global' })
      router.push('/login')
    } catch (e) {
      console.error('Sign out failed', e)
    } finally {
      setSigningOut(false)
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

      {/* Appearance */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <SlidersHorizontal size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Appearance</h3>
        </div>
        <div className="space-y-3">
          <ToggleRow
            label="Compact Mode"
            description="Reduce spacing and padding throughout the app"
            checked={!!appearance.compact}
            onCheckedChange={v => saveAppearance({ compact: v })}
          />
          <ToggleRow
            label="Reduce Motion"
            description="Minimise animations for accessibility"
            checked={!!appearance.reduceMotion}
            onCheckedChange={v => saveAppearance({ reduceMotion: v })}
          />
        </div>
      </div>

      {/* User-controlled long-term memory */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-1">
          <Brain size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Chat memory</h3>
        </div>
        <p className="mb-4 text-xs" style={{ color: '#9e9e9e' }}>Only active memories below are added to future chats. You can pause, correct, or forget them at any time.</p>
        <div className="flex gap-2">
          <input value={newMemory} onChange={e => setNewMemory(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') void addMemory() }} maxLength={2000} placeholder="Something you want the companion to remember" className="min-w-0 flex-1 rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none" />
          <button onClick={() => void addMemory()} disabled={!newMemory.trim()} className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-40">Remember</button>
        </div>
        <div className="mt-3 space-y-2">
          {memories.map(memory => (
            <div key={memory.id} className="flex items-start gap-3 rounded-lg border border-neutral-100 p-3">
              <button onClick={() => void toggleMemory(memory)} className="mt-0.5 text-xs font-medium" style={{ color: memory.active ? '#4A7C59' : '#9e9e9e' }}>{memory.active ? 'Active' : 'Paused'}</button>
              {editingMemoryId === memory.id ? (
                <div className="min-w-0 flex-1">
                  <input
                    autoFocus
                    aria-label="Correct memory"
                    value={editingMemoryContent}
                    onChange={event => setEditingMemoryContent(event.target.value)}
                    onKeyDown={event => {
                      if (event.key === 'Enter') void saveMemoryCorrection(memory)
                      if (event.key === 'Escape') cancelEditingMemory()
                    }}
                    maxLength={2000}
                    className="w-full rounded-lg border border-neutral-200 px-2 py-1 text-sm outline-none"
                  />
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => void saveMemoryCorrection(memory)} disabled={!editingMemoryContent.trim()} className="text-xs font-medium text-neutral-900 disabled:opacity-40">Save correction</button>
                    <button onClick={cancelEditingMemory} className="text-xs text-neutral-500">Cancel</button>
                  </div>
                </div>
              ) : (
                <p className="min-w-0 flex-1 text-sm text-neutral-700">{memory.content}</p>
              )}
              <button onClick={() => startEditingMemory(memory)} aria-label="Correct memory" title="Correct memory" className="text-neutral-400 hover:text-neutral-900"><Pencil size={14} /></button>
              <button onClick={() => void forgetMemory(memory.id)} aria-label="Forget memory" title="Forget memory" className="text-neutral-400 hover:text-red-700"><Trash2 size={14} /></button>
            </div>
          ))}
          {memories.length === 0 && <p className="py-2 text-xs text-neutral-400">No saved memories.</p>}
        </div>
      </div>

      {/* Profile — timezone & language */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <Globe size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Region & Language</h3>
        </div>
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-sm font-medium" style={{ color: '#0a0a0a' }}>Timezone</Label>
              <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>Used for scheduling and time-based ESL rules</p>
            </div>
            <select
              value={settings.timezone ?? ''}
              onChange={e => {
                setSettings(prev => ({ ...prev, timezone: e.target.value || undefined }))
                setDirty(true)
                setSaveSuccess(false)
                setSaveError(null)
              }}
              className="text-sm rounded-lg px-2 py-1.5 border outline-none"
              style={{ border: '1px solid rgba(0,0,0,0.12)', color: '#0a0a0a', background: '#fafafa' }}
            >
              <option value="">— select —</option>
              {TIMEZONES.map(tz => (
                <option key={tz} value={tz}>{tz}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label className="text-sm font-medium" style={{ color: '#0a0a0a' }}>Language</Label>
              <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>Preferred language for responses</p>
            </div>
            <select
              value={settings.language ?? ''}
              onChange={e => {
                setSettings(prev => ({ ...prev, language: e.target.value || undefined }))
                setDirty(true)
                setSaveSuccess(false)
                setSaveError(null)
              }}
              className="text-sm rounded-lg px-2 py-1.5 border outline-none"
              style={{ border: '1px solid rgba(0,0,0,0.12)', color: '#0a0a0a', background: '#fafafa' }}
            >
              <option value="">— select —</option>
              {LANGUAGES.map(lang => (
                <option key={lang.value} value={lang.value}>{lang.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

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
                    style={{ color: (calendarSource.status === 'synced' || calendarSource.status === 'sync_needed') ? '#4A7C59' : '#B04A3A' }}
                  >
                    {(calendarSource.status === 'synced' || calendarSource.status === 'sync_needed')
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
            {(calendarSource?.status === 'synced' || calendarSource?.status === 'sync_needed') ? (
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
          <div className="pt-2 border-t" style={{ borderColor: 'rgba(0,0,0,0.08)' }}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium" style={{ color: '#0a0a0a' }}>Sign out of all devices</p>
                <p className="text-xs mt-0.5" style={{ color: '#9e9e9e' }}>Revoke all active sessions immediately</p>
              </div>
              <button
                onClick={handleSignOutAll}
                disabled={signingOut}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity disabled:opacity-50 hover:opacity-80"
                style={{ border: '1px solid rgba(176,74,58,0.35)', color: '#B04A3A', background: 'rgba(176,74,58,0.06)' }}
              >
                <LogOut size={12} />
                {signingOut ? 'Signing out…' : 'Sign out all'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Relevance Tuning */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <SlidersHorizontal size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>Relevance Tuning</h3>
        </div>
        <p className="text-xs mb-4" style={{ color: '#9e9e9e' }}>
          Adjust how much each signal influences what ESL surfaces for you.
        </p>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm w-36 shrink-0" style={{ color: '#0a0a0a' }}>Goal Alignment</span>
            <input
              type="range" min={0} max={2} step={0.1}
              value={settings.weight_goal_alignment ?? 1.0}
              onChange={e => handleWeightChange('weight_goal_alignment', parseFloat(e.target.value))}
              className="flex-1 accent-black"
            />
            <span className="text-xs w-8 text-right" style={{ color: '#6b6b6b' }}>
              {(settings.weight_goal_alignment ?? 1.0).toFixed(1)}x
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm w-36 shrink-0" style={{ color: '#0a0a0a' }}>Time Sensitivity</span>
            <input
              type="range" min={0} max={2} step={0.1}
              value={settings.weight_time_sensitivity ?? 1.0}
              onChange={e => handleWeightChange('weight_time_sensitivity', parseFloat(e.target.value))}
              className="flex-1 accent-black"
            />
            <span className="text-xs w-8 text-right" style={{ color: '#6b6b6b' }}>
              {(settings.weight_time_sensitivity ?? 1.0).toFixed(1)}x
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm w-36 shrink-0" style={{ color: '#0a0a0a' }}>Personal Values</span>
            <input
              type="range" min={0} max={2} step={0.1}
              value={settings.weight_personal_values ?? 1.0}
              onChange={e => handleWeightChange('weight_personal_values', parseFloat(e.target.value))}
              className="flex-1 accent-black"
            />
            <span className="text-xs w-8 text-right" style={{ color: '#6b6b6b' }}>
              {(settings.weight_personal_values ?? 1.0).toFixed(1)}x
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm w-36 shrink-0" style={{ color: '#0a0a0a' }}>Context Relevance</span>
            <input
              type="range" min={0} max={2} step={0.1}
              value={settings.weight_context_relevance ?? 1.0}
              onChange={e => handleWeightChange('weight_context_relevance', parseFloat(e.target.value))}
              className="flex-1 accent-black"
            />
            <span className="text-xs w-8 text-right" style={{ color: '#6b6b6b' }}>
              {(settings.weight_context_relevance ?? 1.0).toFixed(1)}x
            </span>
          </div>
        </div>

        {/* Relevance Tuning save */}
        <div className="flex items-center gap-3 mt-5 pt-4 border-t" style={{ borderColor: '#eeeeee' }}>
          <button
            onClick={handleSave}
            disabled={saving || !dirty}
            className="px-4 py-2 rounded-xl text-sm font-medium transition-opacity disabled:opacity-40"
            style={{ background: '#4a7c59', color: '#ffffff' }}
          >
            {saving ? 'Saving…' : 'Save tuning'}
          </button>
          {saveSuccess && (
            <span className="text-xs" style={{ color: '#4A7C59' }}>Saved</span>
          )}
          {saveError && (
            <span className="text-xs" style={{ color: '#B04A3A' }}>{saveError}</span>
          )}
          {!dirty && !saveSuccess && !saveError && (
            <span className="text-xs" style={{ color: '#9e9e9e' }}>No changes</span>
          )}
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
