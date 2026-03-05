# UI Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement empty states, skeleton loaders, drag & drop, ESL indicators, status indicators, and focus management to elevate the minimal interface with ethical transparency.

**Architecture:** Phased implementation starting with design system foundation (Geist font, CSS animations), then core reusable components (EmptyState, StatusIndicator, ESLIndicator, enhanced Skeleton), followed by drag & drop functionality, and finally integration across all pages with accessibility enhancements.

**Tech Stack:** Next.js 16, React 19, Tailwind CSS v4, Radix UI, @dnd-kit (drag & drop), Geist font, lucide-react icons

---

## Phase 1: Foundation (Design System Updates)

### Task 1: Install Geist Font

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/layout.tsx`

**Step 1: Install geist package**

Run: `cd frontend && npm install geist`

Expected: Package installed successfully

**Step 2: Update layout.tsx to use Geist font**

File: `frontend/app/layout.tsx`

Find the import section and add:
```tsx
import { GeistSans } from 'geist/font/sans'
```

Then update the `<html>` tag to use the Geist font:
```tsx
<html lang="en" className={GeistSans.className}>
```

**Step 3: Verify font renders**

Run: `npm run dev`

Expected: App starts, font loads (check browser DevTools > Network for geist font files)

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/app/layout.tsx
git commit -m "feat: add Geist font for technical precision aesthetic"
```

---

### Task 2: Update Theme with ESL Colors and Motion

**Files:**
- Modify: `frontend/lib/theme.ts`

**Step 1: Add ESL colors to theme**

File: `frontend/lib/theme.ts`

Add after existing theme object:

```typescript
export const theme = {
  // ... existing colors, shadows, radius, transitions, spacing

  // ESL ambient indicators
  esl: {
    approved: 'rgba(5, 150, 105, 0.1)',    // Green tint
    vetoed: 'rgba(220, 38, 38, 0.1)',      // Red tint
    modified: 'rgba(37, 99, 235, 0.1)',    // Blue tint
    pulse: 'rgba(23, 23, 23, 0.05)',       // Neutral pulse
  },

  // Physics-based animations
  motion: {
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',   // Elastic feel
    magnetic: 'cubic-bezier(0.22, 0.61, 0.36, 1)', // Smooth snap
  }
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build`

Expected: Build succeeds with no type errors

**Step 3: Commit**

```bash
git add frontend/lib/theme.ts
git commit -m "feat: add ESL colors and motion curves to theme"
```

---

### Task 3: Add CSS Keyframe Animations

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: Add shimmer and pulse animations**

File: `frontend/app/globals.css`

Add at the end of the file (after existing styles):

```css
/* Shimmer animation for skeleton loaders */
@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* ESL pulse animation (signature interaction) */
@keyframes esl-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.5);
    opacity: 0.5;
  }
}

/* Utility classes */
.animate-shimmer {
  animation: shimmer 2s infinite;
}

.animate-esl-pulse {
  animation: esl-pulse 150ms ease-out;
}
```

**Step 2: Verify CSS compiles**

Run: `npm run dev`

Expected: No CSS errors in console

**Step 3: Test animation with simple div (optional manual test)**

Create temporary test in any page:
```tsx
<div className="h-10 w-10 bg-black animate-esl-pulse" />
```

Expected: Div pulses once on mount

**Step 4: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: add shimmer and ESL pulse keyframe animations"
```

---

## Phase 2: Core Components

### Task 4: Create EmptyState Component

**Files:**
- Create: `frontend/components/ui/empty-state.tsx`

**Step 1: Create EmptyState component file**

File: `frontend/components/ui/empty-state.tsx`

```tsx
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  className
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center",
        className
      )}
      role="status"
      aria-label="No items found"
    >
      <Icon className="h-8 w-8 text-[#D4D4D4] mb-4" />
      <h3 className="text-lg font-medium text-[#171717] mb-2">{title}</h3>
      <p className="text-sm text-[#525252] max-w-sm">{description}</p>
    </div>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/components/ui/empty-state.tsx
git commit -m "feat: add EmptyState component for minimal informative empty states"
```

---

### Task 5: Create StatusIndicator Component

**Files:**
- Create: `frontend/components/ui/status-indicator.tsx`

**Step 1: Create StatusIndicator component**

File: `frontend/components/ui/status-indicator.tsx`

```tsx
import {
  CheckCircle,
  XCircle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Info
} from 'lucide-react'
import { cn } from '@/lib/utils'

