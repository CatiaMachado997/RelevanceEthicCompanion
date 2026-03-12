# ElevenLabs Theme — Design Document

**Goal:** Apply the ElevenLabs visual theme (clean white, black accents, pill buttons, narrow icon sidebar) to Ethic Companion, replacing the current Warm Sand palette.

**Reference:** https://www.figma.com/design/1IVI6lUGyyH55JO25n1HX6/ElevenLabs---AI-Audio-Platform-SaaS-UI--Community-

---

## Section 1: Design System Tokens (`lib/theme.ts`)

Replace Warm Sand palette with ElevenLabs palette. ESL status colors (green/amber/red) are unchanged.

| Token | Old | New |
|---|---|---|
| `pageBg` | `#FAF8F5` | `#feffff` |
| `sidebarBg` | `#F2EDE8` | `#fbfafa` |
| `surface` | `#FFFFFF` | `#feffff` |
| `surfaceBorder` | `rgba(0,0,0,0.04)` | `rgba(23,26,31,0.07)` |
| `textPrimary` | `#1C1917` | `#171a1f` |
| `textSecondary` | `#78716C` | `#9095a1` |
| `textMuted` | `#A8A29E` | `#9095a1` |
| `accent` | `#C2714F` | `#050505` |
| `accentLight` | `rgba(194,113,79,0.10)` | `rgba(5,5,5,0.06)` |
| `accentBorder` | `rgba(194,113,79,0.30)` | `rgba(5,5,5,0.15)` |
| `shadows.card` | `0 1px 4px rgba(0,0,0,0.06)` | `0px 3px 16px rgba(23,26,31,0.12), 0px 0px 1px rgba(23,26,31,0.07)` |
| `shadows.cardHover` | `0 4px 12px rgba(0,0,0,0.08)` | `0px 6px 24px rgba(23,26,31,0.16), 0px 0px 1px rgba(23,26,31,0.07)` |
| `radius.button` | `8px` | `20px` (pill) |
| `radius.card` | `16px` | `24px` |

---

## Section 2: Layout & Sidebar

### Sidebar (`components/sidebar.tsx`)
- Always icon-only, fixed width `64px` — remove collapse toggle entirely
- Background `#fbfafa`, right border `rgba(23,26,31,0.07)`
- Top logo: "EC" in small white rounded box (`rounded-lg`, white bg, subtle shadow)
- Nav items: icon centered, `44px` touch target, active = `#f3f3f4` bg tint, active icon color `#171a1f`, inactive icon color `#9095a1`
- Remove: `SidebarProvider`, `useSidebar`, collapse button, section labels, text labels
- Bottom: user avatar + shield icon

### TopBar (`components/top-bar.tsx`)
- White bg, bottom shadow `0px 0px 2px rgba(23,26,31,0.12), 0px 0px 1px rgba(23,26,31,0.07)`
- Left: page title (`font-semibold text-2xl #171a1f`) + subtitle (`text-sm #9095a1`)
- Right: optional action button (pill, black bg, white text)
- Remove: time-based greeting, ESL Active pill

### Layout (`app/dashboard/layout.tsx`)
- Remove `SidebarProvider` wrapper (sidebar is no longer context-driven)
- Sidebar is always `w-16` (no dynamic width)
- Main content area: no max-width cap

---

## Section 3: Component Updates

### Chat bubbles (`app/dashboard/chat/page.tsx`)
- User bubble: `rgba(5,5,5,0.06)` bg (was terracotta tint), `#171a1f` text
- AI bubble: unchanged structure, left border `#eaebec` neutral (ESL still overrides with color)

### Buttons (across all pages)
- Primary: `rounded-full`, black bg, white text
- Secondary: `rounded-full`, white bg, border `#eaebec`

### Cards (automatic via tokens)
- `rounded-3xl` (24px), larger shadow — propagates automatically

### Badges (automatic via tokens)
- Value type badges and goal status badges update via existing token references

---

## Files Changed

| File | Change |
|---|---|
| `frontend/lib/theme.ts` | Token swap |
| `frontend/components/sidebar.tsx` | Always-icon-only, remove context/toggle |
| `frontend/components/top-bar.tsx` | ElevenLabs header style |
| `frontend/app/dashboard/layout.tsx` | Remove SidebarProvider, fixed w-16 sidebar |
| `frontend/app/dashboard/chat/page.tsx` | Chat bubble colors |
