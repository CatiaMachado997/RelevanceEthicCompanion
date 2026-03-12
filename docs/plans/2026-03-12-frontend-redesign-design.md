# Frontend Redesign — Design Document

**Date:** 2026-03-12
**Scope:** Dashboard, Chat, Values, Goals (core experience)
**Direction:** Warm Sand — clean & minimal meets warm & human

---

## Design System

### Colors
| Token | Value | Usage |
|-------|-------|-------|
| Background | `#FAF8F5` | Page background |
| Surface | `#FFFFFF` + `rgba(0,0,0,0.04)` border | Cards |
| Sidebar | `#F2EDE8` | Sidebar background |
| Text primary | `#1C1917` | Headings, body |
| Text secondary | `#78716C` | Labels, meta |
| Accent | `#C2714F` | CTAs, active states, links |
| ESL Approved | `#4A7C59` | Sage green |
| ESL Vetoed | `#B04A3A` | Muted red |
| ESL Modified | `#9B7A3D` | Warm amber |

### Typography
- **Font:** Geist Sans
- **Headings:** semibold, tight tracking
- **Body:** regular, 15px, 1.6 line height
- **Labels:** 12px uppercase, 0.08em letter spacing

### Shape & Spacing
- Card radius: 16px
- Card shadow: `0 1px 4px rgba(0,0,0,0.06)`
- Button radius: 8px
- Sidebar expanded: 240px | collapsed: 64px | transition: 200ms ease

---

## Layout

### Collapsible Sidebar
- Default: 240px — icon + label per nav item
- Collapsed: 64px — icons only with tooltips on hover
- Toggle: chevron button pinned to right edge of sidebar
- Active state: terracotta left border + soft terracotta tint background
- Nav sections:
  - **Main:** Dashboard, Chat
  - **Manage:** Values, Goals
  - **Insights:** Transparency
- Bottom: user avatar + name (expanded) / avatar only (collapsed)

### Main Content Area
- Top bar: page title (left) + ESL status pill + user greeting (right)
- Content: max-width 1100px, centered, 32px padding
- No nested sidebars — feature-specific sidebars replaced by slide-over sheets

### Mobile
- Sidebar hidden, opens as drawer from hamburger in top bar
- Full-width content, 16px padding

---

## Pages

### Dashboard
- Greeting card: "Good morning, [name]" + today's date
- 3-column stat row: Active Goals / Values Set / ESL Decisions Today
- Two-column section: Recent Chat (last 3 messages) + Active Goals (top 3)
- ESL activity strip: last 5 decisions as pill badges

### Chat
- Full-height message thread
- AI bubbles: left-aligned, warm white card, left border colored by ESL status
- User bubbles: right-aligned, terracotta tint
- Collapsible ESL tag per AI message ("ESL: APPROVED" — click to expand reason)
- Fixed bottom input bar: rounded pill, terracotta send button
- Empty state: 3 example prompt chips

### Values
- 2-column card grid
- Each card: type badge + value text + priority number + drag handle (on hover)
- Type badges: boundary (terracotta), preference (sage), topic filter (amber), time window (slate)
- "Add Value" top-right → slide-over sheet

### Goals
- Vertical list
- Each row: priority dot + title + status badge + target date + action menu (⋯)
- Status badges: active (sage), completed (charcoal), paused (amber), archived (muted)
- "Add Goal" top-right → slide-over sheet
- Completed goals collapsed at bottom with reveal toggle