type StatusType =
  | 'success'
  | 'error'
  | 'warning'
  | 'info'
  | 'esl-approved'
  | 'esl-vetoed'
  | 'esl-modified'

interface StatusIndicatorProps {
  type: StatusType
  message: string
  className?: string
}

const config: Record<StatusType, { icon: any; color: string; bg: string }> = {
  success: {
    icon: CheckCircle,
    color: 'text-[#059669]',
    bg: 'bg-[#059669]/10'
  },
  error: {
    icon: XCircle,
    color: 'text-[#DC2626]',
    bg: 'bg-[#DC2626]/10'
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-[#D97706]',
    bg: 'bg-[#D97706]/10'
  },
  info: {
    icon: Info,
    color: 'text-[#2563EB]',
    bg: 'bg-[#2563EB]/10'
  },
  'esl-approved': {
    icon: Shield,
    color: 'text-[#059669]',
    bg: 'bg-[#059669]/10'
  },
  'esl-vetoed': {
    icon: ShieldAlert,
    color: 'text-[#DC2626]',
    bg: 'bg-[#DC2626]/10'
  },
  'esl-modified': {
    icon: ShieldCheck,
    color: 'text-[#2563EB]',
    bg: 'bg-[#2563EB]/10'
  }
}

export function StatusIndicator({
  type,
  message,
  className
}: StatusIndicatorProps) {
  const { icon: Icon, color, bg } = config[type]

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg",
        bg,
        className
      )}
      role="status"
      aria-live="polite"
    >
      <Icon className={cn("h-4 w-4", color)} />
      <span className={cn("text-sm font-medium", color)}>{message}</span>
    </div>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/components/ui/status-indicator.tsx
git commit -m "feat: add StatusIndicator component with icon + color + text pattern"
```

---

### Task 6: Create ESLIndicator Component

**Files:**
- Create: `frontend/components/ui/esl-indicator.tsx`

**Step 1: Create ESLIndicator component**

File: `frontend/components/ui/esl-indicator.tsx`

```tsx
'use client'

import { Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'

interface ESLIndicatorProps {
  status: 'approved' | 'vetoed' | 'modified'
  reason: string
  className?: string
  pulse?: boolean
}

const statusColors = {
  approved: 'ring-[#059669]/30 bg-[#059669]/10',
  vetoed: 'ring-[#DC2626]/30 bg-[#DC2626]/10',
  modified: 'ring-[#2563EB]/30 bg-[#2563EB]/10'
}

export function ESLIndicator({
  status,
  reason,
  className,
  pulse = false
}: ESLIndicatorProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "h-2 w-2 rounded-full bg-[#D4D4D4] transition-all duration-150",
              "opacity-0 group-hover:opacity-100",
              "group-hover:h-4 group-hover:w-4 group-hover:ring-2",
              statusColors[status],
              pulse && "animate-esl-pulse",
              className
            )}
            role="status"
            aria-live="polite"
            aria-label={`ESL decision: ${status}`}
          />
        </TooltipTrigger>
        <TooltipContent
          side="left"
          className="bg-[#171717] text-white border-[#404040] rounded-lg"
        >
          <div className="flex items-center gap-2">
            <Shield className="h-3 w-3" />
            <span className="text-xs font-medium">{reason}</span>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/components/ui/esl-indicator.tsx
git commit -m "feat: add ESLIndicator ambient dot with hover tooltip"
```

---

### Task 7: Enhance Skeleton Component with Shimmer

**Files:**
- Modify: `frontend/components/ui/skeleton.tsx`

**Step 1: Read current skeleton component**

File: `frontend/components/ui/skeleton.tsx`

Current content (from earlier):
```tsx
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("bg-accent animate-pulse rounded-md", className)}
      {...props}
    />
  )
}

export { Skeleton }
```

**Step 2: Enhance with shimmer effect**

Replace with:
```tsx
import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "bg-[#F5F5F5] animate-pulse rounded-lg",
        "relative overflow-hidden",
        "before:absolute before:inset-0",
        "before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        "before:animate-shimmer",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
```

**Step 3: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 4: Test skeleton visually (optional)**

Add to any page temporarily:
```tsx
<Skeleton className="h-20 w-full" />
```

Expected: Gray box with subtle shimmer animation

**Step 5: Commit**

```bash
git add frontend/components/ui/skeleton.tsx
git commit -m "feat: enhance Skeleton with shimmer gradient animation"
```

---

## Phase 3: Drag & Drop

### Task 8: Install @dnd-kit Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install @dnd-kit packages**

Run:
```bash
cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
```

Expected: Packages installed successfully

**Step 2: Verify installation**

Run: `npm list @dnd-kit/core`

Expected: Shows installed version

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat: add @dnd-kit packages for drag & drop functionality"
```

