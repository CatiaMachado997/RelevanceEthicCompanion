# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the Dashboard, Chat, Values, and Goals pages using the Warm Sand design system — clean minimal meets warm human.

**Architecture:** Replace the fixed 80px icon sidebar with a new collapsible sidebar (240px expanded / 64px collapsed). Move `<TopHeader />` out of individual pages into the shared layout. Restyle all four core pages using new design tokens. All existing API calls are preserved unchanged.

**Tech Stack:** Next.js App Router, React 19, Tailwind CSS v4, Geist Sans, Lucide icons, Framer Motion, shadcn/ui components.

**Design reference:** `docs/plans/2026-03-12-frontend-redesign-design.md`

---

## Task 1: Update Design Tokens

**Files:**
- Modify: `frontend/lib/theme.ts`

**Step 1: Replace the color tokens and spacing**

Replace the full contents of `frontend/lib/theme.ts` with:

```typescript
// Warm Sand Design System — Ethic Companion

export const colors = {
  // Backgrounds
  pageBg: '#FAF8F5',
  sidebarBg: '#F2EDE8',
  surface: '#FFFFFF',
  surfaceBorder: 'rgba(0,0,0,0.04)',

  // Text
  textPrimary: '#1C1917',
  textSecondary: '#78716C',
  textMuted: '#A8A29E',

  // Accent (terracotta)
  accent: '#C2714F',
  accentLight: 'rgba(194,113,79,0.10)',
  accentBorder: 'rgba(194,113,79,0.30)',

  // ESL status
  eslApproved: '#4A7C59',
  eslApprovedBg: 'rgba(74,124,89,0.10)',
  eslVetoed: '#B04A3A',
  eslVetoedBg: 'rgba(176,74,58,0.10)',
  eslModified: '#9B7A3D',
  eslModifiedBg: 'rgba(155,122,61,0.10)',

  // Value type badges
  badgeBoundary: '#C2714F',
  badgeBoundaryBg: 'rgba(194,113,79,0.10)',
  badgePreference: '#4A7C59',
  badgePreferenceBg: 'rgba(74,124,89,0.10)',
  badgeTopicFilter: '#9B7A3D',
  badgeTopicFilterBg: 'rgba(155,122,61,0.10)',
  badgeTimeWindow: '#5B7FA6',
  badgeTimeWindowBg: 'rgba(91,127,166,0.10)',

  // Goal status badges
  statusActive: '#4A7C59',
  statusActiveBg: 'rgba(74,124,89,0.10)',
  statusCompleted: '#1C1917',
  statusCompletedBg: 'rgba(28,25,23,0.08)',
  statusPaused: '#9B7A3D',
  statusPausedBg: 'rgba(155,122,61,0.10)',
  statusArchived: '#A8A29E',
  statusArchivedBg: 'rgba(168,162,158,0.10)',
} as const

export const shadows = {
  card: '0 1px 4px rgba(0,0,0,0.06)',
  cardHover: '0 4px 12px rgba(0,0,0,0.08)',
  toggle: '0 1px 3px rgba(0,0,0,0.12)',
} as const

export const radius = {
  card: '16px',
  button: '8px',
  badge: '6px',
  pill: '9999px',
} as const

export const transition = {
  sidebar: 'all 200ms ease',
  hover: 'all 150ms ease',
} as const
```

**Step 2: Run the dev server to confirm no import errors**

```bash
cd frontend && npm run dev
```

Expected: compiles without errors.

**Step 3: Commit**

```bash
git add frontend/lib/theme.ts
git commit -m "feat: update design tokens to Warm Sand palette"
```

---

## Task 2: Create Collapsible Sidebar Component

**Files:**
- Create: `frontend/components/sidebar.tsx`

**Step 1: Create the sidebar component**

Create `frontend/components/sidebar.tsx`:

```tsx
"use client"

import { createContext, useContext, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  MessageSquare,
  Heart,
  Target,
  Eye,
  ChevronLeft,
  ChevronRight,
  Menu,
} from "lucide-react"
import { cn } from "@/lib/utils"

// --- Context ---

type SidebarCtx = { collapsed: boolean; toggle: () => void }
const SidebarContext = createContext<SidebarCtx>({ collapsed: false, toggle: () => {} })
export const useSidebar = () => useContext(SidebarContext)

// --- Nav config ---

const NAV = [
  {
    section: "Main",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
      { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
    ],
  },
  {
    section: "Manage",
    items: [
      { href: "/dashboard/values", label: "Values", icon: Heart },
      { href: "/dashboard/goals", label: "Goals", icon: Target },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/dashboard/transparency", label: "Transparency", icon: Eye },
    ],
  },
]

// --- Provider (wraps layout) ---

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <SidebarContext.Provider value={{ collapsed, toggle: () => setCollapsed(v => !v) }}>
      {children}
    </SidebarContext.Provider>
  )
}

// --- Sidebar nav ---

export function SidebarNav() {
  const { collapsed, toggle } = useSidebar()
  const pathname = usePathname()

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(href + "/")

  return (
    <aside
      className={cn(
        "relative flex flex-col h-screen shrink-0 transition-all duration-200 ease-in-out",
        "border-r border-black/5",
        collapsed ? "w-16" : "w-60"
      )}
      style={{ background: "#F2EDE8" }}
    >
      {/* Logo */}
      <div
        className={cn(
          "flex items-center h-14 border-b border-black/5 shrink-0",
          collapsed ? "justify-center px-0" : "px-5"
        )}
      >
        {collapsed ? (
          <span className="text-sm font-bold" style={{ color: "#C2714F" }}>EC</span>
        ) : (
          <span className="text-sm font-semibold tracking-tight" style={{ color: "#1C1917" }}>
            Ethic Companion
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV.map(({ section, items }) => (
          <div key={section} className="mb-3">
            {!collapsed && (
              <p
                className="px-5 mb-1 text-[11px] font-medium uppercase tracking-[0.08em]"
                style={{ color: "#A8A29E" }}
              >
                {section}
              </p>
            )}
            {items.map(({ href, label, icon: Icon, exact }) => {
              const active = isActive(href, exact)
              return (
                <Link
                  key={href}
                  href={href}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "flex items-center gap-3 mx-2 py-2 rounded-lg text-sm transition-colors duration-150",
                    collapsed ? "justify-center px-2" : "px-3",
                    active
                      ? "font-medium border-l-2 rounded-l-none"
                      : "hover:bg-black/5"
                  )}
                  style={
                    active
                      ? {
                          background: "rgba(194,113,79,0.10)",
                          borderColor: "#C2714F",
                          color: "#C2714F",
                        }
                      : { color: "#78716C" }
                  }
                >
                  <Icon size={17} className="shrink-0" />
                  {!collapsed && <span>{label}</span>}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="absolute -right-3 top-[68px] z-10 w-6 h-6 rounded-full flex items-center justify-center transition-colors duration-150"
        style={{
          background: "#FFFFFF",
          border: "1px solid rgba(0,0,0,0.10)",
          boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
        }}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed
          ? <ChevronRight size={11} style={{ color: "#78716C" }} />
          : <ChevronLeft size={11} style={{ color: "#78716C" }} />
        }
      </button>

      {/* User slot */}
      <div
        className={cn(
          "flex items-center gap-3 border-t border-black/5 shrink-0",
          collapsed ? "justify-center p-3" : "px-5 py-4"
        )}
      >
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold"
          style={{ background: "rgba(194,113,79,0.15)", color: "#C2714F" }}
        >
          U
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-sm font-medium truncate" style={{ color: "#1C1917" }}>User</p>
            <p className="text-xs truncate" style={{ color: "#78716C" }}>Active</p>
          </div>
        )}
      </div>
    </aside>
  )
}

// --- Mobile trigger ---

export function MobileSidebarTrigger() {
  return (
    <button className="md:hidden p-2 rounded-lg" style={{ color: "#78716C" }}>
      <Menu size={20} />
    </button>
  )
}
```

**Step 2: Verify no TypeScript errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors relating to `components/sidebar.tsx`.

**Step 3: Commit**

```bash
git add frontend/components/sidebar.tsx
git commit -m "feat: create collapsible sidebar component"
```

---

## Task 3: Create New TopBar Component

**Files:**
- Create: `frontend/components/top-bar.tsx`

**Step 1: Create the component**

Create `frontend/components/top-bar.tsx`:

```tsx
"use client"

import { usePathname } from "next/navigation"
import { MobileSidebarTrigger } from "@/components/sidebar"

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/dashboard/chat": "Chat",
  "/dashboard/values": "Values",
  "/dashboard/goals": "Goals",
  "/dashboard/transparency": "Transparency",
}

export function TopBar() {
  const pathname = usePathname()
  const title = PAGE_TITLES[pathname] ?? "Ethic Companion"

  const hour = new Date().getHours()
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"

  return (
    <header
      className="h-14 flex items-center justify-between px-8 shrink-0 border-b border-black/5"
      style={{ background: "#FAF8F5" }}
    >
      <div className="flex items-center gap-3">
        <MobileSidebarTrigger />
        <h1 className="text-[15px] font-semibold" style={{ color: "#1C1917" }}>
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm hidden sm:block" style={{ color: "#78716C" }}>
          {greeting}
        </span>
        <div className="w-px h-4 bg-black/10" />
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
          style={{
            background: "rgba(74,124,89,0.10)",
            color: "#4A7C59",
            border: "1px solid rgba(74,124,89,0.20)",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: "#4A7C59" }}
          />
          ESL Active
        </span>
      </div>
    </header>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/components/top-bar.tsx
git commit -m "feat: create new TopBar component with warm sand styling"
```

