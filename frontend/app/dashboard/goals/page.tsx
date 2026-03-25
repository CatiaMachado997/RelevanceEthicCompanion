'use client'

import { useState, useEffect } from 'react'
import { goalsApi, api, type Goal, type Milestone } from '@/lib/api'
import { Plus, MoreHorizontal, Check, X, ChevronDown, ChevronRight } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Card } from '@/components/ui/card'
import { FilterChips } from '@/components/ui/filter-chips'

type GoalStatus = 'active' | 'completed' | 'paused' | 'archived'

const STATUS_COLORS: Record<GoalStatus, { bg: string; text: string; border: string }> = {
  active:    { bg: 'rgba(74,124,89,0.10)',   text: '#4A7C59', border: 'rgba(74,124,89,0.25)' },
  completed: { bg: 'rgba(10,10,10,0.08)',    text: '#0a0a0a', border: 'rgba(10,10,10,0.15)' },
  paused:    { bg: 'rgba(155,122,61,0.10)',  text: '#9B7A3D', border: 'rgba(155,122,61,0.25)' },
  archived:  { bg: 'rgba(158,158,158,0.10)', text: '#9e9e9e', border: 'rgba(158,158,158,0.25)' },
}

const PRIORITY_COLORS = ['#000000', '#9B7A3D', '#5B7FA6', '#4A7C59', '#9e9e9e']

function StatusBadge({ status }: { status: GoalStatus }) {
  const c = STATUS_COLORS[status] ?? STATUS_COLORS.active
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      {status}
    </span>
  )
}