---

### Task 9: Create DragDropList Component

**Files:**
- Create: `frontend/components/drag-drop-list.tsx`

**Step 1: Create DragDropList wrapper component**

File: `frontend/components/drag-drop-list.tsx`

```tsx
'use client'

import { useState } from 'react'
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
    zIndex: isDragging ? 1000 : 'auto'
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      role="button"
      aria-label={`Reorder item. Press space to grab.`}
      tabIndex={0}
    >
      {children(isDragging)}
    </div>
  )
}
```

**Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/components/drag-drop-list.tsx
git commit -m "feat: add DragDropList component with magnetic snap animation"
```

---

### Task 10: Add Drag & Drop to Goals Page

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

**Step 1: Read current goals page**

Check the current implementation to understand structure.

**Step 2: Add DragDropList to goals page**

Import at top:
```tsx
import { DragDropList } from '@/components/drag-drop-list'
import { useState, useEffect } from 'react'
```

Replace static list with:
```tsx
const [goals, setGoals] = useState(fetchedGoals)
const [isReordering, setIsReordering] = useState(false)

async function handleReorder(reorderedGoals) {
  setGoals(reorderedGoals)
  setIsReordering(true)

  try {
    const response = await fetch('/api/goals/reorder', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goalIds: reorderedGoals.map(g => g.id)
      })
    })

    if (!response.ok) throw new Error('Failed to reorder')
  } catch (error) {
    console.error('Reorder failed:', error)
    // Revert on error
    setGoals(fetchedGoals)
  } finally {
    setIsReordering(false)
  }
}

// In JSX:
<DragDropList
  items={goals}
  onReorder={handleReorder}
  getItemId={(goal) => goal.id}
  renderItem={(goal, isDragging) => (
    <GoalCard goal={goal} className={isDragging ? 'cursor-grabbing' : 'cursor-grab'} />
  )}
/>
```

**Step 3: Test drag functionality (manual)**

Run: `npm run dev`

Expected: Can drag goals to reorder (will fail on API call until backend implemented)

**Step 4: Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx
git commit -m "feat: add drag & drop reordering to Goals page"
```

---

### Task 11: Add Drag & Drop to Values Page

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`

**Step 1: Add DragDropList to values page**

Same pattern as goals page:

```tsx
import { DragDropList } from '@/components/drag-drop-list'

// In component:
async function handleReorder(reorderedValues) {
  setValues(reorderedValues)

  try {
    await fetch('/api/values/reorder', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        valueIds: reorderedValues.map(v => v.id)
      })
    })
  } catch (error) {
    console.error('Reorder failed:', error)
    setValues(originalValues)
  }
}

// In JSX:
<DragDropList
  items={values}
  onReorder={handleReorder}
  getItemId={(value) => value.id}
  renderItem={(value, isDragging) => (
    <ValueCard value={value} className={isDragging ? 'cursor-grabbing' : 'cursor-grab'} />
  )}
/>
```

**Step 2: Verify TypeScript compiles**

Run: `npm run build`

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/app/dashboard/values/page.tsx
git commit -m "feat: add drag & drop reordering to Values page"
```

---

## Phase 4: Integration (Apply to All Pages)

### Task 12: Add Skeleton Loaders to Dashboard

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

**Step 1: Add loading state with skeleton**

Import:
```tsx
import { Skeleton } from '@/components/ui/skeleton'
import { useState, useEffect } from 'react'
```

Add loading state:
```tsx
const [isLoading, setIsLoading] = useState(true)

useEffect(() => {
  async function loadData() {
    setIsLoading(true)
    // Fetch data
    await fetchDashboardData()
    setIsLoading(false)
  }
  loadData()
}, [])

// In JSX:
{isLoading ? (
  <div className="space-y-6">
    <Skeleton className="h-24 w-full" />
    <Skeleton className="h-24 w-full" />
    <Skeleton className="h-64 w-full" />
    <div className="grid grid-cols-2 gap-4">
      <Skeleton className="h-32" />
      <Skeleton className="h-32" />
    </div>
  </div>
) : (
  // Actual content
)}
```

**Step 2: Verify skeleton appears on load**

Run: `npm run dev`

Expected: Skeletons appear briefly, then content loads

