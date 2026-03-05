# Ethic Companion Design System

**Version**: 1.0
**Last Updated**: 2026-02-07
**Framework**: Next.js 16 + React 19 + Tailwind CSS v4

---

## 🎨 Design Principles

### 1. **Minimal & Functional** (Primary Goal)
- Flat design - NO gradients, heavy shadows, or scale effects
- Clean borders and subtle transitions
- High contrast text for readability
- Focus on content, not decoration

### 2. **Accessible First**
- WCAG AAA contrast ratios (7:1 minimum)
- Visible focus states on all interactive elements
- Keyboard navigation support
- Screen reader compatible (Radix UI primitives)

### 3. **Consistent & Predictable**
- 4px spacing grid system
- Standardized component sizes (40px height for inputs/buttons)
- Unified animation timing (150ms)
- Clear visual hierarchy

---

## 📏 Design Tokens

### Color Palette

**Neutrals** (Black/White/Gray)
```tsx
neutral-50:  #FAFAFA  // Background
neutral-100: #F5F5F5  // Subtle background
neutral-200: #E5E5E5  // Borders
neutral-300: #D4D4D4  // Subtle borders
neutral-400: #A3A3A3  // Disabled text
neutral-500: #737373  // Muted text
neutral-600: #525252  // Secondary text
neutral-700: #404040  // Body text
neutral-800: #262626  // Headings
neutral-900: #171717  // Primary text
```

**Accent**
```tsx
Primary: #171717 (Black) - Used for primary actions
Hover:   #0A0A0A (Darker black)
```

**Semantic Colors**
```tsx
Success: #059669 (Green-600)
Warning: #D97706 (Amber-600)
Error:   #DC2626 (Red-600)
Info:    #2563EB (Blue-600)
```

**Usage Rules:**
- ✅ Use neutrals for 95% of UI
- ✅ Use semantic colors ONLY for status/feedback
- ❌ NO custom colors outside this palette
- ❌ NO gradients

---

### Typography

**Font Family**: Plus Jakarta Sans (400, 500, 600, 700, 800)

**Type Scale**
```tsx
h1:    text-3xl font-bold tracking-tight      // 30px, Page titles
h2:    text-2xl font-semibold tracking-tight  // 24px, Section titles
h3:    text-xl font-semibold                  // 20px, Subsections
h4:    text-lg font-medium                    // 18px, Card titles
body:  text-sm                                // 14px, Body text
small: text-xs                                // 12px, Captions
```

**Rules:**
- ✅ Use semibold/bold for hierarchy, not size
- ✅ Limit to 3 font sizes per page
- ❌ NO italic (use color/weight for emphasis)
- ❌ NO font sizes outside scale

---

### Spacing System (4px Grid)

```tsx
xs:  0.25rem  //  4px - Tight spacing
sm:  0.5rem   //  8px - Icon gaps
md:  1rem     // 16px - Standard (most common)
lg:  1.5rem   // 24px - Section spacing
xl:  2rem     // 32px - Large gaps
2xl: 3rem     // 48px - Page sections
```

**Rules:**
- ✅ All spacing must be multiples of 4px
- ✅ Use `gap-4` (16px) as default
- ✅ Use `p-6` (24px) for card padding
- ❌ NO arbitrary values (no `p-[17px]`)

---

### Border Radius

```tsx
none: 0         // Sharp corners
sm:   0.25rem   // 4px
md:   0.375rem  // 6px
lg:   0.5rem    // 8px - Standard (most common)
xl:   0.75rem   // 12px - Large cards
```

**Rules:**
- ✅ Use `rounded-lg` as default (8px)
- ✅ Use `rounded-xl` for large cards only
- ❌ NO fully rounded (rounded-full) except avatars

---

### Shadows (Minimal)

```tsx
none: none                                    // Flat (preferred)
xs:   0 1px 2px 0 rgb(0 0 0 / 0.05)          // Barely visible
sm:   0 1px 3px 0 rgb(0 0 0 / 0.1)           // Subtle elevation
md:   0 4px 6px -1px rgb(0 0 0 / 0.1)        // Cards on hover
lg:   0 10px 15px -3px rgb(0 0 0 / 0.1)      // Modals/dialogs
```

**Rules:**
- ✅ Default to NO shadow (flat design)
- ✅ Use shadow-sm for subtle depth only
- ✅ Use shadow-md ONLY on hover states
- ❌ NO heavy shadows (shadow-xl, shadow-2xl)

---

### Transitions

```tsx
fast: 100ms cubic-bezier(0.4, 0, 0.2, 1)  // Quick feedback
base: 150ms cubic-bezier(0.4, 0, 0.2, 1)  // Standard (default)
slow: 200ms cubic-bezier(0.4, 0, 0.2, 1)  // Deliberate animations
```

**Rules:**
- ✅ Use `duration-150` as default
- ✅ Transition colors only: `transition-colors`
- ❌ NO slow transitions (>200ms)
- ❌ NO transform/scale effects

