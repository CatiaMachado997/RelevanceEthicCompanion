# UI Enhancements Design - Intentional Minimalism with Ethical Transparency

**Date**: 2026-02-07
**Status**: Approved
**Designer**: Claude (frontend-design skill)

---

## Vision

Elevate Ethic Companion's brutally minimal interface with:
- **Unforgettable Element**: Ethical transparency via ambient ESL indicators
- **Design Philosophy**: Intentional minimalism - refined, not generic
- **User Experience**: Functional enhancements that respect user autonomy

---

## Design Principles

### 1. Intentional Minimalism
- Brutal minimalism executed with precision and refinement
- Every element serves a purpose
- No decoration, only function and subtle elegance

### 2. Ethical Transparency as Design Feature
- ESL decisions visible through ambient, discoverable indicators
- Trust built through subtle visual communication
- Signature pulse animation when system protects values

### 3. Respect User Autonomy
- Empty states inform, never pressure (no aggressive CTAs)
- Animations are purposeful, not distracting
- Loading states manage expectations without manipulation

---

## Core Features

### 1. Empty States (Minimal & Informative)
**Component**: `components/ui/empty-state.tsx`

**Design**:
```tsx
<EmptyState
  icon={Target}           // 32px, neutral-300
  title="No goals yet"    // text-lg font-medium
  description="Goals help the system understand your priorities"  // text-sm text-[#525252]
/>
```

**Characteristics**:
- Icon: 32px, neutral-300 color
- Title: text-lg, font-medium, neutral-900
- Description: text-sm, neutral-600, single line
- No CTA buttons (respects autonomy)
- Centered layout with generous whitespace

**Pages**:
- Dashboard (no values/goals)
- Goals page (no goals)
- Values page (no values)
- Chat page (no history)
- Transparency page (no ESL decisions)

---

### 2. Skeleton Loaders (All Pages)
**Component**: `components/ui/skeleton.tsx` (enhanced)

**Design**:
```tsx
<Skeleton className="h-20 w-full" />
```

**Enhancements**:
- Base: `bg-[#F5F5F5]` with subtle shimmer effect
- Shimmer: White gradient overlay with CSS animation
- Staggered reveal: Items fade in with 50ms delays
- Matches actual content dimensions

**Implementation**:
```css
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
```

**Pages**:
- Dashboard: Stats cards, charts, recent items
- Goals: List of goal cards
- Values: List of value cards
- Chat: Message bubbles
- Transparency: Decision log rows

---

### 3. Drag & Drop (Goals + Values)
**Library**: `@dnd-kit/core` + `@dnd-kit/sortable`
**Component**: `components/drag-drop-list.tsx`

**Interaction Design**:
1. **Grab**: Entire card is draggable (click anywhere)
2. **Lift**: Item opacity: 50%, no shadow (minimal)
3. **Move**: Magnetic snap with physics-based easing
4. **Drop**: Spring animation to final position
5. **Save**: Auto-save order to backend

**Motion Curve**: `cubic-bezier(0.22, 0.61, 0.36, 1)` (magnetic easing)
**Duration**: 150ms (within design system constraint)

**Visual Feedback**:
- No drag handles (entire card draggable)
- No drop zones (items shift smoothly)
- Minimal: Only opacity change during drag

**Backend Requirements**:
- Add `position: number` field to `goals` and `user_values` tables
- Endpoint: `PATCH /api/goals/reorder` → `{ goalIds: string[] }`
- Endpoint: `PATCH /api/values/reorder` → `{ valueIds: string[] }`

---

### 4. ESL Ambient Indicators
**Component**: `components/ui/esl-indicator.tsx`
**Animation**: `components/animations/esl-pulse.tsx`

**Design**:
```tsx
<Card className="relative group">
  <ESLIndicator
    status="approved"  // approved | vetoed | modified
    reason="Protected: Respects quiet hours"
    className="absolute top-2 right-2"
  />
  <CardContent>...</CardContent>
</Card>
```