**Step 3: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: add skeleton loaders to Dashboard page"
```

---

### Task 13: Add Empty State to Dashboard

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

**Step 1: Add empty state for no goals/values**

Import:
```tsx
import { EmptyState } from '@/components/ui/empty-state'
import { Target, Shield } from 'lucide-react'
```

Add conditional rendering:
```tsx
{goals.length === 0 && (
  <EmptyState
    icon={Target}
    title="No goals yet"
    description="Goals help the system understand your priorities"
  />
)}

{values.length === 0 && (
  <EmptyState
    icon={Shield}
    title="No values defined"
    description="Values guide the ESL to respect your boundaries"
  />
)}
```

**Step 2: Test with empty data**

Clear goals/values in database, reload page

Expected: Empty states appear

**Step 3: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: add empty states to Dashboard for no goals/values"
```

---

### Task 14: Add Skeleton and Empty State to Goals Page

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

**Step 1: Add loading state**

```tsx
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Target } from 'lucide-react'

const [isLoading, setIsLoading] = useState(true)

// In JSX:
{isLoading ? (
  <div className="space-y-3">
    {[1, 2, 3].map(i => (
      <Skeleton key={i} className="h-20 w-full" />
    ))}
  </div>
) : goals.length === 0 ? (
  <EmptyState
    icon={Target}
    title="No goals yet"
    description="Create your first goal to help the system understand your priorities"
  />
) : (
  <DragDropList ... />
)}
```

**Step 2: Verify renders correctly**

Run: `npm run dev`

Expected: Skeleton → Empty state OR goal list

**Step 3: Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx
git commit -m "feat: add skeleton loader and empty state to Goals page"
```

---

### Task 15: Add Skeleton and Empty State to Values Page

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`

**Step 1: Add loading and empty states**

Same pattern as goals:

```tsx
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Shield } from 'lucide-react'

{isLoading ? (
  <div className="space-y-3">
    {[1, 2, 3].map(i => <Skeleton key={i} className="h-20 w-full" />)}
  </div>
) : values.length === 0 ? (
  <EmptyState
    icon={Shield}
    title="No values defined"
    description="Values guide the ESL to protect your boundaries"
  />
) : (
  <DragDropList ... />
)}
```

**Step 2: Commit**

```bash
git add frontend/app/dashboard/values/page.tsx
git commit -m "feat: add skeleton loader and empty state to Values page"
```

---

### Task 16: Add Status Indicators to Form Submissions

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx` (create goal dialog)
- Modify: `frontend/app/dashboard/values/page.tsx` (create value dialog)

**Step 1: Add status indicator after form submission**

Import:
```tsx
import { StatusIndicator } from '@/components/ui/status-indicator'
```

Add state:
```tsx
const [submitStatus, setSubmitStatus] = useState<{
  type: 'success' | 'error'
  message: string
} | null>(null)

async function handleSubmit(data) {
  try {
    await createGoal(data)
    setSubmitStatus({
      type: 'success',
      message: 'Goal created successfully'
    })
    setTimeout(() => setSubmitStatus(null), 3000)
  } catch (error) {
    setSubmitStatus({
      type: 'error',
      message: 'Failed to create goal'
    })
  }
}

// In dialog:
{submitStatus && (
  <StatusIndicator
    type={submitStatus.type}
    message={submitStatus.message}
  />
)}
```

**Step 2: Test form submission**

Create a goal, verify status indicator appears

**Step 3: Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx frontend/app/dashboard/values/page.tsx
git commit -m "feat: add status indicators to goal/value form submissions"
```

---

### Task 17: Update Dialog Focus Management

**Files:**
- Modify: `frontend/components/ui/dialog.tsx`

**Step 1: Read current dialog component**

File: `frontend/components/ui/dialog.tsx`

Check existing implementation.

**Step 2: Add focus management**

Update DialogContent:

```tsx
const DialogContent = React.forwardRef<...>(
  ({ className, children, ...props }, ref) => {
    const closeButtonRef = useRef<HTMLButtonElement>(null)

    useEffect(() => {
      // Focus close button when dialog opens
      closeButtonRef.current?.focus()
    }, [])

    return (
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          ref={ref}
          onEscapeKeyDown={(e) => {
            // Ensure Esc always closes
          }}
          {...props}
        >
          {children}
          <DialogPrimitive.Close
            ref={closeButtonRef}
            className="absolute right-4 top-4 rounded-lg opacity-70 hover:opacity-100
                       focus:outline-none focus:ring-2 focus:ring-[#171717] focus:ring-offset-2"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPortal>
    )
  }
)
```