---

## Task 4: Update Dashboard Layout

**Files:**
- Modify: `frontend/app/dashboard/layout.tsx`

**Step 1: Replace layout to use new sidebar + topbar**

Replace the full contents of `frontend/app/dashboard/layout.tsx`:

```tsx
import { SidebarProvider, SidebarNav } from "@/components/sidebar"
import { TopBar } from "@/components/top-bar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarProvider>
      <div className="flex h-screen" style={{ background: "#FAF8F5" }}>
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
    </SidebarProvider>
  )
}
```

**Step 2: Run dev server and open http://localhost:3000/dashboard**

```bash
cd frontend && npm run dev
```

Expected: new collapsible sidebar visible, collapse toggle works, top bar shows page title + ESL pill.

**Step 3: Commit**

```bash
git add frontend/app/dashboard/layout.tsx
git commit -m "feat: update dashboard layout with collapsible sidebar and new topbar"
```

---

## Task 5: Redesign Dashboard Page

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

**Step 1: Replace the full page**

Replace the full contents of `frontend/app/dashboard/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { transparencyApi, goalsApi, valuesApi } from '@/lib/api'
import Link from 'next/link'
import { MessageSquare, Heart, Shield, ArrowRight, Target } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface Goal {
  id: string
  title: string
  status: string
  priority: number
}

interface ESLLog {
  id: string
  decision: { status: 'APPROVED' | 'VETOED' | 'MODIFIED'; reason: string }
  timestamp: string
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)', text: '#4A7C59', border: 'rgba(74,124,89,0.20)' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.20)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.20)' },
}

export default function DashboardPage() {
  const [goalCount, setGoalCount] = useState<number | null>(null)
  const [valueCount, setValueCount] = useState<number | null>(null)
  const [eslCount, setEslCount] = useState<number | null>(null)
  const [recentGoals, setRecentGoals] = useState<Goal[]>([])
  const [eslActivity, setEslActivity] = useState<ESLLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [goals, values, report, logs] = await Promise.allSettled([
          goalsApi.list(),
          valuesApi.list(),
          transparencyApi.report(),
          transparencyApi.logs(),
        ])
        if (goals.status === 'fulfilled') {
          const g = goals.value?.data ?? []
          setGoalCount(g.length)
          setRecentGoals(g.slice(0, 3))
        }
        if (values.status === 'fulfilled') setValueCount((values.value?.data ?? []).length)
        if (report.status === 'fulfilled') setEslCount(report.value?.total_decisions ?? 0)
        if (logs.status === 'fulfilled') setEslActivity((logs.value?.logs ?? []).slice(0, 5))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const now = new Date()
  const hour = now.getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

  const stats = [
    { label: 'Active Goals', value: goalCount, icon: Target, href: '/dashboard/goals' },
    { label: 'Values Set', value: valueCount, icon: Heart, href: '/dashboard/values' },
    { label: 'ESL Decisions Today', value: eslCount, icon: Shield, href: '/dashboard/transparency' },
  ]

  return (
    <div className="space-y-5">

      {/* Greeting card */}
      <div
        className="rounded-2xl p-6"
        style={{
          background: '#FFFFFF',
          border: '1px solid rgba(0,0,0,0.04)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}
      >
        <p className="text-sm mb-1" style={{ color: '#78716C' }}>{dateStr}</p>
        <h2 className="text-2xl font-semibold" style={{ color: '#1C1917' }}>{greeting}</h2>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        {stats.map(({ label, value, icon: Icon, href }) => (
          <Link
            key={label}
            href={href}
            className="rounded-2xl p-5 flex items-center gap-4 transition-shadow duration-150 hover:shadow-md"
            style={{
              background: '#FFFFFF',
              border: '1px solid rgba(0,0,0,0.04)',
              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
            }}
          >
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'rgba(194,113,79,0.10)' }}
            >
              <Icon size={18} style={{ color: '#C2714F' }} />
            </div>
            <div>
              {loading ? (
                <Skeleton className="h-7 w-10 mb-1" />
              ) : (
                <p className="text-2xl font-semibold" style={{ color: '#1C1917' }}>
                  {value ?? '—'}
                </p>
              )}
              <p className="text-xs" style={{ color: '#78716C' }}>{label}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Two-column: chat shortcut + active goals */}
      <div className="grid grid-cols-2 gap-4">

        {/* Chat shortcut */}
        <div
          className="rounded-2xl p-5 flex flex-col justify-between"
          style={{
            background: '#FFFFFF',
            border: '1px solid rgba(0,0,0,0.04)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare size={16} style={{ color: '#C2714F' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Chat</h3>
          </div>
          <p className="text-sm mb-4" style={{ color: '#78716C' }}>
            Ask your companion anything. Every response goes through ESL.
          </p>
          <Link
            href="/dashboard/chat"
            className="inline-flex items-center gap-1.5 text-sm font-medium"
            style={{ color: '#C2714F' }}
          >
            Open chat <ArrowRight size={14} />
          </Link>
        </div>

        {/* Active goals */}
        <div
          className="rounded-2xl p-5"
          style={{
            background: '#FFFFFF',
            border: '1px solid rgba(0,0,0,0.04)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target size={16} style={{ color: '#C2714F' }} />
              <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Active Goals</h3>
            </div>
            <Link href="/dashboard/goals" className="text-xs" style={{ color: '#C2714F' }}>
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <Skeleton key={i} className="h-5 w-full" />)}
            </div>
          ) : recentGoals.length === 0 ? (
            <p className="text-sm" style={{ color: '#A8A29E' }}>No active goals yet.</p>
          ) : (
            <ul className="space-y-2">
              {recentGoals.map(g => (
                <li key={g.id} className="flex items-center gap-2">
                  <span
                    className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: '#4A7C59' }}
                  />
                  <span className="text-sm truncate" style={{ color: '#1C1917' }}>{g.title}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ESL activity strip */}
      <div
        className="rounded-2xl p-5"
        style={{
          background: '#FFFFFF',
          border: '1px solid rgba(0,0,0,0.04)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Shield size={16} style={{ color: '#C2714F' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>Recent ESL Decisions</h3>
          </div>
          <Link href="/dashboard/transparency" className="text-xs" style={{ color: '#C2714F' }}>
            View report
          </Link>
        </div>
        {loading ? (
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-6 w-20 rounded-full" />)}
          </div>
        ) : eslActivity.length === 0 ? (
          <p className="text-sm" style={{ color: '#A8A29E' }}>No decisions recorded yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {eslActivity.map(log => {
              const status = log.decision?.status ?? 'APPROVED'
              const c = ESL_COLORS[status] ?? ESL_COLORS.APPROVED
              return (
                <span
                  key={log.id}
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
                  title={log.decision?.reason}
                >
                  {status}
                </span>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Open http://localhost:3000/dashboard and verify**

Check:
- Greeting card shows date + greeting text
- 3 stat cards show icons + numbers (or skeleton while loading)
- Two-column section shows Chat shortcut and Active Goals list
- ESL activity strip shows decision pills

**Step 3: Commit**

```bash
git add frontend/app/dashboard/page.tsx
git commit -m "feat: redesign dashboard page with warm sand layout"
```

---

## Task 6: Redesign Chat Page

**Files:**
- Modify: `frontend/app/dashboard/chat/page.tsx`

**Step 1: Replace the full page**

Replace the full contents of `frontend/app/dashboard/chat/page.tsx`:

```tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import api from '@/lib/api'
import { Send, ChevronDown, ChevronUp } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  esl_decision?: {
    status: 'APPROVED' | 'VETOED' | 'MODIFIED'
    reason: string
    violated_values?: string[]
  }
}