**Visual States**:
- **Default**: 8px neutral-300 dot, opacity: 0
- **Hover**: 16px dot with colored ring, opacity: 100
  - Approved: Green ring `rgba(5, 150, 105, 0.3)`
  - Vetoed: Red ring `rgba(220, 38, 38, 0.3)`
  - Modified: Blue ring `rgba(37, 99, 235, 0.3)`
- **Active Protection**: Signature pulse animation (150ms)

**Tooltip**:
- Background: `bg-[#171717]`
- Text: `text-white text-xs`
- Content: "ESL Decision: {reason}"

**Pulse Animation** (Signature interaction):
```css
@keyframes esl-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
}
```

**Trigger**: When ESL actively blocks/modifies action (real-time)

---

### 5. Status Indicators (Icon + Color + Text)
**Component**: `components/ui/status-indicator.tsx`

**Design**:
```tsx
<StatusIndicator
  type="esl-approved"
  message="Protected: Respects quiet hours"
/>
```

**Types**:
- **success**: CheckCircle + green
- **error**: XCircle + red
- **warning**: AlertTriangle + amber
- **info**: Info + blue
- **esl-approved**: Shield + green
- **esl-vetoed**: ShieldAlert + red
- **esl-modified**: ShieldCheck + blue

**Structure**:
```tsx
<div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-{color}/10">
  <Icon className="h-4 w-4 text-{color}" />
  <span className="text-sm font-medium text-{color}">
    {message}
  </span>
</div>
```

**Usage**:
- Form submissions (success/error feedback)
- ESL decisions (transparency dashboard)
- Connection status (data sources)

---

### 6. Focus Management
**Updates**: `components/ui/dialog.tsx`

**Behavior**:
1. Dialog opens → Close button auto-focused
2. Tab cycles through interactive elements
3. Esc always closes dialog
4. Focus returns to trigger element on close

**Keyboard Navigation**:
- **Tab/Shift+Tab**: Navigate elements
- **Enter**: Submit/activate
- **Esc**: Close dialogs
- **Space**: Grab draggable items
- **Arrow keys**: Navigate drag items

**Screen Reader**:
```tsx
<div
  role="status"
  aria-live="polite"
  aria-label="ESL decision: Approved"
/>
```

---

## Typography Update

### Current
- **Font**: Plus Jakarta Sans
- **Usage**: All text

### New
- **Font**: Geist (via next/font/google)
- **Rationale**:
  - Ultra-modern, technical precision
  - Matches Vercel aesthetic (design system inspiration)
  - More distinctive than Plus Jakarta Sans
  - Better rendering at small sizes

**Implementation**:
```tsx
// app/layout.tsx
import { GeistSans } from 'geist/font/sans'

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={GeistSans.className}>
      {children}
    </html>
  )
}
```

**Maintain**:
- Existing size scale (text-3xl, text-2xl, etc.)
- Existing weight scale (font-bold, font-semibold, etc.)
- Letter-spacing refinements for better rhythm

---

## Design System Updates

### Colors (Add to `lib/theme.ts`)
```typescript
export const theme = {
  // ... existing colors

  esl: {
    approved: 'rgba(5, 150, 105, 0.1)',    // Green tint
    vetoed: 'rgba(220, 38, 38, 0.1)',      // Red tint
    modified: 'rgba(37, 99, 235, 0.1)',    // Blue tint
    pulse: 'rgba(23, 23, 23, 0.05)',       // Neutral pulse
  },
}
```

### Motion (Add to `lib/theme.ts`)
```typescript
export const theme = {
  // ... existing

  motion: {
    spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',   // Elastic feel
    magnetic: 'cubic-bezier(0.22, 0.61, 0.36, 1)', // Smooth snap
  }
}
```

### CSS Animations (Add to globals.css)
```css
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes esl-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
}

.animate-shimmer {
  animation: shimmer 2s infinite;
}

.animate-esl-pulse {
  animation: esl-pulse 150ms ease-out;
}
```

---

## Component Structure

