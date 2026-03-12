# Ethic Companion — Design System Rules
> Reference for Claude Code when implementing Figma designs via MCP.
> Theme: **Anthropic Console dark** — grey/black backgrounds, terracotta accent, clean minimal layout.

---

## 1. Token Definitions

### Two token systems exist — prefer `globals.css` CSS variables for new work

#### Primary: CSS variables (`frontend/app/globals.css`)
Tailwind 4 uses `@theme inline` to expose CSS HSL variables as Tailwind utility classes:

```css
/* Usage in Tailwind: bg-background, text-foreground, bg-card, etc. */
:root {
  --background: 35 40% 92%;     /* light mode page bg */
  --foreground: 25 30% 25%;     /* light mode text */
  --card: 35 35% 95%;           /* card surface */
  --primary: 25 75% 47%;        /* terracotta accent #C2714F */
  --border: 35 25% 80%;         /* border color */
  --muted-foreground: 25 20% 45%; /* secondary text */
}
```

#### Target dark theme (Anthropic Console style — apply these values):
```css
.dark {
  --background: 0 0% 8%;         /* #141414 — near-black page bg */
  --foreground: 0 0% 96%;        /* #f5f5f5 — primary text */
  --card: 0 0% 12%;              /* #1e1e1e — card surface */
  --card-foreground: 0 0% 96%;
  --border: 0 0% 20%;            /* #333333 — subtle border */
  --muted: 0 0% 15%;             /* #262626 — muted surface */
  --muted-foreground: 0 0% 55%;  /* #8c8c8c — secondary text */
  --primary: 25 75% 47%;         /* #C2714F — terracotta, unchanged */
  --primary-foreground: 0 0% 100%;
  --input: 0 0% 15%;             /* dark input bg */
}
```

#### Secondary: `lib/theme.ts` (flat JS constants)
Used by newer redesigned page components. These will be updated to match the dark theme:
```ts
// Current (Warm Sand) → Target (Dark)
colors.pageBg:      '#FAF8F5' → '#141414'
colors.sidebarBg:   '#F2EDE8' → '#0f0f0f'
colors.surface:     '#FFFFFF' → '#1e1e1e'
colors.textPrimary: '#1C1917' → '#f5f5f5'
colors.textSecondary:'#78716C'→ '#8c8c8c'
colors.accent:      '#C2714F' → '#C2714F'  // KEEP terracotta
```

---

## 2. Component Library

### Location: `frontend/components/ui/`
Built on **Radix UI** primitives with Tailwind classes via `class-variance-authority` (CVA).

Key components and their files:
| Component | File | Notes |
|-----------|------|-------|
| Button | `ui/button.tsx` | CVA variants: default, secondary, outline, ghost, destructive |
| Card | `ui/card.tsx` | Radix-free, uses `bg-card border-border` tokens |
| Input | `ui/input.tsx` | Uses `bg-input border-border` tokens |
| Badge | `ui/badge.tsx` | CVA variants |
| Dialog | `ui/dialog.tsx` | Radix Dialog |
| Sheet | `ui/sheet.tsx` | Radix Dialog (slide-over) |
| Skeleton | `ui/skeleton.tsx` | Uses shimmer animation |
| Dropdown | `ui/dropdown-menu.tsx` | Radix DropdownMenu |

**Pattern for using components:**
```tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

// Primary button (terracotta)
<Button>Save</Button>

// Ghost/outline
<Button variant="outline">Cancel</Button>
```

---

## 3. Frameworks & Libraries

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Next.js App Router | 16.0.3 |
| UI | React | 19.2.0 |
| Language | TypeScript | 5 |
| Styling | Tailwind CSS v4 | 4.1.17 |
| Components | Radix UI | various |
| Animation | Framer Motion | 12.23.25 |
| Drag & drop | @dnd-kit | 6.3.1 |
| Font | Geist | 1.7.0 |
| Icons | lucide-react | 0.554.0 |
| Utility | clsx + tailwind-merge via cn() | — |

**Tailwind v4 note**: Uses `@import "tailwindcss"` in globals.css (not `@tailwind base/components/utilities`). Config is in `postcss.config.mjs` via `@tailwindcss/postcss`.

---

## 4. Asset Management

