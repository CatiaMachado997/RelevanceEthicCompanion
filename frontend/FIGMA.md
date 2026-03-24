# Figma Design System Rules

## Source
Figma file: CaseAI Match Design (HPMK4Ss4dtA7FLSI4L7Jpy)
Adapted for: Ethic Companion (Next.js + TypeScript + Tailwind CSS v4)

## Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--gray-950` | `#2A222D` | Logo backgrounds, deepest elements |
| `--gray-900` | `#332B36` | Primary text, headings, active states |
| `--gray-600` | `#695E6E` | Secondary text, labels, muted content |
| `--gray-400` | `#B0A6B4` | Placeholder text, disabled states |
| `--gray-200` | `#E4DEE7` | Borders, dividers, inactive dots |
| `--gray-50`  | `#F9F6FA` | Surface tint, card backgrounds, panels |
| `--white`    | `#FFFFFF` | Page background, form inputs |

Semantic mappings:
- `--foreground` → `#332B36`
- `--background` → `#FFFFFF`
- `--muted-foreground` → `#695E6E`
- `--border` → `#E4DEE7`
- `--input` → `#E4DEE7`
- `--ring` → `#332B36`

Functional colors (preserved from original design):
- ESL Approved: `#4A7C59`
- ESL Vetoed: `#B04A3A`
- ESL Modified: `#9B7A3D`
- Time Window: `#5B7FA6`

## Typography

Font: Inter (weight 400, 500)

| Scale | Size | Line Height | Weight |
|-------|------|-------------|--------|
| `text-xs` | 12px | 18px | 500 |
| `text-sm` | 14px | 20px | 400/500 |
| `text-base` | 16px | 24px | 500 |
| `text-lg` | 18px | 28px | 500 |
| `text-2xl` | 24px | 32px | 500 |

## Spacing

8px grid: `8, 12, 16, 24, 32, 48, 80px`

## Border Radius

- Inputs/Fields: `rounded-xl` (12px)
- Buttons: `rounded-[14px]`
- Cards/Panels: `rounded-2xl` (16px)
- Checkboxes: `rounded-md` (6px)
- Pills/Dots: `rounded-full`

## Component Patterns

### Input
```tsx
<input className="border border-[#E4DEE7] rounded-xl px-3 py-2.5 text-sm text-[#332B36] placeholder:text-[#B0A6B4] focus:border-[#332B36] focus:ring-2 focus:ring-[#332B36]/10 bg-white" />
```

### Button (Primary)
```tsx
<button className="bg-[#332B36] text-white rounded-[14px] px-5 py-3 text-base font-medium hover:bg-[#2A222D] disabled:bg-[#E4DEE7] transition-colors" />
```

### Card
```tsx
<div className="bg-white rounded-2xl border border-[#E4DEE7] shadow-[0_1px_3px_rgba(42,34,45,0.08)] hover:shadow-[0_4px_12px_rgba(42,34,45,0.10)]" />
```

### Surface Panel (testimonial / sidebar bg)
```tsx
<div className="bg-[#F9F6FA] rounded-2xl" />
```

## Asset Handling

- Images: Next.js `<Image>` component with `sizes` prop
- Icons: `lucide-react`
- Logos: SVG inline or `<Image>` for raster

## Icon System

Use `lucide-react`. Size 16px (text), 20px (UI), 24px (feature icons).

## Responsive Breakpoints

- Mobile: < 640px (sm)
- Tablet: 640-1024px
- Desktop: > 1024px (lg)