```
frontend/
├── components/
│   ├── ui/
│   │   ├── empty-state.tsx          # NEW: Minimal empty states
│   │   ├── status-indicator.tsx     # NEW: Icon + Color + Text
│   │   ├── esl-indicator.tsx        # NEW: Ambient ESL dot
│   │   ├── skeleton.tsx             # ENHANCED: Add shimmer
│   │   └── dialog.tsx               # ENHANCED: Focus management
│   ├── animations/
│   │   └── esl-pulse.tsx            # NEW: Signature pulse
│   └── drag-drop-list.tsx           # NEW: Sortable list wrapper
└── lib/
    └── theme.ts                      # ENHANCED: Add ESL colors, motion
```

---

## Implementation Plan

### Phase 1: Foundation (4-6 hours)
**Goal**: Update design system and install dependencies

**Tasks**:
1. Install Geist font: `npm install geist`
2. Update `app/layout.tsx` with Geist font
3. Update `lib/theme.ts` with ESL colors and motion curves
4. Add CSS keyframes to `app/globals.css`
5. Update `DESIGN_SYSTEM.md` with new patterns

**Acceptance**:
- [ ] Geist font renders across app
- [ ] ESL colors available in theme
- [ ] Animations work (test with simple div)

---

### Phase 2: Core Components (8-10 hours)
**Goal**: Build reusable components

**Tasks**:
1. Create `components/ui/empty-state.tsx`
   - Props: icon, title, description
   - Centered layout, minimal styling

2. Create `components/ui/status-indicator.tsx`
   - Props: type, message
   - Icon + color + text pattern

3. Create `components/ui/esl-indicator.tsx`
   - Props: status, reason
   - Dot with hover state and tooltip

4. Create `components/animations/esl-pulse.tsx`
   - Trigger pulse programmatically
   - 150ms duration

5. Update `components/ui/skeleton.tsx`
   - Add shimmer effect with gradient overlay
   - Maintain existing API

**Acceptance**:
- [ ] All components render correctly
- [ ] Storybook examples work (if using)
- [ ] TypeScript types complete

---

### Phase 3: Drag & Drop (10-12 hours)
**Goal**: Add reordering to Goals and Values

**Tasks**:
1. Install dependencies:
   ```bash
   npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities
   ```

2. Create `components/drag-drop-list.tsx`
   - Wrap `@dnd-kit` with custom styling
   - Magnetic snap animation
   - Keyboard support

3. Update `app/dashboard/goals/page.tsx`
   - Replace static list with DragDropList
   - Handle reorder events
   - Persist to backend

4. Update `app/dashboard/values/page.tsx`
   - Same as goals

5. Backend updates:
   - Add `position` column to `goals` table
   - Add `position` column to `user_values` table
   - Create `PATCH /api/goals/reorder` endpoint
   - Create `PATCH /api/values/reorder` endpoint

**Acceptance**:
- [ ] Goals can be reordered via drag
- [ ] Values can be reordered via drag
- [ ] Order persists on page reload
- [ ] Keyboard navigation works (Space to grab, Arrow to move)

---

### Phase 4: Integration (12-16 hours)
**Goal**: Apply components to all pages

**Tasks**:

**Dashboard (`app/dashboard/page.tsx`)**:
- Add skeleton loaders for stats, charts, recent items
- Add empty state when no goals/values exist
- Add ESL indicators to recent activity items

**Goals Page (`app/dashboard/goals/page.tsx`)**:
- Add skeleton loader while fetching
- Add empty state when no goals
- Add status indicators for CRUD operations
- ESL indicators on goal cards (if ESL influenced)

**Values Page (`app/dashboard/values/page.tsx`)**:
- Add skeleton loader while fetching
- Add empty state when no values
- Add status indicators for CRUD operations
- ESL indicators on value cards

**Chat Page (`app/dashboard/chat/page.tsx`)**:
- Add skeleton for message history
- Add empty state for new chat
- Add status indicators for errors
- ESL indicator when response modified