- Images: Stored in `frontend/public/` — referenced as `/image.png`
- No CDN configured — all assets are local
- Figma image assets: Download from Figma MCP URLs (expire in 7 days), save to `public/` or use as `src` directly during dev
- No image optimization pipeline beyond Next.js built-in `next/image`

---

## 5. Icon System

**Library**: `lucide-react` exclusively. No custom SVG icon sets.

**Import pattern:**
```tsx
import { Shield, Target, MessageSquare, ChevronDown } from "lucide-react"

// Usage — always pass size and color explicitly:
<Shield size={18} className="text-muted-foreground" />
// or inline:
<Shield size={18} style={{ color: '#C2714F' }} />
```

**Sizing conventions:**
- Nav icons: `size={18}` or `size={17}`
- Inline/card icons: `size={16}`
- Empty state icons: `size={32}` or `size={40}`
- Badge/label icons: `size={12}` or `size={14}`

---

## 6. Styling Approach

### Method: Tailwind v4 + inline styles (mixed)
The codebase uses **three styling patterns** — use whichever matches surrounding code:

**Pattern A — Tailwind semantic tokens** (preferred for new components):
```tsx
<div className="bg-card text-foreground border border-border rounded-lg p-4">
```

**Pattern B — Tailwind arbitrary hex** (common in redesigned pages):
```tsx
<div className="bg-[#1e1e1e] text-[#f5f5f5] border border-[#333]">
```

**Pattern C — Inline style objects** (used in dashboard, chat pages for dynamic colors):
```tsx
<div style={{ background: '#1e1e1e', color: '#f5f5f5', border: '1px solid rgba(255,255,255,0.08)' }}>
```

**`cn()` utility** — always use for conditional classes:
```tsx
import { cn } from "@/lib/utils"
<div className={cn("base-class", isActive && "active-class", className)}>
```

### Responsive design
Tailwind breakpoints: `sm:` `md:` `lg:`. Mobile-first. Layout switches at `md:` (768px).

### Dark theme implementation
Add `class="dark"` to `<html>` in `layout.tsx`. All `bg-background`, `bg-card`, etc. auto-switch via CSS variables.

---

## 7. Project Structure

```
frontend/
├── app/
│   ├── globals.css          ← CSS variables + Tailwind base
│   ├── layout.tsx           ← Root layout (font, html class)
│   └── dashboard/
│       ├── layout.tsx       ← Dashboard shell (sidebar + topbar)
│       ├── page.tsx         ← Dashboard home
│       ├── chat/page.tsx
│       ├── goals/page.tsx
│       ├── values/page.tsx
│       ├── transparency/page.tsx
│       └── search/page.tsx
├── components/
│   ├── sidebar.tsx          ← SidebarNav (icon-only, always w-16)
│   ├── top-bar.tsx          ← Page header (title + subtitle)
│   └── ui/                  ← Radix-based primitive components
├── lib/
│   ├── api.ts               ← All API calls (valuesApi, goalsApi, chatApi, etc.)
│   ├── theme.ts             ← Flat JS design tokens
│   └── utils.ts             ← cn() utility
```

**Page anatomy** (every dashboard page):
1. `layout.tsx` renders `<SidebarNav>` + `<TopBar>` + `<main>` wrapper
2. Each `page.tsx` is a Client Component (`"use client"`)
3. Data fetching: `useEffect` + API calls from `@/lib/api`
4. No server components in dashboard pages currently

---

## 8. Anthropic UI Kit Design Rules

Based on the Anthropic Console (console.anthropic.com) UI Kit reference.

### Color palette (dark theme — target state)
```
Page background:    #141414  (near-black charcoal)
Sidebar background: #0f0f0f  (slightly darker than page)
Nav bar background: #1a1a1a  (header bar)
Card surface:       #1e1e1e  (elevated surface)
Card border:        rgba(255,255,255,0.08)  (very subtle white border)
Input background:   #1a1a1a
Input border:       rgba(255,255,255,0.10)

Text primary:       #f5f5f5  (off-white)
Text secondary:     #8c8c8c  (mid gray)
Text muted:         #555555  (dim gray)

Accent/Primary:     #C2714F  (terracotta — KEEP, matches Anthropic accent)
Accent hover:       #d4845f
Accent light bg:    rgba(194,113,79,0.12)

ESL Approved:       #4A7C59  (sage green — KEEP)
ESL Vetoed:         #B04A3A  (muted red — KEEP)
ESL Modified:       #9B7A3D  (amber — KEEP)
```

