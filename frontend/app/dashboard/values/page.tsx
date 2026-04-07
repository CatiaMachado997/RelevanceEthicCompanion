'use client'

import { useState, useEffect, useRef } from 'react'
import { api, type UserValue } from '@/lib/api'
import { DndContext, closestCenter, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Plus, GripVertical, Pencil, Trash2, X, Check, ShieldCheck } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { FilterChips } from '@/components/ui/filter-chips'

type ValueType = 'boundary' | 'preference' | 'topic_filter' | 'time_window'

const TYPE_LABELS: Record<ValueType, string> = {
  boundary: 'Boundary',
  preference: 'Preference',
  topic_filter: 'Topic Filter',
  time_window: 'Time Window',
}

const TYPE_DOT_COLORS: Record<string, string> = {
  boundary:     '#1a1a1a',
  preference:   '#4A7C59',
  topic_filter: '#9B7A3D',
  time_window:  '#5B7FA6',
}

const CARD_BASE = {
  background: '#ffffff',
  border: '1px solid rgba(0,0,0,0.08)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
}

function TypeBadge({ type }: { type: string }) {
  const dotColor = TYPE_DOT_COLORS[type] ?? '#9e9e9e'
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border border-[#e0e0e0] text-[#6b6b6b]">
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor }} />
      {TYPE_LABELS[type as ValueType] ?? type}
    </span>
  )
}

interface AnimatedValue extends UserValue {
  mounted?: boolean
  removing?: boolean
}

interface SortableCardProps {
  value: AnimatedValue
  onEdit: (v: UserValue) => void
  onDelete: (id: string) => void
}

function SortableValueCard({ value, onEdit, onDelete }: SortableCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: value.id })

  const dragStyle = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : undefined,
    opacity: isDragging ? 0.85 : 1,
  }

  const animClass = value.removing
    ? 'opacity-0 scale-95'
    : value.mounted
    ? 'opacity-100 scale-100'
    : 'opacity-0 scale-95'

  return (
    <div
      ref={setNodeRef}
      style={{ ...dragStyle }}
      data-value-type={value.type}
    >
      <div
        className={`rounded-2xl p-5 group transition-all duration-200 ease-out hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)] ${animClass}`}
        style={CARD_BASE}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <div
              {...attributes}
              {...listeners}
              className="shrink-0 opacity-0 group-hover:opacity-40 transition-opacity cursor-grab"
            >
              <GripVertical size={14} style={{ color: '#9e9e9e' }} />
            </div>
            <TypeBadge type={value.type} />
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              onClick={() => onEdit(value)}
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors hover:bg-black/5"
              aria-label="Edit value"
            >
              <Pencil size={13} style={{ color: '#6b6b6b' }} />
            </button>
            <button
              onClick={() => onDelete(value.id)}
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors hover:bg-black/5"
              aria-label="Delete value"
            >
              <Trash2 size={13} style={{ color: '#B04A3A' }} />
            </button>
          </div>
        </div>
        <p className="mt-3 text-sm font-medium" style={{ color: '#1a1a1a' }}>{value.value}</p>
        <p className="mt-1 text-xs" style={{ color: '#9e9e9e' }}>
          Priority {value.priority}
        </p>
      </div>
    </div>
  )
}