---

## 🧩 Component Library

### Button Variants

**Primary** - High contrast, primary actions
```tsx
<Button className="bg-[#171717] hover:bg-[#0A0A0A] text-white">
  Primary Action
</Button>
```

**Secondary** - Low emphasis
```tsx
<Button variant="secondary" className="bg-[#F5F5F5] hover:bg-[#E5E5E5] text-[#171717]">
  Secondary Action
</Button>
```

**Ghost** - Minimal, inline actions
```tsx
<Button variant="ghost" className="hover:bg-[#F5F5F5] text-[#525252]">
  Cancel
</Button>
```

**Sizes**
```tsx
default: h-10 px-4  // 40px height (standard)
sm:      h-9 px-3   // 36px height (compact)
lg:      h-11 px-6  // 44px height (prominent)
icon:    size-10    // Square icon button
```

**Rules:**
- ✅ Max 2 button variants per section
- ✅ Primary buttons for ONE action per view
- ❌ NO gradient backgrounds
- ❌ NO scale hover effects

---

### Card Component

**Standard Card**
```tsx
<Card className="bg-white border border-[#E5E5E5] rounded-lg p-6">
  <CardHeader>
    <CardTitle className="text-lg font-medium">Title</CardTitle>
    <CardDescription className="text-sm text-[#525252]">
      Description text
    </CardDescription>
  </CardHeader>
  <CardContent>
    Content here
  </CardContent>
</Card>
```

**Hover State** (Optional)
```tsx
className="hover:border-[#D4D4D4] transition-colors duration-150"
```

**Rules:**
- ✅ Flat design - border only, no shadow by default
- ✅ Use `p-6` for card padding
- ✅ Hover: border color change ONLY
- ❌ NO shadows on default state
- ❌ NO scale effects

---

### Input Fields

**Standard Input**
```tsx
<Input
  className="h-10 border-[#E5E5E5] focus:border-[#171717] focus:ring-2 focus:ring-[#171717]"
  placeholder="Enter text..."
/>
```

**Rules:**
- ✅ Always 40px height (`h-10`)
- ✅ Clear focus state with 2px ring
- ✅ Placeholder text: `#A3A3A3`
- ❌ NO shadows on inputs

---

### Icon Usage (lucide-react)

**Sizing**
```tsx
h-4 w-4  // 16px - Standard (use this 95% of time)
h-5 w-5  // 20px - Larger buttons
h-6 w-6  // 24px - Headers/emphasis
```

**Import Pattern**
```tsx
import { Search, X, Settings } from "lucide-react"

<Search className="h-4 w-4 text-[#525252]" />
```

**Rules:**
- ✅ Use `h-4 w-4` as default
- ✅ Align icons with text baseline
- ❌ NO shadows on icons
- ❌ NO animations unless meaningful (loading spinners ok)

---

## 🎯 Layout Patterns

### Sidebar Layout (80px Icon Sidebar)

```tsx
<div className="flex h-screen bg-[#FAFAFA]">
  {/* Icon Sidebar - 80px */}
  <IconSidebar />

  {/* Main Content */}
  <div className="flex flex-1 min-w-0 overflow-hidden">
    {children}
  </div>
</div>
```

**Sidebar Specs:**
- Width: `w-20` (80px)
- Icon size: `h-4 w-4` (16px)
- Spacing: `space-y-0.5` (2px between items)
- Active state: `bg-[#171717] text-white`
- Hover: `hover:bg-[#F5F5F5]`

---

### Page Layout

```tsx
<main className="flex-1 overflow-y-auto p-6 bg-[#FAFAFA]">
  <div className="max-w-7xl mx-auto space-y-6">
    {/* Page content */}
  </div>
</main>
```

**Rules:**
- ✅ Max width: `max-w-7xl` (1280px)
- ✅ Page padding: `p-6` (24px)
- ✅ Section spacing: `space-y-6`
- ✅ Background: `bg-[#FAFAFA]`

---

### Grid Layouts

**Responsive Grid**
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {/* Grid items */}
</div>
```

**Common Patterns:**
- 1 column mobile → 2 columns tablet → 4 columns desktop
- Gap: `gap-4` (16px) or `gap-6` (24px)
- Use CSS Grid over Flexbox for equal-width columns

---

## ♿ Accessibility Rules

### Focus States (REQUIRED)

```tsx
// Always include focus states
className="focus:outline-none focus:ring-2 focus:ring-[#171717] focus:ring-offset-2"
```

**Rules:**
- ✅ EVERY interactive element needs visible focus
- ✅ 2px ring, 2px offset
- ✅ Dark ring (#171717) on light backgrounds
- ❌ NEVER remove outline without replacement

---

### Keyboard Navigation

- ✅ All interactive elements accessible via Tab
- ✅ Dialog/Modal: Esc to close
- ✅ Dropdown: Arrow keys for navigation
- ✅ Use Radix UI primitives (built-in keyboard support)

---

### Screen Readers

```tsx
// Use aria-label for icon-only buttons
<button aria-label="Close dialog">
  <X className="h-4 w-4" />
