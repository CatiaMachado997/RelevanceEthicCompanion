# Black & White Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply a clean black-and-white theme to Ethic Companion — pure white backgrounds, near-black text, black accents and buttons. Monochrome throughout. ESL status colors (green/red/amber) kept since they are functional.

**Architecture:** Update CSS variables in `globals.css`, update `lib/theme.ts` flat tokens, update sidebar, top-bar, layout, and all dashboard pages to replace warm/coloured inline styles with B&W values.

**Tech Stack:** Next.js App Router, React 19, Tailwind v4 CSS variables, lucide-react icons.

---

## Color Mapping

| Token | New Value | Purpose |
|-------|-----------|---------|
| `pageBg` | `#ffffff` | Page background |
| `sidebarBg` | `#fafafa` | Sidebar background |
| `surface` | `#ffffff` | Card/surface background |
| `surfaceBorder` | `rgba(0,0,0,0.08)` | Card border |
| `textPrimary` | `#0a0a0a` | Primary text |
| `textSecondary` | `#6b6b6b` | Secondary/label text |
| `textMuted` | `#9e9e9e` | Placeholder/muted text |
| `accent` | `#000000` | Primary action (black buttons) |
| `accentLight` | `rgba(0,0,0,0.05)` | Hover/active tint |
| Card shadow | `0 1px 3px rgba(0,0,0,0.08)` | Subtle lift |
| Hover bg | `rgba(0,0,0,0.04)` | Item hover |

ESL colors unchanged: `#4A7C59` approved, `#B04A3A` vetoed, `#9B7A3D` modified.

---

## Task 1: Update CSS variables (`globals.css`)

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: Replace file content**

```css
@import "tailwindcss";
@plugin "tailwindcss-animate";

@custom-variant dark (&:is(.dark *));

:root {
  --primary: 0 0% 4%;                 /* #0a0a0a near-black */
  --primary-foreground: 0 0% 100%;    /* white */

  --background: 0 0% 100%;            /* #ffffff pure white */
  --foreground: 0 0% 4%;              /* #0a0a0a near-black */
  --card: 0 0% 100%;                  /* #ffffff */
  --card-foreground: 0 0% 4%;
  --popover: 0 0% 100%;
  --popover-foreground: 0 0% 4%;
  --secondary: 0 0% 96%;              /* #f5f5f5 light gray */
  --secondary-foreground: 0 0% 4%;
  --muted: 0 0% 96%;
  --muted-foreground: 0 0% 42%;       /* #6b6b6b */
  --accent: 0 0% 96%;
  --accent-foreground: 0 0% 4%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 100%;
  --border: 0 0% 90%;                 /* #e5e5e5 */
  --input: 0 0% 96%;                  /* #f5f5f5 */
  --ring: 0 0% 4%;

  --radius: 0.75rem;

  --sidebar: 0 0% 98%;                /* #fafafa */
  --sidebar-foreground: 0 0% 42%;
  --sidebar-primary: 0 0% 4%;
  --sidebar-primary-foreground: 0 0% 100%;
  --sidebar-accent: 0 0% 94%;
  --sidebar-accent-foreground: 0 0% 4%;
  --sidebar-border: 0 0% 90%;
  --sidebar-ring: 0 0% 4%;
}

@theme inline {
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));
  --color-popover: hsl(var(--popover));
  --color-popover-foreground: hsl(var(--popover-foreground));
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-secondary: hsl(var(--secondary));
  --color-secondary-foreground: hsl(var(--secondary-foreground));
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-ring: hsl(var(--ring));
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --color-sidebar: hsl(var(--sidebar));
  --color-sidebar-foreground: hsl(var(--sidebar-foreground));
  --color-sidebar-primary: hsl(var(--sidebar-primary));
  --color-sidebar-primary-foreground: hsl(var(--sidebar-primary-foreground));
  --color-sidebar-accent: hsl(var(--sidebar-accent));
  --color-sidebar-accent-foreground: hsl(var(--sidebar-accent-foreground));
  --color-sidebar-border: hsl(var(--sidebar-border));
  --color-sidebar-ring: hsl(var(--sidebar-ring));
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
}

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
  will-change: transform;
}

.animate-esl-pulse {
  animation: esl-pulse 150ms ease-out;
  will-change: transform, opacity;
}

@media (prefers-reduced-motion: reduce) {
  .animate-shimmer,
  .animate-esl-pulse {
    animation: none !important;
  }
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```
Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: switch to black and white CSS variables"
```

---

## Task 2: Update `lib/theme.ts` flat tokens

**Files:**
- Modify: `frontend/lib/theme.ts`

**Step 1: Replace file content**

```ts
// Black & White Design System — Ethic Companion