export default function ValuesPage() {
  const [values, setValues] = useState<AnimatedValue[]>([])
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState<ValueType | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingValue, setEditingValue] = useState<UserValue | null>(null)

  const [formType, setFormType] = useState<ValueType>('boundary')
  const [formValue, setFormValue] = useState('')
  const [formPriority, setFormPriority] = useState(5)
  const [saving, setSaving] = useState(false)

  const removeTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  useEffect(() => {
    api.values.list()
      .then((r: UserValue[] | { values?: UserValue[] }) => {
        const items = Array.isArray(r) ? r : (r as { values?: UserValue[] }).values ?? []
        // Mount animation: set mounted=false first, then true on next tick
        const withMount = items.map((v: UserValue) => ({ ...v, mounted: false }))
        setValues(withMount)
        requestAnimationFrame(() => {
          setValues(prev => prev.map(v => ({ ...v, mounted: true })))
        })
      })
      .catch(console.error)
      .finally(() => setLoading(false))

    return () => {
      removeTimers.current.forEach(t => clearTimeout(t))
    }
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
        const updated = await api.values.update(editingValue.id, {
          value: formValue,
          priority: formPriority,
        })
        setValues(prev => prev.map(v => v.id === editingValue.id ? { ...updated, mounted: true } : v))
      } else {
        const created = await api.values.create({
          type: formType,
          value: formValue,
          priority: formPriority,
        })
        if (created) {
          // Add with mounted=false, then animate in
          setValues(prev => [...prev, { ...created, mounted: false }])
          requestAnimationFrame(() => {
            setValues(prev => prev.map(v => v.id === created.id ? { ...v, mounted: true } : v))
          })
        }
      }
      setSheetOpen(false)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    // Animate out first, then remove
    setValues(prev => prev.map(v => v.id === id ? { ...v, removing: true } : v))
    const timer = setTimeout(async () => {
      try {
        await api.values.delete(id)
        setValues(prev => prev.filter(v => v.id !== id))
      } catch (e) {
        // Revert animation on error
        setValues(prev => prev.map(v => v.id === id ? { ...v, removing: false } : v))
        console.error(e)
      }
      removeTimers.current.delete(id)
    }, 200)
    removeTimers.current.set(id, timer)
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = values.findIndex(v => v.id === active.id)
    const newIndex = values.findIndex(v => v.id === over.id)
    const reordered = arrayMove(values, oldIndex, newIndex)
    setValues(reordered)
    try {
      await api.values.reorder(reordered.map(v => v.id))
      // Re-fetch to confirm server state
      const r = await api.values.list() as UserValue[] | { values?: UserValue[] }
      const refreshed = Array.isArray(r) ? r : (r as { values?: UserValue[] }).values ?? []
      const withMount = refreshed.map((v: UserValue) => ({ ...v, mounted: true }))
      setValues(withMount)
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: '#1a1a1a' }}>Your Values</h2>
          <p className="text-sm mt-0.5" style={{ color: '#6b6b6b' }}>
            Define the boundaries ESL protects for you.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: '#000000', color: '#ffffff' }}
        >
          <Plus size={15} />
          Add Value
        </button>
      </div>

      {/* Filter chips */}
      <FilterChips<ValueType>
        chips={[
          { value: null, label: 'All', count: values.length },
          { value: 'boundary', label: 'Boundary', count: values.filter(v => v.type === 'boundary').length },
          { value: 'preference', label: 'Preference', count: values.filter(v => v.type === 'preference').length },
          { value: 'topic_filter', label: 'Topic Filter', count: values.filter(v => v.type === 'topic_filter').length },
          { value: 'time_window', label: 'Time Window', count: values.filter(v => v.type === 'time_window').length },
        ]}
        selected={typeFilter}
        onChange={setTypeFilter}
      />

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
      ) : (() => {
        const displayedValues = typeFilter ? values.filter(v => v.type === typeFilter) : values
        return displayedValues.length === 0 ? (
          values.length === 0 ? (
            <div className="py-10 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto" style={{ background: 'var(--ec-surface-2)', border: '1px solid var(--ec-card-border)' }}>
                <ShieldCheck size={20} style={{ color: 'var(--ec-text-subtle)' }} />
              </div>
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--ec-text)' }}>No values yet</p>
                <p className="text-xs mt-1" style={{ color: 'var(--ec-text-subtle)' }}>
                  Values tell Ethic Companion what you care about.<br />Your Ethical Safeguard Layer enforces them on every response.
                </p>
              </div>
            </div>
          ) : (
            <div
              className="rounded-2xl p-10 text-center"
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.08)', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
            >
              <p className="text-sm" style={{ color: '#9e9e9e' }}>
                No values match this filter.
              </p>
            </div>
          )
        ) : (
          <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={displayedValues.map(v => v.id)} strategy={verticalListSortingStrategy}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {displayedValues.map(v => (
                  <SortableValueCard
                    key={v.id}
                    value={v}
                    onEdit={openEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )
      })()}

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
                    className="w-full rounded-xl px-3 py-2 text-sm outline-none"
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
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none resize-none"
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
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-black/5 flex gap-2">
              <button
                onClick={() => setSheetOpen(false)}
                className="flex-1 py-2 rounded-full text-sm font-medium"
                style={{ background: 'rgba(0,0,0,0.05)', color: '#6b6b6b' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formValue.trim() || saving}
                className="flex-1 py-2 rounded-full text-sm font-medium flex items-center justify-center gap-1.5 transition-opacity disabled:opacity-50"
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