**Step 3: Test dialog focus**

Open any dialog, verify close button is focused

Press Tab, verify focus cycles through elements

Press Esc, verify dialog closes

**Step 4: Commit**

```bash
git add frontend/components/ui/dialog.tsx
git commit -m "feat: add focus management to Dialog component"
```

---

## Phase 5: Polish & Accessibility

### Task 18: Add Staggered Fade-In Animations

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`
- Modify: `frontend/app/dashboard/values/page.tsx`

**Step 1: Add staggered reveal to list items**

Update rendering to include animation delays:

```tsx
<DragDropList
  items={goals}
  onReorder={handleReorder}
  getItemId={(goal) => goal.id}
  renderItem={(goal, isDragging, index) => (
    <div
      style={{ animationDelay: `${index * 50}ms` }}
      className="animate-fade-in"
    >
      <GoalCard goal={goal} />
    </div>
  )}
/>
```

Add CSS to `globals.css`:
```css
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 150ms ease-out forwards;
}
```

**Step 2: Test animation**

Reload page, verify items fade in with stagger

**Step 3: Commit**

```bash
git add frontend/app/globals.css frontend/app/dashboard/goals/page.tsx frontend/app/dashboard/values/page.tsx
git commit -m "feat: add staggered fade-in animations to list items"
```

---

### Task 19: Add prefers-reduced-motion Support

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: Add reduced-motion media query**

Add to globals.css:

```css
@media (prefers-reduced-motion: reduce) {
  .animate-shimmer,
  .animate-esl-pulse,
  .animate-fade-in {
    animation: none !important;
  }

  * {
    transition-duration: 0.01ms !important;
  }
}
```

**Step 2: Test with reduced motion enabled**

In macOS: System Preferences → Accessibility → Display → Reduce motion

Expected: No animations play

**Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: add prefers-reduced-motion support for accessibility"
```

---

### Task 20: Keyboard Navigation Testing

**Manual Testing Steps:**

**Step 1: Test Tab navigation**

1. Press Tab repeatedly on dashboard
2. Verify focus visible on all interactive elements
3. Verify focus ring is 2px, offset 2px, color #171717

**Step 2: Test Dialog navigation**

1. Open create goal dialog
2. Verify close button focused on open
3. Press Tab, verify cycles through form fields
4. Press Esc, verify dialog closes
5. Verify focus returns to trigger button

**Step 3: Test Drag with keyboard**

1. Focus on a goal card
2. Press Space to grab
3. Press Arrow keys to move
4. Press Space to drop
5. Verify order persisted

**Step 4: Document test results**

Create: `docs/testing/keyboard-navigation-results.md`

```markdown
# Keyboard Navigation Test Results

**Date**: 2026-02-07

## Tab Navigation
- [ ] All interactive elements focusable
- [ ] Focus ring visible (2px #171717)
- [ ] Logical tab order

## Dialog Focus
- [ ] Close button auto-focused on open
- [ ] Tab cycles through dialog elements
- [ ] Esc closes dialog
- [ ] Focus returns to trigger

## Drag & Drop
- [ ] Space grabs item
- [ ] Arrow keys move item
- [ ] Space drops item
- [ ] Order persists
```

**Step 5: Fix any issues found**

Address issues discovered during testing.

**Step 6: Commit test results**

```bash
git add docs/testing/keyboard-navigation-results.md
git commit -m "docs: add keyboard navigation test results"
```

---

### Task 21: Update DESIGN_SYSTEM.md

**Files:**
- Modify: `DESIGN_SYSTEM.md`

**Step 1: Add new component documentation**

Add sections for:

**EmptyState Component**
```markdown
### EmptyState

**Usage**:
```tsx
<EmptyState
  icon={Target}
  title="No goals yet"
  description="Goals help the system understand your priorities"
/>
```

**Props**:
- icon: LucideIcon (32px)
- title: string (text-lg, font-medium)
- description: string (text-sm, max 1 line)

**Rules**:
- No CTA buttons (respects autonomy)
- Centered layout
- Generous whitespace (py-12)
```

Add similar sections for StatusIndicator, ESLIndicator, DragDropList

**Step 2: Document ESL patterns**

```markdown
## ESL Ambient Indicators

**Visual States**:
- Default: 8px neutral dot, opacity: 0
- Hover: 16px with colored ring, opacity: 100
- Pulse: Triggered when ESL actively protects

**Colors**:
- Approved: Green rgba(5, 150, 105, 0.3)
- Vetoed: Red rgba(220, 38, 38, 0.3)
- Modified: Blue rgba(37, 99, 235, 0.3)
```

