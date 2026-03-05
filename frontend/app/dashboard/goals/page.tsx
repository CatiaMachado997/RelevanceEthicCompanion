'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { goalsApi, Goal } from '@/lib/api'
import { motion } from 'framer-motion'
import {
  Plus,
  Target,
  CheckCircle2,
  Pause,
  Archive,
  Pencil,
  Trash2,
  Calendar,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { TopHeader } from '@/components/top-header'
import { DragDropList } from '@/components/drag-drop-list'

const STATUS_OPTIONS = ['active', 'completed', 'paused', 'archived'] as const
type GoalStatus = typeof STATUS_OPTIONS[number]

const statusConfig: Record<GoalStatus, { label: string; color: string; icon: typeof Target }> = {
  active: {
    label: 'Active',
    color: 'bg-blue-100 text-blue-700 border-blue-200',
    icon: Target,
  },
  completed: {
    label: 'Completed',
    color: 'bg-green-100 text-[#171717] border-[#E5E5E5]',
    icon: CheckCircle2,
  },
  paused: {
    label: 'Paused',
    color: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    icon: Pause,
  },
  archived: {
    label: 'Archived',
    color: 'bg-gray-100 text-gray-500 border-gray-200',
    icon: Archive,
  },
}

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string | null>('active')
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Goal | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [isReordering, setIsReordering] = useState(false)
  const [originalGoals, setOriginalGoals] = useState<Goal[]>([])
  const [reorderError, setReorderError] = useState<string | null>(null)

  // Form state
  const [formTitle, setFormTitle] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formPriority, setFormPriority] = useState('5')
  const [formTargetDate, setFormTargetDate] = useState('')

  useEffect(() => {
    loadGoals()
  }, [filter])

  const loadGoals = async () => {
    try {
      const response = await goalsApi.list(filter || undefined)
      const loadedGoals = response.goals || []
      setGoals(loadedGoals)
      setOriginalGoals(loadedGoals) // Store for revert on error
    } catch (error) {
      console.error('Failed to load goals:', error)
      setGoals([]) // Reset to empty array on error
      setOriginalGoals([])
    } finally {
      setLoading(false)
    }
  }

  const openCreateForm = () => {
    setEditingGoal(null)
    setFormTitle('')
    setFormDescription('')
    setFormPriority('5')
    setFormTargetDate('')
    setIsFormOpen(true)
  }

  const openEditForm = (goal: Goal) => {
    setEditingGoal(goal)
    setFormTitle(goal.title)
    setFormDescription(goal.description || '')
    setFormPriority(String(goal.priority))
    setFormTargetDate(goal.target_date ? goal.target_date.split('T')[0] : '')
    setIsFormOpen(true)
  }

  const handleSubmit = async () => {
    if (!formTitle.trim()) return

    setSubmitting(true)
    try {
      const data = {
        title: formTitle,
        description: formDescription || undefined,
        priority: parseInt(formPriority),
        target_date: formTargetDate || undefined,
      }

      if (editingGoal) {
        await goalsApi.update(editingGoal.id, data)
      } else {
        await goalsApi.create(data)
      }
      setIsFormOpen(false)
      await loadGoals()
    } catch (error) {
      console.error('Failed to save goal:', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleStatusChange = async (goal: Goal, newStatus: GoalStatus) => {
    try {
      await goalsApi.update(goal.id, { status: newStatus })
      await loadGoals()
    } catch (error) {
      console.error('Failed to update goal status:', error)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return

    setSubmitting(true)
    try {
      await goalsApi.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      await loadGoals()
    } catch (error) {
      console.error('Failed to delete goal:', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReorder = useCallback(async (reorderedGoals: Goal[]) => {
    const previousGoals = goals  // Capture current state for this reorder
    setGoals(reorderedGoals)
    setIsReordering(true)
    setReorderError(null)  // Clear any previous errors

    try {
      const response = await fetch('/api/goals/reorder', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goalIds: reorderedGoals.map((g) => g.id),
        }),
      })

      if (!response.ok) throw new Error('Failed to reorder goals')

      // Update originalGoals after successful reorder
      setOriginalGoals(reorderedGoals)
    } catch (error) {
      console.error('Reorder failed:', error)
      setGoals(previousGoals)  // Revert to state at start of THIS reorder
      setReorderError('Failed to save goal order. Please try again.')
      // Clear error after 5 seconds
      setTimeout(() => setReorderError(null), 5000)
    } finally {
      setIsReordering(false)
    }
  }, [goals])

  const formatDate = (dateString: string | null) => {
    if (!dateString) return null
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  const renderGoalCard = (goal: Goal, isDragging: boolean) => {
    const index = goals.findIndex((g) => g.id === goal.id)
    const config = statusConfig[goal.status]
    const Icon = config.icon

    return (
      <Card
        className={`border-[#E5E5E5] rounded-lg shadow-md hover:shadow-md transition-shadow ${
          isDragging ? 'cursor-grabbing' : 'cursor-grab'
        }`}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold text-[#A3A3A3]">
                {index + 1}
              </span>
              <div>
                <CardTitle className="text-lg text-[#171717]">{goal.title}</CardTitle>
                {goal.description && (
                  <p className="text-sm text-[#525252] mt-1">
                    {goal.description}
                  </p>
                )}
              </div>
            </div>
            <Badge variant="outline" className={`${config.color} rounded-full`}>
              <Icon className="h-3 w-3 mr-1" />
              {config.label}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4 text-sm text-[#525252]">
              {goal.target_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Target: {formatDate(goal.target_date)}
                </span>
              )}
              <span>Priority: {goal.priority}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {goal.status === 'active' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-[#E5E5E5] text-[#171717] hover:bg-[#F5F5F5] hover:text-[#171717] rounded-lg"
                  onClick={() => handleStatusChange(goal, 'completed')}
                >
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Complete
                </Button>
              )}
              {goal.status !== 'archived' && (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-[#E5E5E5] text-[#525252] hover:bg-[#FAFAFA] rounded-lg"
                  onClick={() => handleStatusChange(goal, 'archived')}
                >
                  <Archive className="h-3 w-3 mr-1" />
                  Archive
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="border-[#E5E5E5] text-[#525252] hover:bg-[#FAFAFA] rounded-lg"
                onClick={() => openEditForm(goal)}
              >
                <Pencil className="h-3 w-3 mr-1" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-[#E5E5E5] text-red-600 hover:bg-red-50 hover:text-red-700 rounded-lg"
                onClick={() => setDeleteConfirm(goal)}
              >
                <Trash2 className="h-3 w-3 mr-1" />
                Delete
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Calculate counts for sidebar
  const goalCounts = useMemo(() => {
    if (!goals || !Array.isArray(goals)) return {}
    return goals.reduce((acc, g) => {
      acc[g.status] = (acc[g.status] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }, [goals])

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
    },
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1 },
  }

  if (loading) {
    return (
      <>
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <TopHeader />
          <div className="flex-1 overflow-y-auto p-6 bg-white">
            <div className="space-y-6 max-w-5xl">
              <div className="flex flex-col space-y-2">
                <Skeleton className="h-8 w-[200px]" />
                <Skeleton className="h-4 w-[300px]" />
              </div>
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-[140px] rounded-lg" />
                ))}
              </div>
            </div>
          </div>
        </main>
      </>
    )
  }

  return (
    <>
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader />
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          <motion.div
            className="space-y-6 max-w-5xl"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {/* Header */}
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-bold tracking-tight text-[#171717]">Goals</h1>
              <p className="text-[#525252]">Track what matters to you</p>
            </div>

            {/* Error Notification */}
            {reorderError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                {reorderError}
              </div>
            )}

            {/* Goals List */}
            {(!goals || goals.length === 0) ? (
              <motion.div variants={itemVariants}>
                <Card className="p-12 text-center border-[#E5E5E5] rounded-lg">
                  <Target className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                  <h3 className="font-semibold mt-4 text-lg text-[#171717]">No goals yet</h3>
                  <p className="text-[#525252] mt-2">
                    Set your first goal to start tracking what matters to you.
                  </p>
                  <Button onClick={openCreateForm} className="mt-6 bg-[#171717] hover:bg-[#404040] rounded-full">
                    <Plus className="h-4 w-4 mr-2" />
                    Create Your First Goal
                  </Button>
                </Card>
              </motion.div>
            ) : (
              <DragDropList
                items={goals}
                onReorder={handleReorder}
                getItemId={(goal) => goal.id}
                renderItem={(goal, isDragging) => renderGoalCard(goal, isDragging)}
              />
            )}
          </motion.div>
        </div>
      </main>

      {/* Create/Edit Sheet */}
      <Sheet open={isFormOpen} onOpenChange={setIsFormOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>
              {editingGoal ? 'Edit Goal' : 'Create New Goal'}
            </SheetTitle>
            <SheetDescription>
              {editingGoal
                ? 'Update your goal details.'
                : 'Set a new goal to track your progress.'}
            </SheetDescription>
          </SheetHeader>
          <div className="grid gap-4 py-6">
            <div className="grid gap-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                placeholder="e.g., Launch MVP"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description (optional)</Label>
              <Textarea
                id="description"
                placeholder="Describe your goal..."
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="priority">Priority (1-10)</Label>
              <Select value={formPriority} onValueChange={setFormPriority}>
                <SelectTrigger>
                  <SelectValue placeholder="Select priority" />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((p) => (
                    <SelectItem key={p} value={String(p)}>
                      {p} {p === 1 ? '(Highest)' : p === 10 ? '(Lowest)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="target_date">Target Date (optional)</Label>
              <Input
                id="target_date"
                type="date"
                value={formTargetDate}
                onChange={(e) => setFormTargetDate(e.target.value)}
              />
            </div>
          </div>
          <SheetFooter>
            <Button
              onClick={handleSubmit}
              disabled={!formTitle.trim() || submitting}
              className="!bg-[#D2691E] hover:!bg-[#B85A19] text-white"
            >
              {submitting
                ? 'Saving...'
                : editingGoal
                ? 'Save Changes'
                : 'Create Goal'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Goal</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this goal? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          {deleteConfirm && (
            <div className="py-4">
              <p className="font-medium">{deleteConfirm.title}</p>
              {deleteConfirm.description && (
                <p className="text-sm text-muted-foreground mt-1">
                  {deleteConfirm.description}
                </p>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={submitting}
            >
              {submitting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
