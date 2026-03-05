'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { valuesApi, UserValue } from '@/lib/api'
import { motion } from 'framer-motion'
import {
  Plus,
  Scale,
  Shield,
  Heart,
  Filter,
  Clock,
  Pencil,
  Trash2,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

const VALUE_TYPES = ['boundary', 'preference', 'topic_filter', 'time_window'] as const
type ValueType = typeof VALUE_TYPES[number]

const typeConfig: Record<ValueType, { label: string; color: string; icon: typeof Shield }> = {
  boundary: {
    label: 'Boundary',
    color: 'bg-red-100 text-red-700 border-red-200',
    icon: Shield,
  },
  preference: {
    label: 'Preference',
    color: 'bg-blue-100 text-blue-700 border-blue-200',
    icon: Heart,
  },
  topic_filter: {
    label: 'Topic Filter',
    color: 'bg-purple-100 text-purple-700 border-purple-200',
    icon: Filter,
  },
  time_window: {
    label: 'Time Window',
    color: 'bg-amber-100 text-amber-700 border-amber-200',
    icon: Clock,
  },
}

export default function ValuesPage() {
  const [values, setValues] = useState<UserValue[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingValue, setEditingValue] = useState<UserValue | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<UserValue | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [isReordering, setIsReordering] = useState(false)
  const [originalValues, setOriginalValues] = useState<UserValue[]>([])
  const [reorderError, setReorderError] = useState<string | null>(null)

  // Form state
  const [formType, setFormType] = useState<ValueType>('boundary')
  const [formValue, setFormValue] = useState('')
  const [formPriority, setFormPriority] = useState('5')

  useEffect(() => {
    loadValues()
  }, [])

  const loadValues = async () => {
    try {
      const response = await valuesApi.list()
      const loadedValues = response.values || []
      setValues(loadedValues)
      setOriginalValues(loadedValues) // Store for revert on error
    } catch (error) {
      console.error('Failed to load values:', error)
      setValues([]) // Reset to empty array on error
      setOriginalValues([])
    } finally {
      setLoading(false)
    }
  }

  const openCreateForm = () => {
    setEditingValue(null)
    setFormType('boundary')
    setFormValue('')
    setFormPriority('5')
    setIsFormOpen(true)
  }

  const openEditForm = (value: UserValue) => {
    setEditingValue(value)
    setFormType(value.type)
    setFormValue(value.value)
    setFormPriority(String(value.priority))
    setIsFormOpen(true)
  }

  const handleSubmit = async () => {
    if (!formValue.trim()) return

    setSubmitting(true)
    try {
      if (editingValue) {
        await valuesApi.update(editingValue.id, {
          value: formValue,
          priority: parseInt(formPriority),
        })
      } else {
        await valuesApi.create({
          type: formType,
          value: formValue,
          priority: parseInt(formPriority),
        })
      }
      setIsFormOpen(false)
      await loadValues()
    } catch (error) {
      console.error('Failed to save value:', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return

    setSubmitting(true)
    try {
      await valuesApi.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      await loadValues()
    } catch (error) {
      console.error('Failed to delete value:', error)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReorder = useCallback(async (reorderedValues: UserValue[]) => {
    const previousValues = values  // Capture current state for this reorder
    setValues(reorderedValues)
    setIsReordering(true)
    setReorderError(null)  // Clear any previous errors

    try {
      const response = await fetch('/api/values/reorder', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          valueIds: reorderedValues.map((v) => v.id),
        }),
      })

      if (!response.ok) throw new Error('Failed to reorder values')

      // Update originalValues after successful reorder
      setOriginalValues(reorderedValues)
    } catch (error) {
      console.error('Reorder failed:', error)
      setValues(previousValues)  // Revert to state at start of THIS reorder
      setReorderError('Failed to save value order. Please try again.')
      // Clear error after 5 seconds
      setTimeout(() => setReorderError(null), 5000)
    } finally {
      setIsReordering(false)
    }
  }, [values])

  const filteredValues = filter
    ? values.filter((v) => v.type === filter)
    : values

  const renderValueCard = (value: UserValue, isDragging: boolean) => {
    const config = typeConfig[value.type]
    const Icon = config.icon
    return (
      <Card className={`h-full flex flex-col border-[#E5E5E5] rounded-lg shadow-md hover:shadow-md transition-shadow ${
        isDragging ? 'cursor-grabbing' : 'cursor-grab'
      }`}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <Badge variant="outline" className={`${config.color} rounded-full`}>
              <Icon className="h-3 w-3 mr-1" />
              {config.label}
            </Badge>
            <span className="text-sm text-[#525252]">
              Priority: {value.priority}
            </span>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col">
          <CardTitle className="text-base font-medium mb-4 flex-1 text-[#171717]">
            {value.value}
          </CardTitle>
          <div className="flex gap-2 mt-auto">
            <Button
              variant="outline"
              size="sm"
              className="border-[#E5E5E5] text-[#525252] hover:bg-[#FAFAFA] rounded-lg"
              onClick={() => openEditForm(value)}
            >
              <Pencil className="h-3 w-3 mr-1" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-[#E5E5E5] text-red-600 hover:bg-red-50 hover:text-red-700 rounded-lg"
              onClick={() => setDeleteConfirm(value)}
            >
              <Trash2 className="h-3 w-3 mr-1" />
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Calculate counts for sidebar
  const valueCounts = useMemo(() => {
    return values.reduce((acc, v) => {
      acc[v.type] = (acc[v.type] || 0) + 1
      return acc
    }, {} as Record<string, number>)
  }, [values])

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
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <Skeleton key={i} className="h-[180px] rounded-lg" />
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
              <h1 className="text-2xl font-bold tracking-tight text-[#171717]">My Values</h1>
              <p className="text-[#525252]">
                Define your boundaries and preferences
              </p>
            </div>

            {/* Error Notification */}
            {reorderError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800">
                {reorderError}
              </div>
            )}

            {/* Values List */}
            {filteredValues.length === 0 ? (
              <motion.div variants={itemVariants}>
                <Card className="p-12 text-center border-[#E5E5E5] rounded-lg">
                  <Scale className="h-10 w-10 mx-auto text-[#A3A3A3]" />
                  <h3 className="font-semibold mt-4 text-lg text-[#171717]">No values yet</h3>
                  <p className="text-[#525252] mt-2">
                    Define your boundaries and preferences to help the AI respect your needs.
                  </p>
                  <Button onClick={openCreateForm} className="mt-6 bg-[#171717] hover:bg-[#404040] rounded-full">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Your First Value
                  </Button>
                </Card>
              </motion.div>
            ) : (
              <DragDropList
                items={filteredValues}
                onReorder={handleReorder}
                getItemId={(value) => value.id}
                renderItem={(value, isDragging) => renderValueCard(value, isDragging)}
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
              {editingValue ? 'Edit Value' : 'Add New Value'}
            </SheetTitle>
            <SheetDescription>
              {editingValue
                ? 'Update your boundary or preference.'
                : 'Define a new boundary or preference for the AI to respect.'}
            </SheetDescription>
          </SheetHeader>
          <div className="grid gap-4 py-6">
            {!editingValue && (
              <div className="grid gap-2">
                <Label htmlFor="type">Type</Label>
                <Select
                  value={formType}
                  onValueChange={(v) => setFormType(v as ValueType)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    {VALUE_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>
                        {typeConfig[type].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="value">Value</Label>
              <Input
                id="value"
                placeholder="e.g., No work notifications after 7pm"
                value={formValue}
                onChange={(e) => setFormValue(e.target.value)}
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
          </div>
          <SheetFooter>
            <Button
              onClick={handleSubmit}
              disabled={!formValue.trim() || submitting}
              className="!bg-[#D2691E] hover:!bg-[#B85A19] text-white"
            >
              {submitting
                ? 'Saving...'
                : editingValue
                ? 'Save Changes'
                : 'Add Value'}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Value</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this value? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          {deleteConfirm && (
            <div className="py-4">
              <p className="font-medium">{deleteConfirm.value}</p>
              <p className="text-sm text-muted-foreground mt-1">
                Type: {typeConfig[deleteConfirm.type].label} | Priority:{' '}
                {deleteConfirm.priority}
              </p>
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