export const colors = {
  // Backgrounds
  pageBg: '#ffffff',
  sidebarBg: '#fafafa',
  surface: '#ffffff',
  surfaceBorder: 'rgba(0,0,0,0.08)',

  // Text
  textPrimary: '#0a0a0a',
  textSecondary: '#6b6b6b',
  textMuted: '#9e9e9e',

  // Accent (black)
  accent: '#000000',
  accentLight: 'rgba(0,0,0,0.05)',
  accentBorder: 'rgba(0,0,0,0.15)',

  // ESL status (unchanged — functional colors)
  eslApproved: '#4A7C59',
  eslApprovedBg: 'rgba(74,124,89,0.10)',
  eslVetoed: '#B04A3A',
  eslVetoedBg: 'rgba(176,74,58,0.10)',
  eslModified: '#9B7A3D',
  eslModifiedBg: 'rgba(155,122,61,0.10)',

  // Value type badges — monochrome
  badgeBoundary: '#0a0a0a',
  badgeBoundaryBg: 'rgba(0,0,0,0.06)',
  badgePreference: '#4A7C59',
  badgePreferenceBg: 'rgba(74,124,89,0.10)',
  badgeTopicFilter: '#9B7A3D',
  badgeTopicFilterBg: 'rgba(155,122,61,0.10)',
  badgeTimeWindow: '#5B7FA6',
  badgeTimeWindowBg: 'rgba(91,127,166,0.10)',

  // Goal status badges
  statusActive: '#4A7C59',
  statusActiveBg: 'rgba(74,124,89,0.10)',
  statusCompleted: '#0a0a0a',
  statusCompletedBg: 'rgba(0,0,0,0.08)',
  statusPaused: '#9B7A3D',
  statusPausedBg: 'rgba(155,122,61,0.10)',
  statusArchived: '#9e9e9e',
  statusArchivedBg: 'rgba(0,0,0,0.05)',
} as const

export const shadows = {
  card: '0 1px 3px rgba(0,0,0,0.08)',
  cardHover: '0 4px 12px rgba(0,0,0,0.12)',
  toggle: '0 1px 3px rgba(0,0,0,0.12)',
} as const

export const radius = {
  card: '16px',
  button: '20px',
  badge: '6px',
  pill: '9999px',
} as const

export const transition = {
  sidebar: 'all 200ms ease',
  hover: 'all 150ms ease',
} as const
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 3: Commit**

```bash
git add frontend/lib/theme.ts
git commit -m "feat: update theme tokens to black and white palette"
```

---

## Task 3: Update sidebar

**Files:**
- Modify: `frontend/components/sidebar.tsx`

**Step 1: Replace file content**

