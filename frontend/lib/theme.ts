// Figma Design System — Ethic Companion (warm purple-gray palette)

export const colors = {
  // Backgrounds
  pageBg: '#ffffff',
  sidebarBg: '#f9f6fa',
  surface: '#ffffff',
  surfaceBorder: '#e4dee7',

  // Text
  textPrimary: '#332b36',
  textSecondary: '#695e6e',
  textMuted: '#b0a6b4',

  // Accent (warm purple-gray)
  accent: '#332b36',
  accentLight: 'rgba(51,43,54,0.05)',
  accentBorder: '#e4dee7',

  // ESL status (unchanged — functional colors)
  eslApproved: '#4A7C59',
  eslApprovedBg: 'rgba(74,124,89,0.10)',
  eslVetoed: '#B04A3A',
  eslVetoedBg: 'rgba(176,74,58,0.10)',
  eslModified: '#9B7A3D',
  eslModifiedBg: 'rgba(155,122,61,0.10)',

  // Value type badges — monochrome (boundary) + functional (others)
  badgeBoundary: '#332b36',
  badgeBoundaryBg: 'rgba(51,43,54,0.06)',
  badgePreference: '#4A7C59',
  badgePreferenceBg: 'rgba(74,124,89,0.10)',
  badgeTopicFilter: '#9B7A3D',
  badgeTopicFilterBg: 'rgba(155,122,61,0.10)',
  badgeTimeWindow: '#5B7FA6',
  badgeTimeWindowBg: 'rgba(91,127,166,0.10)',

  // Goal status badges
  statusActive: '#4A7C59',
  statusActiveBg: 'rgba(74,124,89,0.10)',
  statusCompleted: '#332b36',
  statusCompletedBg: 'rgba(51,43,54,0.08)',
  statusPaused: '#9B7A3D',
  statusPausedBg: 'rgba(155,122,61,0.10)',
  statusArchived: '#b0a6b4',
  statusArchivedBg: 'rgba(176,166,180,0.10)',
} as const

export const shadows = {
  card: '0 1px 3px rgba(42,34,45,0.08)',
  cardHover: '0 4px 12px rgba(42,34,45,0.10)',
  toggle: '0 1px 3px rgba(42,34,45,0.12)',
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