**Transparency Page (`app/dashboard/transparency/page.tsx`)**:
- Add skeleton for decision log
- Add empty state when no decisions
- Status indicators for each ESL decision type

**Dialogs**:
- Update all dialogs with focus management
- Auto-focus close button on open
- Esc to close

**Acceptance**:
- [ ] All pages have skeleton loaders
- [ ] All empty states display correctly
- [ ] Status indicators appear on actions
- [ ] ESL indicators visible where applicable
- [ ] Focus management works in all dialogs

---

### Phase 5: Polish (4-6 hours)
**Goal**: Refinements and testing

**Tasks**:
1. Staggered fade-in animations
   - Items appear with 50ms delays
   - Smooth reveal on page load

2. Keyboard navigation testing
   - Tab through all interactive elements
   - Test drag with keyboard
   - Verify dialog Esc behavior

3. Screen reader testing
   - Test with VoiceOver (macOS)
   - Verify aria-labels
   - Check role attributes

4. Performance optimization
   - Check bundle size impact
   - Optimize animations (GPU acceleration)
   - Lazy load heavy components

**Acceptance**:
- [ ] Animations smooth on low-end devices
- [ ] Keyboard navigation complete
- [ ] Screen reader announces correctly
- [ ] No performance regressions

---

## Testing Strategy

### Manual Testing
1. **Empty States**: Clear database, verify all pages show empty states
2. **Skeleton Loaders**: Throttle network, verify loaders appear
3. **Drag & Drop**: Reorder 10+ items, verify persistence
4. **ESL Indicators**: Trigger ESL decisions, verify indicators appear
5. **Status Indicators**: Submit forms, verify feedback
6. **Focus Management**: Tab through app, verify focus visible

### Automated Testing (Future)
```tsx
// Example: Empty state test
describe('EmptyState', () => {
  it('renders with icon, title, description', () => {
    render(<EmptyState icon={Target} title="No goals" description="Create your first goal" />)
    expect(screen.getByText('No goals')).toBeInTheDocument()
  })
})
```

---

## Accessibility Checklist

- [ ] All interactive elements keyboard accessible
- [ ] Focus states visible (2px ring, 2px offset)
- [ ] Screen reader labels on icon-only elements
- [ ] ARIA roles on status indicators (`role="status"`)
- [ ] Color not sole indicator (icon + color + text)
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Contrast ratios meet WCAG AAA (7:1)

---

## Performance Considerations

### Bundle Size
- **@dnd-kit**: ~15KB gzipped (acceptable)
- **Geist font**: Self-hosted via next/font (optimized)
- **Animations**: CSS-only (no JS runtime cost)

### Runtime Performance
- **Drag & Drop**: GPU-accelerated transforms
- **Skeleton Shimmer**: CSS animation (GPU)
- **ESL Pulse**: Triggered sparingly (low impact)

### Optimization
- Lazy load drag & drop on pages that need it
- Memoize empty states (static content)
- Debounce reorder API calls (300ms)

---

## Migration Path

### Backward Compatibility
- All existing components continue working
- New components are additive, not breaking
- Theme updates are extensions, not replacements

### Rollout Strategy
1. **Phase 1-2**: Design system updates (low risk)
2. **Phase 3**: Drag & drop (isolated feature)
3. **Phase 4**: Integration (gradual page-by-page)
4. **Phase 5**: Polish (refinement only)

### Rollback Plan
- Each phase can be reverted independently
- Theme updates backward compatible
- New components can be removed without breaking existing UI

---

## Success Metrics

### Qualitative
- [ ] UI feels more polished and intentional
- [ ] ESL transparency enhances trust
- [ ] Drag & drop improves goal/value prioritization
- [ ] Loading states reduce perceived wait time

### Quantitative
- [ ] Zero accessibility regressions
- [ ] No increase in page load time (>100ms)
- [ ] No increase in bundle size (>50KB)
- [ ] All existing tests pass

---

## Future Enhancements (Post-MVP)