```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  MessageSquare,
  Heart,
  Target,
  Eye,
  Shield,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard/values", label: "Values", icon: Heart },
  { href: "/dashboard/goals", label: "Goals", icon: Target },
  { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
]

export function SidebarNav() {
  const pathname = usePathname()
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside
      className="flex flex-col h-screen w-16 shrink-0 border-r"
      style={{ background: "#fafafa", borderColor: "rgba(0,0,0,0.08)" }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-center h-14 shrink-0 border-b"
        style={{ borderColor: "rgba(0,0,0,0.08)" }}
      >
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold"
          style={{
            background: "#000000",
            color: "#ffffff",
          }}
        >
          EC
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(href, exact)
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={cn(
                "w-11 h-11 rounded-xl flex items-center justify-center transition-colors duration-150",
                active ? "" : "hover:bg-black/5"
              )}
              style={{
                background: active ? "rgba(0,0,0,0.08)" : undefined,
                color: active ? "#000000" : "#9e9e9e",
              }}
            >
              <Icon size={18} />
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div
        className="flex flex-col items-center gap-3 pb-4 border-t pt-3"
        style={{ borderColor: "rgba(0,0,0,0.08)" }}
      >
        <button
          title="Security"
          className="w-11 h-11 rounded-xl flex items-center justify-center hover:bg-black/5 transition-colors"
          style={{ color: "#9e9e9e" }}
        >
          <Shield size={18} />
        </button>
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold"
          style={{ background: "#0a0a0a", color: "#ffffff" }}
        >
          U
        </div>
      </div>
    </aside>
  )
}

export function MobileSidebarTrigger() {
  return null
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 3: Commit**

```bash
git add frontend/components/sidebar.tsx
git commit -m "feat: update sidebar to black and white theme"
```

---

## Task 4: Update top-bar

**Files:**
- Modify: `frontend/components/top-bar.tsx`

**Step 1: Replace file content**

```tsx
"use client"

import { usePathname } from "next/navigation"

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Overview of your activity" },
  "/dashboard/chat": { title: "Chat", subtitle: "Message your companion" },
  "/dashboard/values": { title: "Values", subtitle: "Manage your personal values" },
  "/dashboard/goals": { title: "Goals", subtitle: "Track your active goals" },
  "/dashboard/transparency": { title: "Transparency", subtitle: "ESL audit and decisions" },
}

