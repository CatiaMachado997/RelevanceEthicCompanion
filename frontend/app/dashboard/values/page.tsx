'use client'

import { useState, useEffect } from 'react'
import { valuesApi, type UserValue } from '@/lib/api'
import { Plus, GripVertical, Pencil, Trash2, X, Check } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

type ValueType = 'boundary' | 'preference' | 'topic_filter' | 'time_window'

const TYPE_LABELS: Record<ValueType, string> = {
  boundary: 'Boundary',
  preference: 'Preference',
  topic_filter: 'Topic Filter',
  time_window: 'Time Window',
}

const TYPE_COLORS: Record<ValueType, { bg: string; text: string; border: string }> = {
  boundary:     { bg: 'rgba(0,0,0,0.06)',        text: '#000000', border: 'rgba(0,0,0,0.15)' },
  preference:   { bg: 'rgba(74,124,89,0.10)',   text: '#4A7C59', border: 'rgba(74,124,89,0.25)' },
  topic_filter: { bg: 'rgba(155,122,61,0.10)',  text: '#9B7A3D', border: 'rgba(155,122,61,0.25)' },
  time_window:  { bg: 'rgba(91,127,166,0.10)',  text: '#5B7FA6', border: 'rgba(91,127,166,0.25)' },
}

const CARD_STYLE = {
  background: '#ffffff',
  border: '1px solid rgba(0,0,0,0.08)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
}

function TypeBadge({ type }: { type: ValueType }) {
  const c = TYPE_COLORS[type] ?? TYPE_COLORS.preference
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      {TYPE_LABELS[type] ?? type}
    </span>
  )
}

export default function ValuesPage() {
  const [values, setValues] = useState<UserValue[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingValue, setEditingValue] = useState<UserValue | null>(null)

  const [formType, setFormType] = useState<ValueType>('boundary')
  const [formValue, setFormValue] = useState('')
  const [formPriority, setFormPriority] = useState(5)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    valuesApi.list()
      .then(r => setValues(r.values ?? []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const openCreate = () => {
    setEditingValue(null)
    setFormType('boundary')
    setFormValue('')
    setFormPriority(5)
    setSheetOpen(true)
  }

  const openEdit = (v: UserValue) => {
    setEditingValue(v)
    setFormType(v.type as ValueType)
    setFormValue(v.value)
    setFormPriority(v.priority)
    setSheetOpen(true)
  }

  const handleSave = async () => {
    if (!formValue.trim()) return
    setSaving(true)
    try {
      if (editingValue) {
        const updated = await valuesApi.update(editingValue.id, {
          value: formValue,
          priority: formPriority,
        })
        setValues(prev => prev.map(v => v.id === editingValue.id ? updated : v))
      } else {
        const created = await valuesApi.create({
          type: formType,
          value: formValue,
          priority: formPriority,
        })
        if (created) setValues(prev => [...prev, created])
      }
      setSheetOpen(false)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await valuesApi.delete(id)
      setValues(prev => prev.filter(v => v.id !== id))
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: '#0a0a0a' }}>Your Values</h2>
          <p className="text-sm mt-0.5" style={{ color: '#6b6b6b' }}>
            Define the boundaries ESL protects for you.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: '#000000', color: '#ffffff' }}
        >
          <Plus size={15} />
          Add Value
        </button>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
      ) : values.length === 0 ? (
        <div className="rounded-2xl p-10 text-center" style={CARD_STYLE}>
          <p className="text-sm" style={{ color: '#9e9e9e' }}>
            No values yet. Add your first boundary or preference.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {values.map(v => (
            <div key={v.id} className="rounded-2xl p-5 group" style={CARD_STYLE}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <GripVertical
                    size={14}
                    className="shrink-0 opacity-0 group-hover:opacity-40 transition-opacity cursor-grab"
                    style={{ color: '#9e9e9e' }}
                  />
                  <TypeBadge type={v.type as ValueType} />
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <button
                    onClick={() => openEdit(v)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
                    aria-label="Edit value"
                  >
                    <Pencil size={13} style={{ color: '#6b6b6b' }} />
                  </button>
                  <button
                    onClick={() => handleDelete(v.id)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
                    aria-label="Delete value"
                  >
                    <Trash2 size={13} style={{ color: '#B04A3A' }} />
                  </button>
                </div>
              </div>
              <p className="mt-3 text-sm font-medium" style={{ color: '#0a0a0a' }}>{v.value}</p>
              <p className="mt-1 text-xs" style={{ color: '#9e9e9e' }}>Priority {v.priority}</p>
            </div>
          ))}
        </div>
      )}

      {/* Slide-over sheet */}
      {sheetOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="flex-1 bg-black/20 backdrop-blur-sm"
            onClick={() => setSheetOpen(false)}
          />
          <div className="w-[400px] flex flex-col h-full shadow-2xl" style={{ background: '#f9f9f9' }}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-black/5">
              <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>
                {editingValue ? 'Edit Value' : 'Add Value'}
              </h3>
              <button onClick={() => setSheetOpen(false)} aria-label="Close sheet">
                <X size={18} style={{ color: '#6b6b6b' }} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {!editingValue && (
                <div>
                  <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>
                    Type
                  </label>
                  <select
                    value={formType}
                    onChange={e => setFormType(e.target.value as ValueType)}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                    style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                  >
                    {(Object.keys(TYPE_LABELS) as ValueType[]).map(t => (
                      <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>
                  Value
                </label>
                <textarea
                  value={formValue}
                  onChange={e => setFormValue(e.target.value)}
                  placeholder="e.g. no_work_after_19h"
                  rows={3}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none resize-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>
                  Priority (1 = highest)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={formPriority}
                  onChange={e => setFormPriority(Number(e.target.value))}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-black/5 flex gap-2">
              <button
                onClick={() => setSheetOpen(false)}
                className="flex-1 py-2 rounded-lg text-sm font-medium"
                style={{ background: 'rgba(0,0,0,0.05)', color: '#6b6b6b' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formValue.trim() || saving}
                className="flex-1 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 transition-opacity disabled:opacity-50"
                style={{ background: '#000000', color: '#ffffff' }}
              >
                <Check size={14} />
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