### Typography
- Font: `font-geist` (already installed as `geist` package)
- Page title: `text-2xl font-semibold` `#f5f5f5`
- Page subtitle: `text-sm` `#8c8c8c`
- Section headers: `text-sm font-medium uppercase tracking-wide` `#8c8c8c`
- Body: `text-sm` `#f5f5f5`
- Muted: `text-xs` `#555555`

### Layout
- **Navigation**: Horizontal top nav (Anthropic Console style) OR narrow icon sidebar — current sidebar.tsx is icon-only at w-16, keep as-is
- **Header bar**: `h-14` or `h-[80px]`, white/dark bg, bottom border, page title + subtitle left, action right
- **Content area**: max-w-[1100px] centered, px-8 py-6
- **Cards**: `rounded-2xl` (24px), `bg-card border border-[rgba(255,255,255,0.08)]`, shadow `0 1px 4px rgba(0,0,0,0.4)`

### Component patterns (Anthropic Console)
```tsx
// Primary button — terracotta pill
<button className="px-5 py-2 rounded-full bg-[#C2714F] text-white text-sm font-medium hover:bg-[#d4845f]">

// Secondary button — ghost
<button className="px-5 py-2 rounded-full border border-[rgba(255,255,255,0.15)] text-[#f5f5f5] text-sm hover:bg-white/5">

// Card
<div className="rounded-2xl bg-[#1e1e1e] border border-[rgba(255,255,255,0.08)] p-5">

// Input
<input className="w-full rounded-lg bg-[#1a1a1a] border border-[rgba(255,255,255,0.10)] px-3 py-2 text-sm text-[#f5f5f5] placeholder:text-[#555] focus:border-[#C2714F] outline-none">

// Modal/Dialog backdrop
<div className="bg-black/60">
  <div className="rounded-2xl bg-[#1e1e1e] border border-[rgba(255,255,255,0.08)] shadow-2xl p-6">

// Nav item active state
<div className="rounded-xl bg-[rgba(255,255,255,0.06)] text-[#f5f5f5]">

// Nav item inactive
<div className="text-[#8c8c8c] hover:bg-[rgba(255,255,255,0.04)]">
```

### ESL-specific patterns (Ethic Companion only)
```tsx
// ESL decision badge
const ESL_COLORS = {
  APPROVED: { bg: 'rgba(74,124,89,0.15)',  text: '#4A7C59', border: 'rgba(74,124,89,0.30)' },
  VETOED:   { bg: 'rgba(176,74,58,0.15)',  text: '#B04A3A', border: 'rgba(176,74,58,0.30)' },
  MODIFIED: { bg: 'rgba(155,122,61,0.15)', text: '#9B7A3D', border: 'rgba(155,122,61,0.30)' },
}
// These NEVER change regardless of theme.

// AI message bubble — left border color signals ESL status
<div style={{ background: '#242424', borderLeftColor: ESL_COLORS[status].text }}>
```

---

## 9. Figma MCP Integration Workflow

When given a Figma URL:

1. **Extract** `fileKey` and `nodeId` from URL: `?node-id=1-2` → `1:2`
2. **Get metadata first** if node is a page (`get_metadata`) to find specific frame IDs
3. **Get design context** (`get_design_context`) on specific frames, not the root page
4. **Screenshot** is included automatically — use it as ground truth for visual decisions
5. **Adapt code** to this project's stack — never copy Figma output verbatim:
   - Replace `ABeeZee` or any non-Geist font with `font-geist`
   - Replace light colors with dark theme equivalents (see Section 8)
   - Replace absolute positioning with Tailwind flex/grid layouts
   - Use `cn()` for conditional classes
   - Use `lucide-react` for any icons, never inline SVG
6. **Color mapping** from Figma to this project:
   - Figma white `#ffffff` → `#1e1e1e` (card surface in dark theme)
   - Figma light gray `#f3f3f4` → `rgba(255,255,255,0.06)` (subtle highlight)
   - Figma dark text `#171a1f` → `#f5f5f5` (inverted for dark theme)
   - Figma muted `#9095a1` → `#8c8c8c`
   - Figma border `#eaebec` → `rgba(255,255,255,0.08)`
   - Any orange/terracotta in Figma → `#C2714F` (keep)