export function TopBar() {
  const pathname = usePathname()
  const meta = PAGE_META[pathname] ?? { title: "Ethic Companion", subtitle: "" }

  return (
    <header
      className="h-[72px] flex items-center px-8 shrink-0 border-b"
      style={{
        background: "#ffffff",
        borderColor: "rgba(0,0,0,0.08)",
      }}
    >
      <div>
        <h1
          className="font-semibold text-xl leading-7"
          style={{ color: "#0a0a0a" }}
        >
          {meta.title}
        </h1>
        {meta.subtitle && (
          <p className="text-xs mt-0.5" style={{ color: "#9e9e9e" }}>
            {meta.subtitle}
          </p>
        )}
      </div>
    </header>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 3: Commit**

```bash
git add frontend/components/top-bar.tsx
git commit -m "feat: update top-bar to black and white theme"
```

---

## Task 5: Update dashboard layout

**Files:**
- Modify: `frontend/app/dashboard/layout.tsx`

**Step 1: Replace file content**

```tsx
import { SidebarNav } from "@/components/sidebar"
import { TopBar } from "@/components/top-bar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex h-screen" style={{ background: "#ffffff" }}>
      <SidebarNav />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1100px] mx-auto px-8 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
```

**Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 3: Commit**

```bash
git add frontend/app/dashboard/layout.tsx
git commit -m "feat: update dashboard layout to black and white"
```

---

## Task 6: Update dashboard page

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

**Step 1: Read the full file**

Read `frontend/app/dashboard/page.tsx`.

**Step 2: Update CARD_STYLE constant**

Replace:
```ts
const CARD_STYLE = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.04)',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
}
```
With:
```ts
const CARD_STYLE = {
  background: '#ffffff',
  border: '1px solid rgba(0,0,0,0.08)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
}
```

**Step 3: Replace all warm color references**

Apply these replacements:
- `'#1C1917'` → `'#0a0a0a'`
- `'#78716C'` → `'#6b6b6b'`
- `'#A8A29E'` → `'#9e9e9e'`
- `'#C2714F'` → `'#000000'` (accent becomes black)
- `rgba(194,113,79,0.10)` → `rgba(0,0,0,0.06)` (accent light bg)
- `'#FAF8F5'` → `'#ffffff'`
- `'#4A7C59'` → keep (ESL approved color)

**Step 4: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 5: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: update dashboard page to black and white theme"
```

---

## Task 7: Update chat page

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`

**Step 1: Read the full file**

Read `frontend/app/dashboard/chat/page.tsx`.

**Step 2: Apply replacements**

- User bubble: `background: 'rgba(194,113,79,0.12)'` → `background: 'rgba(0,0,0,0.05)'`
- User bubble text: `color: '#1C1917'` → `color: '#0a0a0a'`
- AI bubble background: `'#FAF8F5'` → `'#f9f9f9'`
- AI bubble text: `color: '#1C1917'` → `color: '#0a0a0a'`
- AI bubble border (neutral): `'#E5E5E5'` → `'#e5e5e5'` (keep)
- Chat container background: `'#FFFFFF'` → `'#ffffff'`
- Input bar background: `'#FAF8F5'` → `'#f5f5f5'`
- Textarea: `background: '#FFFFFF'` → `'#ffffff'`, text `'#1C1917'` → `'#0a0a0a'`
- Example prompt buttons border: `rgba(0,0,0,0.08)` → keep; color `'#78716C'` → `'#6b6b6b'`
- "Ask your companion" text: `'#A8A29E'` → `'#9e9e9e'`
- Loading dots: `'#A8A29E'` → `'#9e9e9e'`
- Loading bubble: `'#FAF8F5'` → `'#f5f5f5'`
- Send button: `background: '#C2714F'` → `background: '#000000'`
- ESLTag text: `'#78716C'` → `'#6b6b6b'`

**Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add frontend/app/dashboard/chat/page.tsx
git commit -m "feat: update chat page to black and white theme"
```

---

## Task 8: Update values page

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`

**Step 1: Read the full file**

Read `frontend/app/dashboard/values/page.tsx`.

**Step 2: Apply color replacements**

- `'#1C1917'` → `'#0a0a0a'`
- `'#78716C'` → `'#6b6b6b'`
- `'#A8A29E'` → `'#9e9e9e'`
- `'#C2714F'` → `'#000000'`
- `rgba(194,113,79,...)` → `rgba(0,0,0,...)`  (same opacity)
- `'#FFFFFF'` / `'#FAF8F5'` / `'#F5F5F5'` → `'#ffffff'` / `'#f9f9f9'` / `'#f5f5f5'`
- `rgba(0,0,0,0.04)` border → `rgba(0,0,0,0.08)` (slightly more visible on white)
- Badge/ESL colors → keep unchanged

**Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add frontend/app/dashboard/values/page.tsx
git commit -m "feat: update values page to black and white theme"
```

---

## Task 9: Update goals page

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

**Step 1: Read the full file**

Read `frontend/app/dashboard/goals/page.tsx`.

**Step 2: Apply same replacements as Task 8**

- `'#1C1917'` → `'#0a0a0a'`
- `'#78716C'` → `'#6b6b6b'`
- `'#A8A29E'` → `'#9e9e9e'`
- `'#C2714F'` → `'#000000'`
- `rgba(194,113,79,...)` → `rgba(0,0,0,...)` (same opacity)
- Warm surface colors → white/near-white equivalents
- Badge/ESL/status colors → keep unchanged

**Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

**Step 4: Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx
git commit -m "feat: update goals page to black and white theme"
```

---

## Task 10: Final build and verification

**Step 1: Run full production build**

```bash
cd frontend && npm run build
```

Expected: `✓ Compiled successfully` with 0 type errors.

**Step 2: Commit if any cleanup needed**

```bash
git add -A
git commit -m "feat: complete black and white theme implementation"
```
