'use client'

import { useState, useEffect } from 'react'
import { goalsApi, valuesApi, transparencyApi } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/hooks/useAuth'
import { Shield, User, BarChart3 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/ui/page-header'

const CARD_STYLE = {
  background: 'var(--ec-card-bg)',
  border: '1px solid var(--ec-card-border)',
  borderRadius: '16px',
  boxShadow: 'var(--ec-card-shadow)',
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function ProfilePage() {
  const { user } = useAuth()

  const [displayName, setDisplayName] = useState('')
  const [timezone, setTimezone] = useState('')
  const [originalName, setOriginalName] = useState('')
  const [originalTimezone, setOriginalTimezone] = useState('')

  const [valuesCount, setValuesCount] = useState<number | null>(null)
  const [goalsCount, setGoalsCount] = useState<number | null>(null)
  const [approvalRate, setApprovalRate] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const initials = user?.email
    ? user.email.split('@')[0].substring(0, 2).toUpperCase()
    : 'U'

  useEffect(() => {
    const load = async () => {
      try {
        const [values, goals, report] = await Promise.allSettled([
          valuesApi.list(),
          goalsApi.list('active'),
          transparencyApi.report(),
        ])
        if (values.status === 'fulfilled') setValuesCount(values.value.values.length)
        if (goals.status === 'fulfilled') setGoalsCount(goals.value.goals.length)
        if (report.status === 'fulfilled') {
          const rate = report.value?.approval_rate ?? 0
          setApprovalRate(rate > 1 ? Math.round(rate) : Math.round(rate * 100))
        }

        // Load profile display_name and timezone from profile API
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token
        if (token) {
          const res = await fetch(`${API_URL}/api/profile/`, {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (res.ok) {
            const json = await res.json()
            const profile = json.data ?? {}
            const name = profile.display_name ?? ''
            const tz = profile.timezone ?? ''
            setDisplayName(name)
            setOriginalName(name)
            setTimezone(tz)
            setOriginalTimezone(tz)
          }
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const isDirty = displayName !== originalName || timezone !== originalTimezone

  const handleSave = async () => {
    if (!isDirty) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const { data: { session } } = await import('@/lib/supabase').then(m => m.supabase.auth.getSession())
      const token = session?.access_token
      const body: Record<string, string> = {}
      if (displayName !== originalName) body.display_name = displayName
      if (timezone !== originalTimezone) body.timezone = timezone

      const res = await fetch(`${API_URL}/api/profile/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? 'Failed to save')
      }
      const json = await res.json()
      const updated = json.data ?? {}
      setOriginalName(updated.display_name ?? displayName)
      setOriginalTimezone(updated.timezone ?? timezone)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setDisplayName(originalName)
    setTimezone(originalTimezone)
    setSaveError(null)
  }

  const stats = [
    { label: 'Values Set', value: valuesCount },
    { label: 'Active Goals', value: goalsCount },
    { label: 'ESL Approval', value: approvalRate !== null ? `${approvalRate}%` : null },
  ]

  return (
    <div className="max-w-4xl space-y-5">
      <PageHeader title="Profile" subtitle="Your personal information" />

      {/* Identity card */}
      <div className="rounded-2xl p-6 flex items-center gap-5" style={CARD_STYLE}>
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold shrink-0"
          style={{ background: '#1a1a1a', color: '#ffffff' }}
        >
          {initials}
        </div>
        <div className="min-w-0">
          <p className="text-base font-semibold truncate" style={{ color: 'var(--ec-text)' }}>
            {displayName || user?.email?.split('@')[0] || 'User'}
          </p>
          <p className="text-sm truncate" style={{ color: 'var(--ec-text-subtle)' }}>{user?.email}</p>
          <div
            className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-xs font-medium"
            style={{ background: 'rgba(74,124,89,0.10)', color: '#4A7C59', border: '1px solid rgba(74,124,89,0.20)' }}
          >
            <Shield size={11} />
            Protected by ESL
          </div>
        </div>
      </div>

      {/* Personal info */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <User size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>Personal Information</h3>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ec-text-muted)' }}>Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Your name"
              className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
              style={{
                background: 'var(--ec-surface)',
                border: '1px solid rgba(0,0,0,0.10)',
                color: 'var(--ec-text)',
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ec-text-muted)' }}>Email</label>
            <input
              type="email"
              value={user?.email ?? ''}
              disabled
              className="w-full px-3 py-2 rounded-xl text-sm"
              style={{
                background: 'var(--ec-page-bg)',
                border: '1px solid rgba(0,0,0,0.06)',
                color: 'var(--ec-text-subtle)',
                cursor: 'not-allowed',
              }}
            />
            <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>Email cannot be changed here</p>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--ec-text-muted)' }}>Timezone</label>
            <select
              value={timezone}
              onChange={e => setTimezone(e.target.value)}
              className="w-full px-3 py-2 rounded-xl text-sm outline-none transition-all"
              style={{
                background: 'var(--ec-surface)',
                border: '1px solid rgba(0,0,0,0.10)',
                color: timezone ? '#0a0a0a' : '#9e9e9e',
              }}
            >
              <option value="">Select timezone…</option>
              <optgroup label="Africa">
                <option value="Africa/Cairo">Africa/Cairo</option>
                <option value="Africa/Johannesburg">Africa/Johannesburg</option>
                <option value="Africa/Lagos">Africa/Lagos</option>
              </optgroup>
              <optgroup label="America">
                <option value="America/Anchorage">America/Anchorage</option>
                <option value="America/Bogota">America/Bogota</option>
                <option value="America/Chicago">America/Chicago</option>
                <option value="America/Denver">America/Denver</option>
                <option value="America/Los_Angeles">America/Los_Angeles</option>
                <option value="America/Mexico_City">America/Mexico_City</option>
                <option value="America/New_York">America/New_York</option>
                <option value="America/Phoenix">America/Phoenix</option>
                <option value="America/Sao_Paulo">America/Sao_Paulo</option>
                <option value="America/Toronto">America/Toronto</option>
                <option value="America/Vancouver">America/Vancouver</option>
              </optgroup>
              <optgroup label="Asia">
                <option value="Asia/Bangkok">Asia/Bangkok</option>
                <option value="Asia/Dubai">Asia/Dubai</option>
                <option value="Asia/Hong_Kong">Asia/Hong_Kong</option>
                <option value="Asia/Jakarta">Asia/Jakarta</option>
                <option value="Asia/Kolkata">Asia/Kolkata</option>
                <option value="Asia/Seoul">Asia/Seoul</option>
                <option value="Asia/Shanghai">Asia/Shanghai</option>
                <option value="Asia/Singapore">Asia/Singapore</option>
                <option value="Asia/Tokyo">Asia/Tokyo</option>
              </optgroup>
              <optgroup label="Australia">
                <option value="Australia/Melbourne">Australia/Melbourne</option>
                <option value="Australia/Perth">Australia/Perth</option>
                <option value="Australia/Sydney">Australia/Sydney</option>
              </optgroup>
              <optgroup label="Europe">
                <option value="Europe/Amsterdam">Europe/Amsterdam</option>
                <option value="Europe/Berlin">Europe/Berlin</option>
                <option value="Europe/Istanbul">Europe/Istanbul</option>
                <option value="Europe/Lisbon">Europe/Lisbon</option>
                <option value="Europe/London">Europe/London</option>
                <option value="Europe/Madrid">Europe/Madrid</option>
                <option value="Europe/Moscow">Europe/Moscow</option>
                <option value="Europe/Paris">Europe/Paris</option>
                <option value="Europe/Rome">Europe/Rome</option>
                <option value="Europe/Zurich">Europe/Zurich</option>
              </optgroup>
              <optgroup label="Pacific">
                <option value="Pacific/Auckland">Pacific/Auckland</option>
                <option value="Pacific/Honolulu">Pacific/Honolulu</option>
              </optgroup>
              <optgroup label="UTC">
                <option value="UTC">UTC</option>
              </optgroup>
            </select>
          </div>
        </div>

        {saveError && (
          <p className="mt-3 text-xs" style={{ color: '#B04A3A' }}>{saveError}</p>
        )}
        {saveSuccess && (
          <p className="mt-3 text-xs" style={{ color: '#4A7C59' }}>Saved successfully</p>
        )}

        {isDirty && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-opacity disabled:opacity-50"
              style={{ background: '#000000', color: '#ffffff' }}
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
            <button
              onClick={handleCancel}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-colors hover:bg-[#f0f0f0]"
              style={{ background: 'var(--ec-page-bg)', color: 'var(--ec-text-muted)' }}
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Account stats */}
      <div className="rounded-2xl p-5" style={CARD_STYLE}>
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 size={15} style={{ color: '#000000' }} />
          <h3 className="text-sm font-semibold" style={{ color: 'var(--ec-text)' }}>Account Statistics</h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {stats.map(({ label, value }) => (
            <div
              key={label}
              className="text-center py-4 rounded-xl"
              style={{ background: 'var(--ec-surface)' }}
            >
              {loading ? (
                <Skeleton className="h-7 w-12 mx-auto mb-1" />
              ) : (
                <p className="text-2xl font-bold" style={{ color: 'var(--ec-text)' }}>
                  {value ?? '—'}
                </p>
              )}
              <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>{label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