1. **Staggered Animations**: Page-level orchestrated reveals
2. **Drag Hints**: Subtle visual cue on first visit
3. **ESL Dashboard**: Dedicated view for all ESL decisions
4. **Custom Cursors**: Branded cursor states (optional)
5. **Sound Design**: Subtle audio feedback for ESL pulse (optional)

---

## References

- **Design System**: `/DESIGN_SYSTEM.md`
- **Frontend Design Skill**: `/.claude/skills/frontend-design/SKILL.md`
- **Accessibility**: WCAG 2.2 Level AAA
- **Inspiration**: Linear, Vercel, Apple (minimal aesthetics)
- **Library**: @dnd-kit documentation

---

## Appendix: Code Snippets

### EmptyState Component
```tsx
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  className?: string
}

export function EmptyState({ icon: Icon, title, description, className }: EmptyStateProps) {
  return (
    <div className={cn(
      "flex flex-col items-center justify-center py-12 px-4 text-center",
      className
    )}>
      <Icon className="h-8 w-8 text-[#D4D4D4] mb-4" />
      <h3 className="text-lg font-medium text-[#171717] mb-2">{title}</h3>
      <p className="text-sm text-[#525252] max-w-sm">{description}</p>
    </div>
  )
}
```

### StatusIndicator Component
```tsx
import { CheckCircle, XCircle, Shield, ShieldAlert, ShieldCheck, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

type StatusType = 'success' | 'error' | 'warning' | 'info' | 'esl-approved' | 'esl-vetoed' | 'esl-modified'

interface StatusIndicatorProps {
  type: StatusType
  message: string
  className?: string
}

const config: Record<StatusType, { icon: any; color: string; bg: string }> = {
  success: { icon: CheckCircle, color: 'text-[#059669]', bg: 'bg-[#059669]/10' },
  error: { icon: XCircle, color: 'text-[#DC2626]', bg: 'bg-[#DC2626]/10' },
  warning: { icon: AlertTriangle, color: 'text-[#D97706]', bg: 'bg-[#D97706]/10' },
  info: { icon: Info, color: 'text-[#2563EB]', bg: 'bg-[#2563EB]/10' },
  'esl-approved': { icon: Shield, color: 'text-[#059669]', bg: 'bg-[#059669]/10' },
  'esl-vetoed': { icon: ShieldAlert, color: 'text-[#DC2626]', bg: 'bg-[#DC2626]/10' },
  'esl-modified': { icon: ShieldCheck, color: 'text-[#2563EB]', bg: 'bg-[#2563EB]/10' },
}

export function StatusIndicator({ type, message, className }: StatusIndicatorProps) {
  const { icon: Icon, color, bg } = config[type]

  return (
    <div className={cn("flex items-center gap-2 px-3 py-2 rounded-lg", bg, className)}>
      <Icon className={cn("h-4 w-4", color)} />
      <span className={cn("text-sm font-medium", color)}>{message}</span>
    </div>
  )
}
```

### ESLIndicator Component
```tsx
'use client'

import { useState } from 'react'
import { Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface ESLIndicatorProps {
  status: 'approved' | 'vetoed' | 'modified'
  reason: string
  className?: string
  pulse?: boolean
}

const statusColors = {
  approved: 'ring-[#059669]/30 bg-[#059669]/10',
  vetoed: 'ring-[#DC2626]/30 bg-[#DC2626]/10',
  modified: 'ring-[#2563EB]/30 bg-[#2563EB]/10',
}

export function ESLIndicator({ status, reason, className, pulse = false }: ESLIndicatorProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "h-2 w-2 rounded-full bg-[#D4D4D4] transition-all duration-150",
              "group-hover:h-4 group-hover:w-4 group-hover:ring-2",
              statusColors[status],
              pulse && "animate-esl-pulse",
              className
            )}
            aria-label={`ESL decision: ${status}`}
          />
        </TooltipTrigger>
        <TooltipContent side="left" className="bg-[#171717] text-white border-[#404040] rounded-lg">
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

---

**End of Design Document**

*Ready for implementation. See Implementation Plan for phased rollout strategy.*