</button>

// Use aria-describedby for hints
<Input aria-describedby="email-hint" />
<p id="email-hint" className="text-xs text-[#A3A3A3]">
  We'll never share your email
</p>
```

---

## 🚫 Anti-Patterns (Do NOT Use)

### ❌ Gradients
```tsx
// ❌ WRONG
className="bg-gradient-to-r from-blue-500 to-purple-600"

// ✅ CORRECT
className="bg-[#171717]"
```

### ❌ Heavy Shadows
```tsx
// ❌ WRONG
className="shadow-2xl"

// ✅ CORRECT
className="shadow-sm" // or no shadow
```

### ❌ Scale/Transform Effects
```tsx
// ❌ WRONG
className="hover:scale-110 hover:-translate-y-2"

// ✅ CORRECT
className="hover:bg-[#E5E5E5] transition-colors"
```

### ❌ Slow Transitions
```tsx
// ❌ WRONG
className="duration-500"

// ✅ CORRECT
className="duration-150"
```

### ❌ Arbitrary Values
```tsx
// ❌ WRONG
className="p-[17px] rounded-[13px]"

// ✅ CORRECT
className="p-4 rounded-lg" // Use spacing scale
```

### ❌ Custom Colors
```tsx
// ❌ WRONG
className="bg-[#8B7355] text-[#C9A961]"

// ✅ CORRECT
className="bg-[#171717] text-white" // Use token palette
```

---

## 📱 Responsive Design

### Breakpoints (Tailwind Defaults)

```tsx
sm:  640px   // Small tablets
md:  768px   // Tablets
lg:  1024px  // Laptops
xl:  1280px  // Desktops
2xl: 1536px  // Large screens
```

### Mobile-First Approach

```tsx
// Base = Mobile
<div className="p-4 md:p-6 lg:p-8">
  // 16px mobile → 24px tablet → 32px desktop
</div>

<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
  // 1 col mobile → 2 cols tablet → 3 cols desktop
</div>
```

---

## 🔧 Utility Functions

### `cn()` - Class Name Merger

Located: `/lib/utils.ts`

```tsx
import { cn } from "@/lib/utils"

// Merge Tailwind classes without conflicts
<div className={cn(
  "bg-white border",           // Base styles
  isActive && "border-[#171717]", // Conditional
  className                     // Props
)} />
```

**Rules:**
- ✅ Use for conditional styles
- ✅ Handles Tailwind conflicts (last class wins)
- ✅ Accepts: strings, arrays, objects

---

## 📦 Component File Structure

```tsx
// Standard component pattern
import * as React from "react"
import { cn } from "@/lib/utils"

interface ComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary"
  size?: "sm" | "md" | "lg"
}

const Component = React.forwardRef<HTMLDivElement, ComponentProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          // Base styles
          "border rounded-lg transition-colors duration-150",
          // Variant styles
          variant === "default" && "bg-white border-[#E5E5E5]",
          variant === "secondary" && "bg-[#F5F5F5] border-[#E5E5E5]",
          // Size styles
          size === "sm" && "p-3",
          size === "md" && "p-4",
          size === "lg" && "p-6",
          // Allow overrides
          className
        )}
        {...props}
      />
    )
  }
)
Component.displayName = "Component"

export { Component }
```

---

## ✅ Design Checklist

Before shipping any component:

- [ ] Uses only token colors (no arbitrary hex values)
- [ ] Follows 4px spacing grid
- [ ] Has visible focus states (2px ring)
- [ ] No gradients or heavy shadows
- [ ] Transitions are 150ms or faster
- [ ] Text contrast is WCAG AAA (7:1)
- [ ] Icons are h-4 w-4 (16px)
- [ ] No scale/transform hover effects
- [ ] Works on mobile (responsive)
- [ ] Keyboard accessible
- [ ] Screen reader tested

---

## 🎓 Best Practices from Modern Apps

### Linear-Style Patterns
- Ultra-flat design, minimal shadows
- Black and white primary colors
- Fast, subtle transitions
- Clear typography hierarchy

### Vercel-Style Patterns
- Clean borders, no shadows
- Monochrome color scheme
- High contrast text
- Generous whitespace

### Apple-Style Patterns
- Subtle rounded corners (8px)
- Fast, smooth animations (150ms)
- Focus on content
- Minimalist aesthetic

---

## 📚 References

- **Component Library**: Radix UI (accessibility primitives)
- **Styling**: Tailwind CSS v4
- **Icons**: lucide-react
- **Animations**: Framer Motion (sparingly)
- **Inspiration**: Linear, Vercel, Apple

---

**Remember**: Minimal, functional, accessible. Every pixel should have a purpose.