**Step 3: Commit**

```bash
git add DESIGN_SYSTEM.md
git commit -m "docs: add EmptyState, StatusIndicator, ESLIndicator, DragDrop to design system"
```

---

## Testing Checklist

### Manual Tests

- [ ] **Empty States**: Clear database, verify all pages show empty states
- [ ] **Skeleton Loaders**: Throttle network to Slow 3G, verify loaders appear
- [ ] **Drag & Drop**: Reorder 10+ items, refresh page, verify order persists
- [ ] **ESL Indicators**: Create goal with ESL protection, verify indicator appears
- [ ] **Status Indicators**: Submit forms, verify success/error feedback
- [ ] **Focus Management**: Tab through app, verify all focus states visible
- [ ] **Keyboard Drag**: Use Space + Arrows to reorder items
- [ ] **Reduced Motion**: Enable in OS settings, verify animations disabled

### Accessibility Tests

- [ ] **VoiceOver**: Navigate with VoiceOver, verify all elements announced
- [ ] **Contrast**: Use browser contrast checker, verify WCAG AAA (7:1)
- [ ] **ARIA**: Inspect roles, verify `role="status"` on indicators
- [ ] **Screen Reader Labels**: Verify aria-label on icon-only elements

### Performance Tests

- [ ] **Bundle Size**: Run `npm run build`, verify total size increase < 50KB
- [ ] **Page Load**: Use Lighthouse, verify no regression (< 100ms slower)
- [ ] **Animation Performance**: Open DevTools Performance tab, verify 60fps

---

## Backend Requirements (Separate Task)

**Note**: These backend endpoints are required for full functionality but are NOT part of this frontend implementation plan.

### Database Migrations

```sql
-- Add position column to goals table
ALTER TABLE goals ADD COLUMN position INTEGER DEFAULT 0;

-- Add position column to user_values table
ALTER TABLE user_values ADD COLUMN position INTEGER DEFAULT 0;

-- Set initial positions
UPDATE goals SET position = ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at);
UPDATE user_values SET position = ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at);
```

### API Endpoints

**PATCH /api/goals/reorder**
```python
@router.patch("/goals/reorder")
async def reorder_goals(
    goal_ids: List[str],
    user_id: str = Depends(get_current_user)
):
    for index, goal_id in enumerate(goal_ids):
        await db.execute(
            "UPDATE goals SET position = $1 WHERE id = $2 AND user_id = $3",
            index, goal_id, user_id
        )
    return {"success": True}
```

**PATCH /api/values/reorder**
```python
@router.patch("/values/reorder")
async def reorder_values(
    value_ids: List[str],
    user_id: str = Depends(get_current_user)
):
    for index, value_id in enumerate(value_ids):
        await db.execute(
            "UPDATE user_values SET position = $1 WHERE id = $2 AND user_id = $3",
            index, value_id, user_id
        )
    return {"success": True}
```

---

## Success Criteria

### Functional
- [x] Geist font renders across app
- [ ] EmptyState component works on all pages
- [ ] StatusIndicator shows on form submissions
- [ ] ESLIndicator appears with hover tooltip
- [ ] Skeleton loaders show during data fetches
- [ ] Drag & drop reorders goals and values
- [ ] Focus management works in dialogs

### Accessibility
- [ ] All interactive elements keyboard accessible
- [ ] Focus states visible (2px ring)
- [ ] Screen reader compatible
- [ ] WCAG AAA contrast (7:1)
- [ ] Reduced motion support

### Performance
- [ ] Bundle size increase < 50KB
- [ ] Page load time increase < 100ms
- [ ] Animations run at 60fps

---

## Rollback Plan

If issues arise, roll back in reverse order:

1. **Phase 5**: Remove staggered animations, revert accessibility additions
2. **Phase 4**: Remove component integrations, restore original pages
3. **Phase 3**: Remove drag & drop, uninstall @dnd-kit
4. **Phase 2**: Remove new components (EmptyState, StatusIndicator, ESLIndicator)
5. **Phase 1**: Revert theme changes, remove Geist font, remove CSS animations

Each phase can be reverted independently via git:
```bash
git revert <commit-hash>
```

---

**End of Implementation Plan**

*Total estimated time: 38-52 hours across 21 tasks*
*Phases can be completed sequentially or in parallel (Phase 2 and 3 are independent)*
