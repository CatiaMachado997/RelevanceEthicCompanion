'use client'

import * as React from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

interface DragDropListProps<T> {
  items: T[]
  onReorder: (items: T[]) => void
  renderItem: (item: T, isDragging: boolean) => React.ReactNode
  getItemId: (item: T) => string
}

export function DragDropList<T>({
  items,
  onReorder,
  renderItem,
  getItemId
}: DragDropListProps<T>) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  )

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event

    if (over && active.id !== over.id) {
      const oldIndex = items.findIndex(item => getItemId(item) === active.id)
      const newIndex = items.findIndex(item => getItemId(item) === over.id)
      const reordered = arrayMove(items, oldIndex, newIndex)
      onReorder(reordered)
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={items.map(getItemId)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-3">
          {items.map(item => (
            <SortableItem
              key={getItemId(item)}
              id={getItemId(item)}
            >
              {isDragging => renderItem(item, isDragging)}
            </SortableItem>
          ))}
        </div>
      </SortableContext>
    </DndContext>
  )
}

DragDropList.displayName = 'DragDropList'

interface SortableItemProps {
  id: string
  children: (isDragging: boolean) => React.ReactNode
}

function SortableItem({ id, children }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition: transition || 'transform 150ms cubic-bezier(0.22, 0.61, 0.36, 1)',
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : undefined
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      role="button"
      aria-label="Reorder item. Press space to grab."
      tabIndex={0}
    >
      {children(isDragging)}
    </div>
  )
}

SortableItem.displayName = 'SortableItem'