type StatusFilter = 'active' | 'paused' | 'completed' | 'archived'

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)
  const [showCompleted, setShowCompleted] = useState(false)
  const [statusFilter, setStatusFilter] = useState<StatusFilter | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null)
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  const [formTitle, setFormTitle] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formPriority, setFormPriority] = useState(5)
  const [formProgress, setFormProgress] = useState(0)
  const [formDate, setFormDate] = useState('')
  const [saving, setSaving] = useState(false)

  const [milestones, setMilestones] = useState<Record<string, Milestone[]>>({})
  const [milestoneInput, setMilestoneInput] = useState<Record<string, string>>({})

  const loadMilestones = async (goalId: string) => {
    try {
      const { milestones: data } = await api.goals.milestones.list(goalId)
      setMilestones(prev => ({ ...prev, [goalId]: data }))
    } catch {}
  }

  useEffect(() => {
    goalsApi.list()
      .then(r => {
        const fetchedGoals = r.goals ?? []
        setGoals(fetchedGoals)
        fetchedGoals
          .filter(g => g.status === 'active' || g.status === 'paused')
          .forEach(g => loadMilestones(g.id))
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const activeGoals = goals.filter(g => g.status === 'active' || g.status === 'paused')
  const completedGoals = goals.filter(g => g.status === 'completed' || g.status === 'archived')

  const openCreate = () => {
    setEditingGoal(null)
    setFormTitle('')
    setFormDesc('')
    setFormPriority(5)
    setFormProgress(0)
    setFormDate('')
    setSheetOpen(true)
  }

  const openEdit = (g: Goal) => {
    setEditingGoal(g)
    setFormTitle(g.title)
    setFormDesc(g.description ?? '')
    setFormPriority(g.priority)
    setFormProgress(g.progress ?? 0)
    setFormDate(g.target_date ?? '')
    setOpenMenu(null)
    setSheetOpen(true)
  }

  const handleSave = async () => {
    if (!formTitle.trim()) return
    setSaving(true)
    try {
      if (editingGoal) {
        const updated = await goalsApi.update(editingGoal.id, {
          title: formTitle,
          description: formDesc || undefined,
          priority: formPriority,
          progress: formProgress,
          target_date: formDate || undefined,
        })
        setGoals(prev => prev.map(g => g.id === editingGoal.id ? updated : g))
      } else {
        const created = await goalsApi.create({
          title: formTitle,
          description: formDesc || undefined,
          priority: formPriority,
          progress: formProgress,
          target_date: formDate || undefined,
        })
        if (created) setGoals(prev => [...prev, created])
      }
      setSheetOpen(false)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleComplete = async (id: string) => {
    try {
      const updated = await goalsApi.update(id, { status: 'completed' })
      setGoals(prev => prev.map(g => g.id === id ? updated : g))
      setOpenMenu(null)
    } catch (e) { console.error(e) }
  }

  const handleArchive = async (id: string) => {
    try {
      await goalsApi.delete(id)
      setGoals(prev => prev.map(g => g.id === id ? { ...g, status: 'archived' as GoalStatus } : g))
      setOpenMenu(null)
    } catch (e) { console.error(e) }
  }

  function GoalRow({ goal }: { goal: Goal }) {
    const dotColor = PRIORITY_COLORS[Math.min(goal.priority - 1, 4)]
    const isCompleted = goal.status === 'completed'
    return (
      <div
        className="flex items-center gap-4 px-5 py-4 rounded-2xl transition-shadow duration-150 hover:shadow-[0_4px_12px_rgba(0,0,0,0.10)]"
        style={{ border: '1px solid rgba(0,0,0,0.08)', background: '#ffffff' }}
      >
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: dotColor }} />
        <div className="flex-1 min-w-0">
          <p
            className="text-sm font-medium truncate"
            style={{
              color: '#0a0a0a',
              textDecoration: isCompleted ? 'line-through' : 'none',
              opacity: isCompleted ? 0.5 : 1,
            }}
          >
            {goal.title}
          </p>
          {goal.description && (
            <p className="text-xs mt-0.5 truncate" style={{ color: '#9e9e9e' }}>{goal.description}</p>
          )}
          {goal.progress !== undefined && goal.progress > 0 && (
            <div className="mt-2">
              <div className="flex justify-between text-xs mb-1" style={{ color: '#9e9e9e' }}>
                <span>Progress</span><span>{goal.progress}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#f0f0f0' }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${goal.progress}%`, background: '#1a1a1a' }} />
              </div>
            </div>
          )}
          {/* Milestones */}
          <div className="mt-3 pt-3 border-t border-[rgba(0,0,0,0.06)]">
            <p className="text-xs font-medium mb-2" style={{ color: '#695e6e' }}>
              Milestones
              {milestones[goal.id] && (
                <span className="ml-1" style={{ color: '#9e9e9e' }}>
                  ({milestones[goal.id].filter(m => m.completed).length}/{milestones[goal.id].length})
                </span>
              )}
            </p>
            <ul className="space-y-1.5 mb-2">
              {(milestones[goal.id] ?? []).map(m => (
                <li key={m.id} className="flex items-center gap-2">
                  <button
                    onClick={async () => {
                      await api.goals.milestones.toggle(goal.id, m.id, !m.completed)
                      loadMilestones(goal.id)
                    }}
                    className="w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors"
                    style={{
                      background: m.completed ? '#4A7C59' : 'transparent',
                      borderColor: m.completed ? '#4A7C59' : '#d4d0d6',
                    }}
                  >
                    {m.completed && <Check size={10} color="#fff" />}
                  </button>
                  <span
                    className="text-xs flex-1"
                    style={{
                      color: m.completed ? '#9e9e9e' : '#1c1520',
                      textDecoration: m.completed ? 'line-through' : 'none',
                    }}
                  >
                    {m.title}
                  </span>
                  <button
                    onClick={async () => {
                      await api.goals.milestones.delete(goal.id, m.id)
                      loadMilestones(goal.id)
                    }}
                  >
                    <X size={11} style={{ color: '#9e9e9e' }} />
                  </button>
                </li>
              ))}
            </ul>
            {/* Add milestone input */}
            <form
              className="flex items-center gap-1.5"
              onSubmit={async e => {
                e.preventDefault()
                const title = (milestoneInput[goal.id] || '').trim()
                if (!title) return
                await api.goals.milestones.create(goal.id, title)
                setMilestoneInput(prev => ({ ...prev, [goal.id]: '' }))
                loadMilestones(goal.id)
              }}
            >
              <input
                type="text"
                value={milestoneInput[goal.id] ?? ''}
                onChange={e => setMilestoneInput(prev => ({ ...prev, [goal.id]: e.target.value }))}
                placeholder="Add milestone…"
                className="flex-1 text-xs px-2 py-1 rounded-lg outline-none"
                style={{ background: '#f5f2ef', color: '#1c1520', border: '1px solid transparent' }}
              />
              <button
                type="submit"
                className="text-xs px-2 py-1 rounded-lg"
                style={{ background: '#000', color: '#fff' }}
              >
                Add
              </button>
            </form>
          </div>
        </div>
        {goal.target_date && (
          <span className="text-xs shrink-0 hidden sm:block" style={{ color: '#9e9e9e' }}>
            {new Date(goal.target_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
        )}
        <StatusBadge status={goal.status as GoalStatus} />
        <div className="relative">
          <button
            onClick={e => { e.stopPropagation(); setOpenMenu(openMenu === goal.id ? null : goal.id) }}
            className="w-11 h-11 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
            aria-label="Goal actions"
          >
            <MoreHorizontal size={15} style={{ color: '#6b6b6b' }} />
          </button>
          {openMenu === goal.id && (
            <div
              className="absolute right-0 top-8 z-10 w-36 rounded-xl py-1 text-sm shadow-lg"
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.08)' }}
            >
              <button
                onClick={() => openEdit(goal)}
                className="w-full text-left px-3 py-2 hover:bg-black/5 transition-colors"
                style={{ color: '#0a0a0a' }}
              >
                Edit
              </button>
              {goal.status === 'active' && (
                <button
                  onClick={() => handleComplete(goal.id)}
                  className="w-full text-left px-3 py-2 hover:bg-black/5 transition-colors"
                  style={{ color: '#4A7C59' }}
                >
                  Mark complete
                </button>
              )}
              <button
                onClick={() => handleArchive(goal.id)}
                className="w-full text-left px-3 py-2 hover:bg-black/5 transition-colors"
                style={{ color: '#B04A3A' }}
              >
                Archive
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5" onClick={() => openMenu && setOpenMenu(null)}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: '#1a1a1a' }}>Your Goals</h2>
          <p className="text-sm mt-0.5" style={{ color: '#6b6b6b' }}>
            Goals inform ESL about your priorities.
          </p>
        </div>
        <button
          onClick={e => { e.stopPropagation(); openCreate() }}
          className="inline-flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: '#000000', color: '#ffffff' }}
        >
          <Plus size={15} />
          Add Goal
        </button>
      </div>

      {/* Filter chips */}
      <FilterChips<StatusFilter>
        chips={[
          { value: null, label: 'All', count: goals.length },
          { value: 'active', label: 'Active', count: goals.filter(g => g.status === 'active').length },
          { value: 'paused', label: 'Paused', count: goals.filter(g => g.status === 'paused').length },
          { value: 'completed', label: 'Completed', count: completedGoals.length },
        ]}
        selected={statusFilter}
        onChange={setStatusFilter}
      />

      {/* Active goals section */}
      {(!statusFilter || statusFilter === 'active' || statusFilter === 'paused') && (
      <Card className="rounded-2xl overflow-hidden border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
        <div className="px-5 py-3 border-b border-black/5">
          <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: '#6b6b6b' }}>
            Active &amp; Paused
          </h3>
        </div>
        <div className="p-3 space-y-2">
          {loading ? (
            [1, 2, 3].map(i => <Skeleton key={i} className="h-14 rounded-xl" />)
          ) : activeGoals.filter(g => !statusFilter || g.status === statusFilter).length === 0 ? (
            <p className="px-2 py-4 text-sm text-center" style={{ color: '#9e9e9e' }}>
              No active goals. Add one to get started.
            </p>
          ) : (
            activeGoals.filter(g => !statusFilter || g.status === statusFilter).map(g => <GoalRow key={g.id} goal={g} />)
          )}
        </div>
      </Card>
      )}

      {/* Completed / archived section */}
      {completedGoals.length > 0 && (!statusFilter || statusFilter === 'completed' || statusFilter === 'archived') && (
        <Card className="rounded-2xl overflow-hidden border border-[rgba(0,0,0,0.08)] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
          <button
            onClick={e => { e.stopPropagation(); setShowCompleted(v => !v) }}
            className="w-full flex items-center justify-between px-5 py-3 border-b border-black/5 hover:bg-black/[0.02] transition-colors"
          >
            <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: '#6b6b6b' }}>
              Completed &amp; Archived ({completedGoals.length})
            </h3>
            {showCompleted
              ? <ChevronDown size={14} style={{ color: '#9e9e9e' }} />
              : <ChevronRight size={14} style={{ color: '#9e9e9e' }} />
            }
          </button>
          {showCompleted && (
            <div className="p-3 space-y-2">
              {completedGoals.filter(g => !statusFilter || g.status === statusFilter).map(g => <GoalRow key={g.id} goal={g} />)}
            </div>
          )}
        </Card>
      )}

      {/* Slide-over sheet */}
      {sheetOpen && (
        <div className="fixed inset-0 z-50 flex" onClick={e => e.stopPropagation()}>
          <div className="flex-1 bg-black/20 backdrop-blur-sm" onClick={() => setSheetOpen(false)} />
          <div className="w-[400px] flex flex-col h-full shadow-2xl" style={{ background: '#f9f9f9' }}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-black/5">
              <h3 className="text-sm font-semibold" style={{ color: '#0a0a0a' }}>
                {editingGoal ? 'Edit Goal' : 'Add Goal'}
              </h3>
              <button onClick={() => setSheetOpen(false)} aria-label="Close sheet">
                <X size={18} style={{ color: '#6b6b6b' }} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>Title</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={e => setFormTitle(e.target.value)}
                  placeholder="e.g. Launch MVP"
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>Description</label>
                <textarea
                  value={formDesc}
                  onChange={e => setFormDesc(e.target.value)}
                  placeholder="Optional details…"
                  rows={3}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none resize-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>Priority (1 = highest)</label>
                <input
                  type="number" min={1} max={10}
                  value={formPriority}
                  onChange={e => setFormPriority(Number(e.target.value))}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                  style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.10)', color: '#0a0a0a' }}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>Progress ({formProgress}%)</label>
                <input
                  type="range" min={0} max={100}
                  value={formProgress}
                  onChange={e => setFormProgress(Number(e.target.value))}
                  className="w-full accent-[#1a1a1a]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#6b6b6b' }}>Target Date</label>
                <input
                  type="date"
                  value={formDate}
                  onChange={e => setFormDate(e.target.value)}
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
                disabled={!formTitle.trim() || saving}
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