const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.10)',  text: '#4A7C59', border: 'rgba(74,124,89,0.25)',  leftBorder: '#4A7C59' },
  VETOED:   { bg: 'rgba(176,74,58,0.10)',  text: '#B04A3A', border: 'rgba(176,74,58,0.25)',  leftBorder: '#B04A3A' },
  MODIFIED: { bg: 'rgba(155,122,61,0.10)', text: '#9B7A3D', border: 'rgba(155,122,61,0.25)', leftBorder: '#9B7A3D' },
}

const EXAMPLE_PROMPTS = [
  "What's on my agenda today?",
  "Help me prioritize my goals",
  "Summarize my week",
]

function ESLTag({ decision }: { decision: Message['esl_decision'] }) {
  const [expanded, setExpanded] = useState(false)
  if (!decision) return null
  const c = ESL_COLORS[decision.status] ?? ESL_COLORS.APPROVED
  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(v => !v)}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium transition-opacity hover:opacity-80"
        style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
      >
        ESL: {decision.status}
        {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {expanded && (
        <p className="mt-1.5 text-xs px-2" style={{ color: '#78716C' }}>
          {decision.reason}
        </p>
      )}
    </div>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.chat.history()
      .then(h => {
        const msgs = (h.messages ?? []).map((m, i) => ({
          id: `h-${i}`,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.timestamp ?? '',
        }))
        setMessages(msgs)
      })
      .catch(console.error)
      .finally(() => setLoadingHistory(false))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text: string) => {
    const msg = text.trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])

    try {
      const result = await api.chat.send(msg)
      const aiMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: result.response ?? 'No response.',
        timestamp: result.timestamp ?? new Date().toISOString(),
        esl_decision: result.esl_decision as Message['esl_decision'],
      }
      setMessages(prev => [...prev, aiMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setLoading(false)
    }
  }

  const isEmpty = !loadingHistory && messages.length === 0

  return (
    <div
      className="flex flex-col rounded-2xl overflow-hidden"
      style={{
        background: '#FFFFFF',
        border: '1px solid rgba(0,0,0,0.04)',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        height: 'calc(100vh - 56px - 48px - 24px)', // viewport - topbar - py-6 padding
      }}
    >
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {loadingHistory && (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-12 w-3/4" />)}
          </div>
        )}

        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <p className="text-sm" style={{ color: '#A8A29E' }}>
              Ask your companion anything
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {EXAMPLE_PROMPTS.map(p => (
                <button
                  key={p}
                  onClick={() => send(p)}
                  className="px-3 py-1.5 rounded-full text-sm transition-colors hover:bg-black/5"
                  style={{
                    border: '1px solid rgba(0,0,0,0.08)',
                    color: '#78716C',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'user' ? (
              <div
                className="max-w-[70%] px-4 py-2.5 rounded-2xl rounded-br-sm text-sm"
                style={{
                  background: 'rgba(194,113,79,0.12)',
                  color: '#1C1917',
                }}
              >
                {msg.content}
              </div>
            ) : (
              <div
                className="max-w-[70%] px-4 py-2.5 rounded-2xl rounded-bl-sm text-sm border-l-2"
                style={{
                  background: '#FAF8F5',
                  color: '#1C1917',
                  borderLeftColor: msg.esl_decision
                    ? (ESL_COLORS[msg.esl_decision.status]?.leftBorder ?? '#E5E5E5')
                    : '#E5E5E5',
                }}
              >
                {msg.content}
                {msg.esl_decision && <ESLTag decision={msg.esl_decision} />}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div
              className="px-4 py-3 rounded-2xl rounded-bl-sm"
              style={{ background: '#FAF8F5', border: '1px solid rgba(0,0,0,0.06)' }}
            >
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{
                      background: '#A8A29E',
                      animationDelay: `${i * 150}ms`,
                    }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input bar */}
      <div
        className="px-4 py-3 border-t border-black/5"
        style={{ background: '#FAF8F5' }}
      >
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Message your companion…"
            rows={1}
            className="flex-1 resize-none rounded-xl px-4 py-2.5 text-sm outline-none transition-colors"
            style={{
              background: '#FFFFFF',
              border: '1px solid rgba(0,0,0,0.08)',
              color: '#1C1917',
              maxHeight: '120px',
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-opacity"
            style={{
              background: input.trim() && !loading ? '#C2714F' : 'rgba(194,113,79,0.30)',
            }}
          >
            <Send size={15} color="#FFFFFF" />
          </button>
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Open http://localhost:3000/dashboard/chat and verify**

Check:
- Empty state shows example prompt chips
- Clicking a chip sends that message
- User messages appear right-aligned with terracotta tint
- AI messages appear left-aligned with ESL border color
- ESL tag is visible and expandable
- Input bar is pinned to bottom

**Step 3: Commit**

```bash
git add frontend/app/dashboard/chat/page.tsx
git commit -m "feat: redesign chat page with warm sand bubbles and collapsible ESL tags"
```

---

## Task 7: Redesign Values Page

**Files:**
- Modify: `frontend/app/dashboard/values/page.tsx`

**Step 1: Read the current values page to understand API calls and state**

Read `frontend/app/dashboard/values/page.tsx` lines 1–80 to understand existing API usage before replacing.

**Step 2: Replace the full page**

Replace the full contents of `frontend/app/dashboard/values/page.tsx` with a new version that preserves all existing API calls (`valuesApi.list`, `valuesApi.create`, `valuesApi.update`, `valuesApi.delete`, `valuesApi.reorder`) but uses the new design:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { valuesApi, UserValue } from '@/lib/api'
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
  boundary:    { bg: 'rgba(194,113,79,0.10)',  text: '#C2714F', border: 'rgba(194,113,79,0.25)' },
  preference:  { bg: 'rgba(74,124,89,0.10)',   text: '#4A7C59', border: 'rgba(74,124,89,0.25)' },
  topic_filter:{ bg: 'rgba(155,122,61,0.10)',  text: '#9B7A3D', border: 'rgba(155,122,61,0.25)' },
  time_window: { bg: 'rgba(91,127,166,0.10)',  text: '#5B7FA6', border: 'rgba(91,127,166,0.25)' },
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

const CARD_STYLE = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.04)',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
}

export default function ValuesPage() {
  const [values, setValues] = useState<UserValue[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingValue, setEditingValue] = useState<UserValue | null>(null)

  // Form state
  const [formType, setFormType] = useState<ValueType>('boundary')
  const [formValue, setFormValue] = useState('')
  const [formPriority, setFormPriority] = useState(5)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    valuesApi.list()
      .then(r => setValues(r.data ?? []))
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
        setValues(prev => prev.map(v => v.id === editingValue.id ? (updated.data ?? v) : v))
      } else {
        const created = await valuesApi.create({
          type: formType,
          value: formValue,
          priority: formPriority,
        })
        if (created.data) setValues(prev => [...prev, created.data])
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
          <h2 className="text-base font-semibold" style={{ color: '#1C1917' }}>Your Values</h2>
          <p className="text-sm mt-0.5" style={{ color: '#78716C' }}>
            Define the boundaries ESL protects for you.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: '#C2714F', color: '#FFFFFF' }}
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
        <div
          className="rounded-2xl p-10 text-center"
          style={CARD_STYLE}
        >
          <p className="text-sm" style={{ color: '#A8A29E' }}>
            No values yet. Add your first boundary or preference.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {values.map(v => (
            <div
              key={v.id}
              className="rounded-2xl p-5 group"
              style={CARD_STYLE}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <GripVertical
                    size={14}
                    className="shrink-0 opacity-0 group-hover:opacity-40 transition-opacity cursor-grab"
                    style={{ color: '#A8A29E' }}
                  />
                  <TypeBadge type={v.type as ValueType} />
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <button
                    onClick={() => openEdit(v)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
                  >
                    <Pencil size={13} style={{ color: '#78716C' }} />
                  </button>
                  <button
                    onClick={() => handleDelete(v.id)}
                    className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
                  >
                    <Trash2 size={13} style={{ color: '#B04A3A' }} />
                  </button>
                </div>
              </div>
              <p className="mt-3 text-sm font-medium" style={{ color: '#1C1917' }}>{v.value}</p>
              <p className="mt-1 text-xs" style={{ color: '#A8A29E' }}>Priority {v.priority}</p>
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
          <div
            className="w-[400px] flex flex-col h-full shadow-2xl"
            style={{ background: '#FAF8F5' }}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-black/5">
              <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>
                {editingValue ? 'Edit Value' : 'Add Value'}
              </h3>
              <button onClick={() => setSheetOpen(false)}>
                <X size={18} style={{ color: '#78716C' }} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {/* Type */}
              {!editingValue && (
                <div>
                  <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                    Type
                  </label>
                  <select
                    value={formType}
                    onChange={e => setFormType(e.target.value as ValueType)}
                    className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                    style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                  >
                    {(Object.keys(TYPE_LABELS) as ValueType[]).map(t => (
                      <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Value text */}
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Value
                </label>
                <textarea
                  value={formValue}
                  onChange={e => setFormValue(e.target.value)}
                  placeholder="e.g. no_work_after_19h"
                  rows={3}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none resize-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>

              {/* Priority */}
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Priority (1 = highest)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={formPriority}
                  onChange={e => setFormPriority(Number(e.target.value))}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-black/5 flex gap-2">
              <button
                onClick={() => setSheetOpen(false)}
                className="flex-1 py-2 rounded-lg text-sm font-medium"
                style={{ background: 'rgba(0,0,0,0.05)', color: '#78716C' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formValue.trim() || saving}
                className="flex-1 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 transition-opacity disabled:opacity-50"
                style={{ background: '#C2714F', color: '#FFFFFF' }}
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
```

**Step 3: Open http://localhost:3000/dashboard/values and verify**

Check:
- 2-column card grid renders with type badges
- Add Value opens slide-over from the right
- Edit + delete buttons appear on hover
- Form saves and updates list

**Step 4: Commit**

```bash
git add frontend/app/dashboard/values/page.tsx
git commit -m "feat: redesign values page with card grid and slide-over sheet"
```

---

## Task 8: Redesign Goals Page

**Files:**
- Modify: `frontend/app/dashboard/goals/page.tsx`

**Step 1: Read the current goals page to understand API calls**

Read `frontend/app/dashboard/goals/page.tsx` lines 1–80 to understand existing API usage before replacing.

**Step 2: Replace the full page**

Replace the full contents of `frontend/app/dashboard/goals/page.tsx`:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { goalsApi, Goal } from '@/lib/api'
import { Plus, MoreHorizontal, Check, X, ChevronDown, ChevronRight } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

type GoalStatus = 'active' | 'completed' | 'paused' | 'archived'

const STATUS_COLORS: Record<GoalStatus, { bg: string; text: string; border: string }> = {
  active:    { bg: 'rgba(74,124,89,0.10)',   text: '#4A7C59', border: 'rgba(74,124,89,0.25)' },
  completed: { bg: 'rgba(28,25,23,0.08)',    text: '#1C1917', border: 'rgba(28,25,23,0.15)' },
  paused:    { bg: 'rgba(155,122,61,0.10)',  text: '#9B7A3D', border: 'rgba(155,122,61,0.25)' },
  archived:  { bg: 'rgba(168,162,158,0.10)', text: '#A8A29E', border: 'rgba(168,162,158,0.25)' },
}

const PRIORITY_COLORS = ['#C2714F', '#9B7A3D', '#5B7FA6', '#4A7C59', '#A8A29E']

function StatusBadge({ status }: { status: GoalStatus }) {
  const c = STATUS_COLORS[status] ?? STATUS_COLORS.active
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium capitalize"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      {status}
    </span>
  )
}

const CARD_STYLE = {
  background: '#FFFFFF',
  border: '1px solid rgba(0,0,0,0.04)',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
}

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([])
  const [loading, setLoading] = useState(true)
  const [showCompleted, setShowCompleted] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null)
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  // Form state
  const [formTitle, setFormTitle] = useState('')
  const [formDesc, setFormDesc] = useState('')
  const [formPriority, setFormPriority] = useState(5)
  const [formDate, setFormDate] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    goalsApi.list({ active_only: false })
      .then(r => setGoals(r.data ?? []))
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
    setFormDate('')
    setSheetOpen(true)
  }

  const openEdit = (g: Goal) => {
    setEditingGoal(g)
    setFormTitle(g.title)
    setFormDesc(g.description ?? '')
    setFormPriority(g.priority)
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
          target_date: formDate || undefined,
        })
        setGoals(prev => prev.map(g => g.id === editingGoal.id ? (updated.data ?? g) : g))
      } else {
        const created = await goalsApi.create({
          title: formTitle,
          description: formDesc || undefined,
          priority: formPriority,
          target_date: formDate || undefined,
        })
        if (created.data) setGoals(prev => [...prev, created.data])
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
      await goalsApi.complete(id)
      setGoals(prev => prev.map(g => g.id === id ? { ...g, status: 'completed' } : g))
      setOpenMenu(null)
    } catch (e) { console.error(e) }
  }

  const handleDelete = async (id: string) => {
    try {
      await goalsApi.delete(id)
      setGoals(prev => prev.filter(g => g.id !== id))
      setOpenMenu(null)
    } catch (e) { console.error(e) }
  }

  const GoalRow = ({ goal }: { goal: Goal }) => (
    <div
      className="flex items-center gap-4 px-5 py-4 rounded-xl group relative"
      style={{ border: '1px solid rgba(0,0,0,0.04)', background: '#FFFFFF' }}
    >
      {/* Priority dot */}
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: PRIORITY_COLORS[Math.min(goal.priority - 1, 4)] }}
      />

      {/* Title + desc */}
      <div className="flex-1 min-w-0">
        <p
          className="text-sm font-medium truncate"
          style={{ color: '#1C1917', textDecoration: goal.status === 'completed' ? 'line-through' : 'none', opacity: goal.status === 'completed' ? 0.5 : 1 }}
        >
          {goal.title}
        </p>
        {goal.description && (
          <p className="text-xs mt-0.5 truncate" style={{ color: '#A8A29E' }}>{goal.description}</p>
        )}
      </div>

      {/* Target date */}
      {goal.target_date && (
        <span className="text-xs shrink-0 hidden sm:block" style={{ color: '#A8A29E' }}>
          {new Date(goal.target_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      )}

      {/* Status badge */}
      <StatusBadge status={goal.status as GoalStatus} />

      {/* Menu */}
      <div className="relative">
        <button
          onClick={() => setOpenMenu(openMenu === goal.id ? null : goal.id)}
          className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-black/5 transition-colors"
        >
          <MoreHorizontal size={15} style={{ color: '#78716C' }} />
        </button>
        {openMenu === goal.id && (
          <div
            className="absolute right-0 top-8 z-10 w-36 rounded-xl py-1 text-sm shadow-lg"
            style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.08)' }}
          >
            <button
              onClick={() => openEdit(goal)}
              className="w-full text-left px-3 py-2 hover:bg-black/5 transition-colors"
              style={{ color: '#1C1917' }}
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
              onClick={() => handleDelete(goal.id)}
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

  return (
    <div className="space-y-5" onClick={() => openMenu && setOpenMenu(null)}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: '#1C1917' }}>Your Goals</h2>
          <p className="text-sm mt-0.5" style={{ color: '#78716C' }}>
            Goals inform ESL about your priorities.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-90"
          style={{ background: '#C2714F', color: '#FFFFFF' }}
        >
          <Plus size={15} />
          Add Goal
        </button>
      </div>

      {/* Active goals */}
      <div
        className="rounded-2xl overflow-hidden"
        style={CARD_STYLE}
      >
        <div className="px-5 py-3 border-b border-black/5">
          <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: '#78716C' }}>
            Active & Paused
          </h3>
        </div>
        <div className="p-3 space-y-2">
          {loading ? (
            [1, 2, 3].map(i => <Skeleton key={i} className="h-14 rounded-xl" />)
          ) : activeGoals.length === 0 ? (
            <p className="px-2 py-4 text-sm text-center" style={{ color: '#A8A29E' }}>
              No active goals. Add one to get started.
            </p>
          ) : (
            activeGoals.map(g => <GoalRow key={g.id} goal={g} />)
          )}
        </div>
      </div>

      {/* Completed goals (collapsed) */}
      {completedGoals.length > 0 && (
        <div className="rounded-2xl overflow-hidden" style={CARD_STYLE}>
          <button
            onClick={() => setShowCompleted(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3 border-b border-black/5 hover:bg-black/[0.02] transition-colors"
          >
            <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: '#78716C' }}>
              Completed & Archived ({completedGoals.length})
            </h3>
            {showCompleted
              ? <ChevronDown size={14} style={{ color: '#A8A29E' }} />
              : <ChevronRight size={14} style={{ color: '#A8A29E' }} />
            }
          </button>
          {showCompleted && (
            <div className="p-3 space-y-2">
              {completedGoals.map(g => <GoalRow key={g.id} goal={g} />)}
            </div>
          )}
        </div>
      )}

      {/* Slide-over sheet */}
      {sheetOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="flex-1 bg-black/20 backdrop-blur-sm"
            onClick={() => setSheetOpen(false)}
          />
          <div
            className="w-[400px] flex flex-col h-full shadow-2xl"
            style={{ background: '#FAF8F5' }}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-black/5">
              <h3 className="text-sm font-semibold" style={{ color: '#1C1917' }}>
                {editingGoal ? 'Edit Goal' : 'Add Goal'}
              </h3>
              <button onClick={() => setSheetOpen(false)}>
                <X size={18} style={{ color: '#78716C' }} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Title
                </label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={e => setFormTitle(e.target.value)}
                  placeholder="e.g. Launch MVP"
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Description
                </label>
                <textarea
                  value={formDesc}
                  onChange={e => setFormDesc(e.target.value)}
                  placeholder="Optional details…"
                  rows={3}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none resize-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Priority (1 = highest)
                </label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={formPriority}
                  onChange={e => setFormPriority(Number(e.target.value))}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 uppercase tracking-wide" style={{ color: '#78716C' }}>
                  Target Date
                </label>
                <input
                  type="date"
                  value={formDate}
                  onChange={e => setFormDate(e.target.value)}
                  className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.10)', color: '#1C1917' }}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-black/5 flex gap-2">
              <button
                onClick={() => setSheetOpen(false)}
                className="flex-1 py-2 rounded-lg text-sm font-medium"
                style={{ background: 'rgba(0,0,0,0.05)', color: '#78716C' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!formTitle.trim() || saving}
                className="flex-1 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 transition-opacity disabled:opacity-50"
                style={{ background: '#C2714F', color: '#FFFFFF' }}
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
```

**Step 3: Open http://localhost:3000/dashboard/goals and verify**

Check:
- Active goals list with priority dots and status badges
- Completed goals section is collapsed, reveals on click
- Add Goal opens slide-over
- Action menu (⋯) shows edit / mark complete / archive
- All API operations work (create, update, complete, archive)

**Step 4: Commit**

```bash
git add frontend/app/dashboard/goals/page.tsx
git commit -m "feat: redesign goals page with list layout, status badges, and slide-over"
```

---

## Final Verification

```bash
cd frontend && npm run build
```

Expected: build succeeds with no TypeScript or compilation errors.

```bash
git log --oneline -8
```

Expected: 8 clean commits for each task.
